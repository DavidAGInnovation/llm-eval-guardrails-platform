def verdict_from_deltas(
    quality_delta: float,
    hallucination_delta: float,
    toxicity_delta: float,
    pass_rate_delta: float,
) -> str:
    score = 0
    if quality_delta >= 0:
        score += 1
    if hallucination_delta <= 0:
        score += 1
    if toxicity_delta <= 0:
        score += 1
    if pass_rate_delta >= 0:
        score += 1

    if score >= 4:
        return "improved"
    if score >= 2:
        return "neutral"
    return "regressed"
