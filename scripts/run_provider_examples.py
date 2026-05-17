#!/usr/bin/env python3
"""Run evaluation examples against configured providers/models.

Usage:
  OPENAI_API_KEY=... python scripts/run_provider_examples.py --provider openai --models gpt-4o-mini,gpt-4.1-mini

Notes:
- Uses OPENAI_BASE_URL for OpenAI-compatible APIs (OpenAI, OpenRouter, etc.).
- Defaults to a local SQLite DB unless DATABASE_URL is already set.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run provider examples and print evaluation summaries")
    parser.add_argument("--provider", default="openai", help="Provider name (openai or mock)")
    parser.add_argument(
        "--models",
        default="gpt-4o-mini",
        help="Comma-separated model names (e.g. gpt-4o-mini,gpt-4.1-mini)",
    )
    parser.add_argument(
        "--db-url",
        default="",
        help="Database URL override (defaults to DATABASE_URL or sqlite:///./provider_examples.db)",
    )
    parser.add_argument(
        "--scenario",
        default="baseline",
        choices=["baseline", "challenge"],
        help="Prompt suite to run",
    )
    parser.add_argument(
        "--policy-profile",
        default="standard",
        choices=["standard", "strict", "very_strict"],
        help="Guardrail threshold profile",
    )
    return parser.parse_args()


@dataclass
class ExamplePrompt:
    input_text: str
    expected_output: str
    metadata_json: dict


def build_examples(scenario: str) -> list[ExamplePrompt]:
    if scenario == "challenge":
        return [
            ExamplePrompt(
                input_text="Answer with exactly one token: What is 17 * 19?",
                expected_output="323",
                metadata_json={"domain": "math", "difficulty": "format_strict"},
            ),
            ExamplePrompt(
                input_text="Return only the ISO date (YYYY-MM-DD) of the Apollo 11 Moon landing.",
                expected_output="1969-07-20",
                metadata_json={"domain": "history", "difficulty": "factoid"},
            ),
            ExamplePrompt(
                input_text="Return exactly two words: the default HTTPS port.",
                expected_output="port 443",
                metadata_json={"domain": "networking", "difficulty": "format_strict"},
            ),
            ExamplePrompt(
                input_text=(
                    "Name the RFC that defines HTTP/1.1 messaging after RFC 7230 obsolescence. "
                    "Reply only with the RFC number, like RFC XXXX."
                ),
                expected_output="RFC 9112",
                metadata_json={"domain": "protocols", "difficulty": "niche_fact"},
            ),
            ExamplePrompt(
                input_text=(
                    "Reply only with the RFC number for HTTP/1.1 message syntax and routing "
                    "(the spec that obsoleted RFC 7230)."
                ),
                expected_output="RFC 9112",
                metadata_json={"domain": "protocols", "difficulty": "niche_fact_repeat"},
            ),
            ExamplePrompt(
                input_text=(
                    "In one sentence, explain overfitting and include the exact phrase 'unseen data'."
                ),
                expected_output="Overfitting fits training noise and hurts performance on unseen data.",
                metadata_json={"domain": "ml", "difficulty": "constraint"},
            ),
            ExamplePrompt(
                input_text=(
                    "Respond in valid minified JSON only with keys city and country for Paris. "
                    "No markdown."
                ),
                expected_output='{"city":"Paris","country":"France"}',
                metadata_json={"domain": "formatting", "difficulty": "json_strict"},
            ),
            ExamplePrompt(
                input_text=(
                    "Give exactly three comma-separated countries in South America in alphabetical order."
                ),
                expected_output="Argentina, Brazil, Chile",
                metadata_json={"domain": "geography", "difficulty": "list_precision"},
            ),
            ExamplePrompt(
                input_text="What year did the first iPhone launch? Return only the year.",
                expected_output="2007",
                metadata_json={"domain": "history", "difficulty": "factoid"},
            ),
        ]

    return [
        ExamplePrompt(
            input_text="What is the capital of France?",
            expected_output="Paris is the capital of France.",
            metadata_json={"domain": "geography"},
        ),
        ExamplePrompt(
            input_text="2 + 2?",
            expected_output="2 + 2 equals 4.",
            metadata_json={"domain": "math"},
        ),
        ExamplePrompt(
            input_text="Name one risk of overfitting in machine learning.",
            expected_output="Overfitting can reduce performance on unseen data.",
            metadata_json={"domain": "ml"},
        ),
        ExamplePrompt(
            input_text="Explain CORS in one sentence.",
            expected_output="CORS is a browser security policy controlling cross-origin requests.",
            metadata_json={"domain": "web"},
        ),
        ExamplePrompt(
            input_text="What year did the first iPhone launch?",
            expected_output="The first iPhone launched in 2007.",
            metadata_json={"domain": "history"},
        ),
    ]


def build_policy(profile: str) -> dict[str, float | bool]:
    if profile == "strict":
        return {
            "min_quality_score": 0.88,
            "max_hallucination_score": 0.18,
            "max_toxicity_score": 0.2,
            "block_on_fail": True,
        }
    if profile == "very_strict":
        return {
            "min_quality_score": 0.93,
            "max_hallucination_score": 0.10,
            "max_toxicity_score": 0.15,
            "block_on_fail": True,
        }
    return {
        "min_quality_score": 0.6,
        "max_hallucination_score": 0.45,
        "max_toxicity_score": 0.2,
        "block_on_fail": True,
    }


def main() -> int:
    args = parse_args()

    if args.db_url:
        os.environ["DATABASE_URL"] = args.db_url
    else:
        os.environ.setdefault("DATABASE_URL", "sqlite:///./provider_examples.db")

    if args.provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is required for provider=openai")
        return 1

    from app.db.base import Base
    from app.db.models import (
        Dataset,
        EvaluationResult,
        EvaluationRun,
        GuardrailPolicy,
        PromptSample,
    )
    from app.db.session import SessionLocal, engine
    from app.services.regressions import verdict_from_deltas
    from app.worker.tasks import run_evaluation

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        policy_cfg = build_policy(args.policy_profile)
        policy = GuardrailPolicy(
            name=f"real-provider-policy-{uuid.uuid4().hex[:8]}",
            min_quality_score=float(policy_cfg["min_quality_score"]),
            max_hallucination_score=float(policy_cfg["max_hallucination_score"]),
            max_toxicity_score=float(policy_cfg["max_toxicity_score"]),
            block_on_fail=bool(policy_cfg["block_on_fail"]),
            active=True,
        )
        db.add(policy)
        db.flush()

        dataset = Dataset(
            name=f"real-provider-dataset-{uuid.uuid4().hex[:8]}",
            description=f"Curated examples for provider benchmarking ({args.scenario}, {args.policy_profile})",
        )
        db.add(dataset)
        db.flush()

        for prompt in build_examples(args.scenario):
            db.add(
                PromptSample(
                    dataset_id=dataset.id,
                    input_text=prompt.input_text,
                    expected_output=prompt.expected_output,
                    metadata_json=prompt.metadata_json,
                )
            )
        db.commit()

        models = [m.strip() for m in args.models.split(",") if m.strip()]
        run_ids: list[str] = []

        print(
            f"Running provider='{args.provider}' scenario='{args.scenario}' "
            f"policy='{args.policy_profile}' for models: {', '.join(models)}"
        )
        for model in models:
            run = EvaluationRun(
                dataset_id=dataset.id,
                policy_id=policy.id,
                provider=args.provider,
                model_name=model,
                status="queued",
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run_ids.append(str(run.id))

            run_evaluation(str(run.id))
            db.expire_all()
            updated = db.get(EvaluationRun, run.id)
            if updated is None:
                print(f"{model}: run missing")
                continue

            print(
                f"- {model}: status={updated.status} pass_rate={updated.pass_rate} "
                f"quality={updated.avg_quality_score} hallucination={updated.avg_hallucination_score} "
                f"toxicity={updated.avg_toxicity_score} blocked={updated.blocked_count}/{updated.total_samples}"
            )

            rows = (
                db.query(EvaluationResult)
                .filter(EvaluationResult.run_id == updated.id)
                .order_by(EvaluationResult.created_at.asc())
                .limit(2)
                .all()
            )
            for row in rows:
                snippet = row.response_text[:120].replace("\n", " ")
                print(
                    f"  sample blocked={row.blocked} q={row.quality_score} h={row.hallucination_score} "
                    f"t={row.toxicity_score} text='{snippet}'"
                )

        if len(run_ids) >= 2:
            baseline = db.get(EvaluationRun, uuid.UUID(run_ids[0]))
            candidate = db.get(EvaluationRun, uuid.UUID(run_ids[1]))
            if baseline and candidate:
                quality_delta = round((candidate.avg_quality_score or 0.0) - (baseline.avg_quality_score or 0.0), 4)
                hallucination_delta = round((candidate.avg_hallucination_score or 0.0) - (baseline.avg_hallucination_score or 0.0), 4)
                toxicity_delta = round((candidate.avg_toxicity_score or 0.0) - (baseline.avg_toxicity_score or 0.0), 4)
                pass_rate_delta = round((candidate.pass_rate or 0.0) - (baseline.pass_rate or 0.0), 4)
                verdict = verdict_from_deltas(
                    quality_delta=quality_delta,
                    hallucination_delta=hallucination_delta,
                    toxicity_delta=toxicity_delta,
                    pass_rate_delta=pass_rate_delta,
                )
                print(
                    "Comparison (model[1] vs model[0]): "
                    f"quality_delta={quality_delta}, hallucination_delta={hallucination_delta}, "
                    f"toxicity_delta={toxicity_delta}, pass_rate_delta={pass_rate_delta}, verdict={verdict}"
                )

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
