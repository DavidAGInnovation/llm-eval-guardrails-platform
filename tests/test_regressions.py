from app.services.regressions import verdict_from_deltas


def test_verdict_improved():
    verdict = verdict_from_deltas(0.1, -0.1, -0.1, 0.05)
    assert verdict == "improved"


def test_verdict_regressed():
    verdict = verdict_from_deltas(-0.2, 0.2, 0.1, -0.3)
    assert verdict == "regressed"
