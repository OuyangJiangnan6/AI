"""Transparent rule-based planner for a synthetic shopping catalog."""
from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
CATEGORY_ALIASES = {
    "耳机": ("耳机", "降噪耳机", "听歌"),
    "键盘": ("键盘", "打字"),
    "鼠标": ("鼠标",),
    "显示器": ("显示器", "屏幕"),
    "背包": ("背包", "书包", "双肩包"),
}
FEATURE_ALIASES = {
    "降噪": ("降噪", "嘈杂", "地铁"),
    "无线": ("无线", "蓝牙"),
    "续航": ("续航", "电池"),
    "舒适": ("舒适", "久戴", "久坐", "人体工学"),
    "通勤": ("通勤",),
    "便携": ("便携", "轻便", "出差"),
    "性价比": ("性价比", "便宜", "划算"),
    "办公": ("办公", "学习", "写代码"),
    "游戏": ("游戏", "电竞"),
    "静音": ("静音", "安静", "图书馆"),
    "机械": ("机械", "段落感"),
    "麦克风": ("麦克风", "会议", "通话"),
    "音质": ("音质", "音乐"),
    "头戴": ("头戴",),
    "入耳": ("入耳",),
    "有线": ("有线",),
}
NEGATION = re.compile(r"(?:不要|不想要|不需要|避免|排除|别选|不买)\s*([一-鿿]{1,8})")
BUDGET_PATTERNS = (
    re.compile(r"预算(?:是|为|调整到|改为|改成)?\s*[¥￥]?\s*(\d{2,6})"),
    re.compile(r"[¥￥]\s*(\d{2,6})"),
    re.compile(r"(\d{2,6})\s*元?\s*(?:以内|以下|之内|不超过|封顶)"),
)

@dataclass
class ShoppingTask:
    categories: list[str] = field(default_factory=list)
    budget: int | None = None
    preferences: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    turns: int = 0


def _mentioned_categories(text: str) -> list[str]:
    return [category for category, aliases in CATEGORY_ALIASES.items()
            if any(alias in text for alias in aliases)]


def _mentioned_features(text: str) -> tuple[list[str], list[str]]:
    exclusions = []
    for match in NEGATION.finditer(text):
        phrase = match.group(1)
        for feature, aliases in FEATURE_ALIASES.items():
            if any(alias in phrase or phrase in alias for alias in aliases):
                exclusions.append(feature)
    preferences = []
    for feature, aliases in FEATURE_ALIASES.items():
        for alias in aliases:
            for found in re.finditer(re.escape(alias), text):
                prefix = text[max(0, found.start()-5):found.start()]
                if not re.search(r"(?:不要|不想要|不需要|避免|排除|别选|不买)$", prefix):
                    if feature not in exclusions:
                        preferences.append(feature)
    return list(dict.fromkeys(preferences)), list(dict.fromkeys(exclusions))


def update_task(task: ShoppingTask, text: str) -> ShoppingTask:
    """Apply a user turn while retaining earlier constraints."""
    text = text.strip()
    categories = list(task.categories)
    mentioned = _mentioned_categories(text)
    if mentioned:
        if any(word in text for word in ("换成", "只要", "改成")):
            categories = mentioned
        else:
            categories = list(dict.fromkeys(categories + mentioned))
    budget = task.budget
    for pattern in BUDGET_PATTERNS:
        match = pattern.search(text)
        if match:
            budget = int(match.group(1))
            break
    preferences, exclusions = _mentioned_features(text)
    retained_preferences = [f for f in task.preferences if f not in exclusions]
    retained_exclusions = [f for f in task.exclusions if f not in preferences]
    return ShoppingTask(
        categories=categories,
        budget=budget,
        preferences=list(dict.fromkeys(retained_preferences + preferences)),
        exclusions=list(dict.fromkeys(retained_exclusions + exclusions)),
        turns=task.turns + 1,
    )


def recommend(task: ShoppingTask, limit: int = 3) -> dict:
    """Return feasible bundles, ranked by preference coverage and price."""
    if not task.categories:
        return {"status": "need_category", "message": "想先买哪类商品？可选耳机、键盘、鼠标、显示器或背包。", "bundles": []}
    if task.budget is None:
        return {"status": "need_budget", "message": "总预算是多少元？例如：预算 1500 元。", "bundles": []}
    groups = []
    for category in task.categories:
        group = [item for item in CATALOG
                 if item["category"] == category
                 and not set(item["features"]).intersection(task.exclusions)]
        if not group:
            return {"status": "no_match", "message": f"{category}没有满足排除条件的商品，请放宽条件。", "bundles": []}
        groups.append(group)
    bundles = []
    for combo in itertools.product(*groups):
        total = sum(item["price"] for item in combo)
        if total > task.budget:
            continue
        matched = sorted(set(task.preferences).intersection(
            set().union(*(set(item["features"]) for item in combo))))
        missing = sorted(set(task.preferences) - set(matched))
        # Coverage dominates price; price resolves otherwise similar options.
        score = len(matched) * 100 - len(missing) * 30 - total / max(task.budget, 1) * 8
        bundles.append({
            "items": list(combo),
            "total": total,
            "remaining": task.budget - total,
            "matched": matched,
            "missing": missing,
            "score": round(score, 2),
        })
    bundles.sort(key=lambda x: (-x["score"], x["total"], [i["id"] for i in x["items"]]))
    if not bundles:
        minimum = sum(min(item["price"] for item in group) for group in groups)
        return {"status": "over_budget", "message": f"当前约束下，最低组合需 ¥{minimum}，比预算多 ¥{minimum-task.budget}。可提高预算或减少品类。", "minimum": minimum, "bundles": []}
    return {
        "status": "ok",
        "message": f"找到 {len(bundles)} 组预算内方案；优先满足偏好，再比较价格。",
        "bundles": bundles[:limit],
        "candidate_count": len(bundles),
    }
