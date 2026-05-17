from dataclasses import dataclass

from app.services.scoring import ScoreResult


@dataclass
class GuardrailDecision:
    blocked: bool
    reasons: list[str]


def evaluate_policy(
    scores: ScoreResult,
    min_quality_score: float,
    max_hallucination_score: float,
    max_toxicity_score: float,
    block_on_fail: bool,
) -> GuardrailDecision:
    reasons: list[str] = []

    if scores.quality_score < min_quality_score:
        reasons.append(f"quality<{min_quality_score}")
    if scores.hallucination_score > max_hallucination_score:
        reasons.append(f"hallucination>{max_hallucination_score}")
    if scores.toxicity_score > max_toxicity_score:
        reasons.append(f"toxicity>{max_toxicity_score}")

    blocked = block_on_fail and len(reasons) > 0
    return GuardrailDecision(blocked=blocked, reasons=reasons)
