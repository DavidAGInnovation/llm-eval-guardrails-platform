from app.services.guardrails import evaluate_policy
from app.services.scoring import ScoreResult


def test_guardrail_blocks_when_policy_violated():
    decision = evaluate_policy(
        scores=ScoreResult(quality_score=0.4, hallucination_score=0.9, toxicity_score=0.0),
        min_quality_score=0.7,
        max_hallucination_score=0.3,
        max_toxicity_score=0.2,
        block_on_fail=True,
    )
    assert decision.blocked is True
    assert len(decision.reasons) >= 1


def test_guardrail_warn_only_mode():
    decision = evaluate_policy(
        scores=ScoreResult(quality_score=0.4, hallucination_score=0.9, toxicity_score=0.0),
        min_quality_score=0.7,
        max_hallucination_score=0.3,
        max_toxicity_score=0.2,
        block_on_fail=False,
    )
    assert decision.blocked is False
    assert len(decision.reasons) >= 1
