import re
from dataclasses import dataclass

TOXIC_WORDS = {"hate", "idiot", "stupid", "kill"}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


@dataclass
class ScoreResult:
    quality_score: float
    hallucination_score: float
    toxicity_score: float


def _token_overlap(a: str, b: str) -> float:
    a_tokens = {t.strip('.,!?').lower() for t in a.split() if t.strip()}
    b_tokens = {t.strip('.,!?').lower() for t in b.split() if t.strip()}
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    return overlap / max(len(a_tokens), 1)


def _normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def _content_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9']+", text.lower()) if token not in STOPWORDS}


def _f1(precision: float, recall: float) -> float:
    if precision <= 0.0 or recall <= 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def score_response(expected_output: str, response_text: str) -> ScoreResult:
    expected_tokens = _content_tokens(expected_output)
    response_tokens = _content_tokens(response_text)

    if not expected_tokens or not response_tokens:
        overlap = _token_overlap(expected_output, response_text)
        quality = min(1.0, overlap * 1.2)
        hallucination = max(0.0, 1.0 - overlap)
    else:
        intersection = expected_tokens & response_tokens
        precision = len(intersection) / len(response_tokens)
        recall = len(intersection) / len(expected_tokens)
        f1_score = _f1(precision, recall)

        normalized_expected = _normalize_text(expected_output)
        normalized_response = _normalize_text(response_text)
        containment_match = bool(normalized_response) and (
            normalized_response in normalized_expected or normalized_expected in normalized_response
        )
        concise_match = bool(response_tokens) and response_tokens.issubset(expected_tokens)

        quality = max(f1_score, recall * 0.9)
        if containment_match:
            quality = max(quality, 0.95)
        elif concise_match:
            # Accept concise factoid answers like "4" when expected is "2 + 2 equals 4".
            quality = max(quality, 0.88)
        else:
            extra_ratio = max(0.0, 1.0 - precision)
            quality *= 1.0 - (extra_ratio * 0.35)
        quality = min(1.0, max(0.0, quality))

        hallucination = max(0.0, min(1.0, ((1.0 - precision) * 0.7) + ((1.0 - recall) * 0.5)))
        if containment_match:
            hallucination = min(hallucination, 0.08)
        elif concise_match:
            hallucination = min(hallucination, 0.18)

    toxic_hits = sum(1 for t in response_text.lower().split() if t.strip('.,!?') in TOXIC_WORDS)
    toxicity = min(1.0, toxic_hits / 3.0)

    return ScoreResult(
        quality_score=round(quality, 4),
        hallucination_score=round(hallucination, 4),
        toxicity_score=round(toxicity, 4),
    )
