"""Optional model-assisted intent extraction for OpenAI-compatible chat endpoints."""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict
from engine import CATEGORY_ALIASES, FEATURE_ALIASES, ShoppingTask, update_task


def configured() -> bool:
    return all(os.getenv(k) for k in ("SHOPPING_AI_BASE_URL", "SHOPPING_AI_API_KEY", "SHOPPING_AI_MODEL"))


def _request_model(task: ShoppingTask, text: str) -> dict:
    url = os.environ["SHOPPING_AI_BASE_URL"].rstrip("/") + "/chat/completions"
    system = (
        "You are a shopping intent parser. Return ONLY one JSON object with keys "
        "categories, budget, preferences, exclusions. These describe the COMPLETE "
        "task state after the latest user message. Preserve prior constraints unless "
        "the user explicitly changes them. Categories must be from: "
        + ", ".join(CATEGORY_ALIASES) + ". Features must be from: "
        + ", ".join(FEATURE_ALIASES) + ". Budget is integer yuan or null. "
        "Do not invent product facts. Do not add any prose."
    )
    payload = {
        "model": os.environ["SHOPPING_AI_MODEL"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(
                {"previous_task": asdict(task), "latest_message": text},
                ensure_ascii=False)},
        ],
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.environ["SHOPPING_AI_API_KEY"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        body = json.load(response)
    content = body["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(content)


def _valid_list(value: object, allowed: set[str]) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result = [x for x in value if isinstance(x, str) and x in allowed]
    return list(dict.fromkeys(result))


def merge_model_result(previous: ShoppingTask, text: str, raw: dict) -> ShoppingTask:
    """Validate model output and retain explicit local constraints."""
    fallback = update_task(previous, text)
    if not isinstance(raw, dict):
        return fallback
    categories = _valid_list(raw.get("categories"), set(CATEGORY_ALIASES))
    preferences = _valid_list(raw.get("preferences"), set(FEATURE_ALIASES))
    exclusions = _valid_list(raw.get("exclusions"), set(FEATURE_ALIASES))
    budget = raw.get("budget")
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 1000000:
        budget = fallback.budget
    # Values explicitly recognized in the user's message always win.
    explicit = update_task(ShoppingTask(), text)
    if explicit.budget is not None:
        budget = explicit.budget
    categories = categories if categories is not None else fallback.categories
    categories = list(dict.fromkeys(categories + explicit.categories))
    preferences = preferences if preferences is not None else fallback.preferences
    exclusions = exclusions if exclusions is not None else fallback.exclusions
    exclusions = list(dict.fromkeys(exclusions + explicit.exclusions))
    preferences = [x for x in dict.fromkeys(preferences + explicit.preferences)
                   if x not in exclusions]
    return ShoppingTask(categories, budget, preferences, exclusions, fallback.turns)


def interpret(task: ShoppingTask, text: str) -> ShoppingTask:
    return merge_model_result(task, text, _request_model(task, text))
