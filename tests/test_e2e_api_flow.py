import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

TEST_DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql+psycopg://postgres:postgres@localhost:5432/llm_eval"
)


def test_api_end_to_end_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    from app.core.config import get_settings

    get_settings.cache_clear()

    try:
        from app.api.routes import runs as runs_routes
        from app.db.base import Base
        from app.db.session import engine
        from app.main import app
        from app.worker.tasks import run_evaluation
    except ImportError as exc:
        pytest.skip(f"Integration test dependencies unavailable: {exc}")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.skip("Postgres is not reachable for end-to-end API test")

    # Keep the database isolated for the integration test run.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def _run_inline(run_id: str):
        run_evaluation(run_id)

        class DummyResult:
            id = run_id

        return DummyResult()

    monkeypatch.setattr(runs_routes.run_evaluation, "delay", _run_inline)

    try:
        with TestClient(app) as client:
            missing_results = client.get(f"/runs/{uuid.uuid4()}/results")
            assert missing_results.status_code == 404

            seeded = client.post("/policies/seed-default")
            assert seeded.status_code == 200
            policy_id = seeded.json()["id"]

            dataset_name = f"qa-baseline-{uuid.uuid4().hex[:8]}"
            dataset_resp = client.post(
                "/datasets",
                json={
                    "name": dataset_name,
                    "description": "integration test dataset",
                    "prompts": [
                        {
                            "input_text": "What is the capital of France?",
                            "expected_output": "Paris is the capital of France",
                            "metadata_json": {"domain": "geography"},
                        },
                        {
                            "input_text": "2 + 2?",
                            "expected_output": "2 + 2 equals 4",
                            "metadata_json": {"domain": "math"},
                        },
                    ],
                },
            )
            assert dataset_resp.status_code == 200
            dataset_id = dataset_resp.json()["id"]

            run_resp = client.post(
                "/runs",
                json={
                    "dataset_id": dataset_id,
                    "policy_id": policy_id,
                    "provider": "mock",
                    "model_name": "mock-safe",
                },
            )
            assert run_resp.status_code == 200
            baseline_run_id = run_resp.json()["id"]

            run_detail = client.get(f"/runs/{baseline_run_id}")
            assert run_detail.status_code == 200
            assert run_detail.json()["status"] == "completed"

            results_resp = client.get(f"/runs/{baseline_run_id}/results")
            assert results_resp.status_code == 200
            assert len(results_resp.json()) == 2

            candidate_resp = client.post(
                "/runs",
                json={
                    "dataset_id": dataset_id,
                    "policy_id": policy_id,
                    "provider": "mock",
                    "model_name": "mock-risky",
                },
            )
            assert candidate_resp.status_code == 200
            candidate_run_id = candidate_resp.json()["id"]

            compare_resp = client.post(
                f"/runs/{candidate_run_id}/compare",
                json={"baseline_run_id": baseline_run_id},
            )
            assert compare_resp.status_code == 200
            payload = compare_resp.json()
            assert payload["candidate_run_id"] == candidate_run_id
            assert payload["baseline_run_id"] == baseline_run_id
            assert payload["verdict"] in {"improved", "neutral", "regressed"}
    finally:
        Base.metadata.drop_all(bind=engine)
        get_settings.cache_clear()
