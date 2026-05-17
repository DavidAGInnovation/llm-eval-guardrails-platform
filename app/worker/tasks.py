import datetime as dt
import uuid

import structlog
from celery import states
from celery.exceptions import Ignore
from sqlalchemy import select

from app.db.models import Dataset, EvaluationResult, EvaluationRun, GuardrailPolicy, PromptSample
from app.db.session import SessionLocal
from app.services.guardrails import evaluate_policy
from app.services.providers import get_provider
from app.services.scoring import score_response
from app.worker.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="run_evaluation")
def run_evaluation(run_id: str) -> dict:
    db = SessionLocal()
    run = None
    try:
        run_uuid = uuid.UUID(run_id)
        run = db.get(EvaluationRun, run_uuid)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        run.status = "running"
        db.commit()

        dataset = db.get(Dataset, run.dataset_id)
        policy = db.get(GuardrailPolicy, run.policy_id)
        if not dataset or not policy:
            raise ValueError("Missing dataset or policy")

        prompts = db.execute(select(PromptSample).where(PromptSample.dataset_id == dataset.id)).scalars().all()
        provider = get_provider(run.provider)

        quality_scores: list[float] = []
        hallucination_scores: list[float] = []
        toxicity_scores: list[float] = []
        blocked_count = 0

        for sample in prompts:
            response = provider.complete(
                prompt=sample.input_text,
                model_name=run.model_name,
                expected_output=sample.expected_output,
            )
            scores = score_response(sample.expected_output, response.text)
            decision = evaluate_policy(
                scores=scores,
                min_quality_score=policy.min_quality_score,
                max_hallucination_score=policy.max_hallucination_score,
                max_toxicity_score=policy.max_toxicity_score,
                block_on_fail=policy.block_on_fail,
            )

            blocked_count += int(decision.blocked)
            quality_scores.append(scores.quality_score)
            hallucination_scores.append(scores.hallucination_score)
            toxicity_scores.append(scores.toxicity_score)

            db.add(
                EvaluationResult(
                    run_id=run.id,
                    prompt_sample_id=sample.id,
                    response_text=response.text,
                    quality_score=scores.quality_score,
                    hallucination_score=scores.hallucination_score,
                    toxicity_score=scores.toxicity_score,
                    blocked=decision.blocked,
                    block_reasons=decision.reasons,
                    latency_ms=response.latency_ms,
                )
            )
            db.commit()

        run.total_samples = len(prompts)
        run.blocked_count = blocked_count
        run.avg_quality_score = round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else None
        run.avg_hallucination_score = round(sum(hallucination_scores) / len(hallucination_scores), 4) if hallucination_scores else None
        run.avg_toxicity_score = round(sum(toxicity_scores) / len(toxicity_scores), 4) if toxicity_scores else None
        run.pass_rate = round((len(prompts) - blocked_count) / len(prompts), 4) if prompts else None
        run.status = "completed"
        run.completed_at = dt.datetime.utcnow()
        db.commit()

        logger.info("evaluation_completed", run_id=run_id, total_samples=run.total_samples, blocked_count=blocked_count)
        return {"run_id": run_id, "status": run.status}
    except Exception as exc:
        logger.exception("evaluation_failed", run_id=run_id, error=str(exc))
        if run:
            run.status = "failed"
            db.commit()
        celery_app.backend.store_result(run_id, {"error": str(exc)}, state=states.FAILURE)
        raise Ignore()
    finally:
        db.close()
