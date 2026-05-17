import pytest
from pydantic import ValidationError

from app.db.schemas import PolicyCreate


def test_policy_thresholds_require_zero_to_one_range() -> None:
    with pytest.raises(ValidationError):
        PolicyCreate(name="bad-policy", min_quality_score=1.1)

    with pytest.raises(ValidationError):
        PolicyCreate(name="bad-policy-2", max_hallucination_score=-0.1)

    with pytest.raises(ValidationError):
        PolicyCreate(name="bad-policy-3", max_toxicity_score=1.2)


def test_policy_thresholds_accept_boundary_values() -> None:
    policy = PolicyCreate(
        name="boundary-policy",
        min_quality_score=0.0,
        max_hallucination_score=1.0,
        max_toxicity_score=1.0,
    )

    assert policy.min_quality_score == 0.0
    assert policy.max_hallucination_score == 1.0
    assert policy.max_toxicity_score == 1.0
