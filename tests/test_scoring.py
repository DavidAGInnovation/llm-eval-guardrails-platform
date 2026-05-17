from app.services.scoring import score_response


def test_scoring_high_overlap_has_high_quality():
    result = score_response(
        expected_output="Paris is the capital of France",
        response_text="Paris is the capital of France",
    )
    assert result.quality_score >= 0.95
    assert result.hallucination_score <= 0.1


def test_scoring_toxicity_detects_bad_words():
    result = score_response(
        expected_output="Neutral response",
        response_text="You are stupid and I hate this",
    )
    assert result.toxicity_score > 0.0
