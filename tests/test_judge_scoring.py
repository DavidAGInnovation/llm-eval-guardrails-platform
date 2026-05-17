from app.services.judge_scoring import _extract_first_json_object


def test_extract_first_json_object_from_plain_json() -> None:
    payload = _extract_first_json_object('{"quality_score":0.9,"hallucination_score":0.1,"toxicity_score":0.0}')
    assert payload["quality_score"] == 0.9


def test_extract_first_json_object_from_wrapped_text() -> None:
    payload = _extract_first_json_object(
        "Result:\n```json\n{\"quality_score\":0.88,\"hallucination_score\":0.12,\"toxicity_score\":0.0}\n```"
    )
    assert payload["hallucination_score"] == 0.12
