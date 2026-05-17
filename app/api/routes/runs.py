from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Dataset, EvaluationResult, EvaluationRun, GuardrailPolicy
from app.db.schemas import RegressionCompareIn, RegressionCompareOut, RunCreate, RunOut
from app.db.session import get_db
from app.services.regressions import verdict_from_deltas
from app.worker.tasks import run_evaluation

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunOut)
def start_run(payload: RunCreate, db: Session = Depends(get_db)) -> RunOut:
    dataset = db.get(Dataset, payload.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    policy_id = payload.policy_id
    if not policy_id:
        settings = get_settings()
        if settings.default_policy_id:
            policy_id = UUID(settings.default_policy_id)
        else:
            policy = db.execute(select(GuardrailPolicy).where(GuardrailPolicy.active.is_(True)).order_by(GuardrailPolicy.created_at.desc())).scalar_one_or_none()
            if not policy:
                raise HTTPException(status_code=400, detail="No active policy found; create one first")
            policy_id = policy.id

    policy = db.get(GuardrailPolicy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    run = EvaluationRun(
        dataset_id=payload.dataset_id,
        policy_id=policy.id,
        provider=payload.provider,
        model_name=payload.model_name,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run_evaluation.delay(str(run.id))

    return RunOut(
        id=run.id,
        status=run.status,
        provider=run.provider,
        model_name=run.model_name,
        dataset_id=run.dataset_id,
        policy_id=run.policy_id,
        total_samples=run.total_samples,
        blocked_count=run.blocked_count,
        pass_rate=run.pass_rate,
    )


@router.get("", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)) -> list[RunOut]:
    rows = db.execute(select(EvaluationRun).order_by(EvaluationRun.created_at.desc())).scalars().all()
    return [
        RunOut(
            id=r.id,
            status=r.status,
            provider=r.provider,
            model_name=r.model_name,
            dataset_id=r.dataset_id,
            policy_id=r.policy_id,
            total_samples=r.total_samples,
            blocked_count=r.blocked_count,
            pass_rate=r.pass_rate,
        )
        for r in rows
    ]


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> RunOut:
    run = db.get(EvaluationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunOut(
        id=run.id,
        status=run.status,
        provider=run.provider,
        model_name=run.model_name,
        dataset_id=run.dataset_id,
        policy_id=run.policy_id,
        total_samples=run.total_samples,
        blocked_count=run.blocked_count,
        pass_rate=run.pass_rate,
    )


@router.get("/{run_id}/results")
def get_run_results(run_id: UUID, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(EvaluationResult).where(EvaluationResult.run_id == run_id).order_by(EvaluationResult.created_at.asc())
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "prompt_sample_id": str(r.prompt_sample_id),
            "response_text": r.response_text,
            "quality_score": r.quality_score,
            "hallucination_score": r.hallucination_score,
            "toxicity_score": r.toxicity_score,
            "blocked": r.blocked,
            "block_reasons": r.block_reasons,
            "latency_ms": r.latency_ms,
        }
        for r in rows
    ]


@router.post("/{run_id}/compare", response_model=RegressionCompareOut)
def compare_run(run_id: UUID, payload: RegressionCompareIn, db: Session = Depends(get_db)) -> RegressionCompareOut:
    candidate = db.get(EvaluationRun, run_id)
    baseline = db.get(EvaluationRun, payload.baseline_run_id)

    if not candidate or not baseline:
        raise HTTPException(status_code=404, detail="Run not found")
    if candidate.status != "completed" or baseline.status != "completed":
        raise HTTPException(status_code=400, detail="Both runs must be completed")

    quality_delta = round((candidate.avg_quality_score or 0.0) - (baseline.avg_quality_score or 0.0), 4)
    hallucination_delta = round((candidate.avg_hallucination_score or 0.0) - (baseline.avg_hallucination_score or 0.0), 4)
    toxicity_delta = round((candidate.avg_toxicity_score or 0.0) - (baseline.avg_toxicity_score or 0.0), 4)
    pass_rate_delta = round((candidate.pass_rate or 0.0) - (baseline.pass_rate or 0.0), 4)
    blocked_delta = candidate.blocked_count - baseline.blocked_count

    verdict = verdict_from_deltas(
        quality_delta=quality_delta,
        hallucination_delta=hallucination_delta,
        toxicity_delta=toxicity_delta,
        pass_rate_delta=pass_rate_delta,
    )

    return RegressionCompareOut(
        candidate_run_id=candidate.id,
        baseline_run_id=baseline.id,
        quality_delta=quality_delta,
        hallucination_delta=hallucination_delta,
        toxicity_delta=toxicity_delta,
        pass_rate_delta=pass_rate_delta,
        blocked_delta=blocked_delta,
        verdict=verdict,
    )
