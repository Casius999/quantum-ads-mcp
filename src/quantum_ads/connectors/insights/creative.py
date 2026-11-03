"""Creative studio: Gemini prompts that return JSON, and strict validation of what comes back.

The model is asked for a JSON object; whatever it returns is parsed leniently (code fences,
prose around the object) and then filtered hard: Google Ads character limits, duplicates and
empty lines are removed, so the output can be passed straight to the campaign builders.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

SEARCH_LIMITS = {"headlines": (15, 30), "descriptions": (4, 90)}
PMAX_LIMITS = {"headlines": (15, 30), "long_headlines": (5, 90), "descriptions": (5, 90)}


class CreativeError(ValueError):
    """The model's output could not be turned into usable ad copy."""


def search_ads_prompt(product: str, audience: str, language: str, final_url: str | None) -> str:
    landing = f" Landing page: {final_url}." if final_url else ""
    return (
        f"You write Google responsive search ads in {language}. Product: {product}. "
        f"Audience: {audience}.{landing} Return ONLY a JSON object "
        '{"headlines": [15 strings, each at most 30 characters], '
        '"descriptions": [4 strings, each at most 90 characters]}. Vary benefits, proof, '
        "offer and call to action; include the main keyword in several headlines; no "
        "exclamation marks in headlines; no duplicate meaning."
    )


def pmax_prompt(product: str, audience: str, language: str) -> str:
    return (
        f"You write Google Performance Max text assets in {language}. Product: {product}. "
        f"Audience: {audience}. Return ONLY a JSON object "
        '{"headlines": [15 strings <= 30 chars], "long_headlines": [5 strings <= 90 chars], '
        '"descriptions": [5 strings <= 90 chars, at least one <= 60 chars], '
        '"image_prompts": [3 photographic scene descriptions without any text in the image]}.'
    )


def _loads_lenient(raw: str) -> Any:
    """``json.loads``, then once more after fixing the slips small models make.

    Repairs missing commas between string items on separate lines and trailing commas.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first:
        repaired = re.sub(r'"(\s*\n\s*)"', r'",\1"', raw)
        repaired = re.sub(r",(\s*[\]}])", r"\1", repaired)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            raise CreativeError(f"model output is not valid JSON: {first.msg}") from first


def repair_prompt(payload: dict[str, Any], limits: dict[str, tuple[int, int]]) -> str:
    """A follow-up prompt naming every over-long item, asking for a compliant rewrite."""
    problems = []
    for field, (count, chars) in limits.items():
        raw = payload.get(field) or []
        for value in raw if isinstance(raw, list) else [raw]:
            text = " ".join(str(value).split())
            if len(text) > chars:
                problems.append(f'{field}: "{text}" has {len(text)} characters (max {chars})')
        problems.append(f"{field}: return {count} items, each at most {chars} characters")
    return (
        "Your previous answer broke Google Ads limits. Count every character, spaces included. "
        "Problems:\n- "
        + "\n- ".join(problems)
        + "\nPrevious answer:\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\nRewrite it. Return ONLY the corrected JSON object with the same keys; shorten, "
        "do not drop items."
    )


def parse_json_object(text: str) -> dict[str, Any]:
    """The first JSON object in ``text`` (tolerates code fences and surrounding prose)."""
    cleaned = re.sub(r"```(?:json)?", "", text)
    start = cleaned.find("{")
    if start < 0:
        raise CreativeError("model output has no JSON object")
    depth = 0
    for index in range(start, len(cleaned)):
        if cleaned[index] == "{":
            depth += 1
        elif cleaned[index] == "}":
            depth -= 1
            if depth == 0:
                value = _loads_lenient(cleaned[start : index + 1])
                if not isinstance(value, dict):
                    raise CreativeError("model output is not a JSON object")
                return value
    raise CreativeError("model output has an unterminated JSON object")


def clean_lines(values: Sequence[object], *, max_count: int, max_chars: int) -> list[str]:
    """Strip, drop empty/over-long lines and case-insensitive duplicates, cap the count."""
    seen: set[str] = set()
    kept: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        if not text or len(text) > max_chars or text.lower() in seen:
            continue
        seen.add(text.lower())
        kept.append(text)
        if len(kept) == max_count:
            break
    return kept


def validated(
    payload: dict[str, Any], limits: dict[str, tuple[int, int]], minimums: dict[str, int]
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for field, (count, chars) in limits.items():
        raw = payload.get(field) or []
        out[field] = clean_lines(
            raw if isinstance(raw, list) else [raw], max_count=count, max_chars=chars
        )
        if len(out[field]) < minimums.get(field, 1):
            raise CreativeError(
                f"{field}: only {len(out[field])} usable lines, need {minimums.get(field, 1)}"
            )
    return out
