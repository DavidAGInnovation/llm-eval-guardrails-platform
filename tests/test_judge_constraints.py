from app.services.judge_scoring import _apply_constraint_penalty, _constraint_violations


def test_constraint_violations_detect_two_words_requirement() -> None:
    prompt = "Return exactly two words: the default HTTPS port."
    assert _constraint_violations(prompt, "443") >= 1
    assert _constraint_violations(prompt, "port 443") == 0


def test_constraint_penalty_caps_scores_on_violation() -> None:
    prompt = "Return only the ISO date (YYYY-MM-DD) of the Apollo 11 Moon landing."
    q, h = _apply_constraint_penalty(quality_score=0.98, hallucination_score=0.02, prompt=prompt, response_text="July 20, 1969")
    assert q <= 0.55
    assert h >= 0.55
