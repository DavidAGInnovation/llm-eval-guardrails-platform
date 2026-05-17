from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PromptSampleIn(BaseModel):
    input_text: str
    expected_output: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    prompts: list[PromptSampleIn]


class DatasetOut(BaseModel):
    id: UUID
    name: str
    description: str | None


class PolicyCreate(BaseModel):
    name: str
    min_quality_score: float = Field(default=0.70, ge=0.0, le=1.0)
    max_hallucination_score: float = Field(default=0.35, ge=0.0, le=1.0)
    max_toxicity_score: float = Field(default=0.20, ge=0.0, le=1.0)
    block_on_fail: bool = True
    active: bool = True


class PolicyOut(BaseModel):
    id: UUID
    name: str
    min_quality_score: float
    max_hallucination_score: float
    max_toxicity_score: float
    block_on_fail: bool
    active: bool


class RunCreate(BaseModel):
    dataset_id: UUID
    policy_id: UUID | None = None
    provider: str = "mock"
    model_name: str = "mock-safe"


class RunOut(BaseModel):
    id: UUID
    status: str
    provider: str
    model_name: str
    dataset_id: UUID
    policy_id: UUID
    total_samples: int
    blocked_count: int
    avg_quality_score: float | None = None
    avg_hallucination_score: float | None = None
    avg_toxicity_score: float | None = None
    pass_rate: float | None


class RegressionCompareIn(BaseModel):
    baseline_run_id: UUID


class RegressionCompareOut(BaseModel):
    candidate_run_id: UUID
    baseline_run_id: UUID
    quality_delta: float
    hallucination_delta: float
    toxicity_delta: float
    pass_rate_delta: float
    blocked_delta: int
    verdict: str
