from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from recipe_api import EdamamClient
from storage import slugify


GOAL_KEYWORDS = {
    "balanced": ["balanced", "weeknight", "simple"],
    "low fat": ["low fat", "light", "grilled", "roasted"],
    "low carb": ["low carb", "keto", "salad", "bowl", "zucchini", "cauliflower"],
    "mediterranean": ["mediterranean", "olive", "feta", "chickpea", "salmon", "tomato"],
    "high protein": ["high protein", "protein", "chicken", "salmon", "turkey", "beef", "lentil"],
    "vegetarian": ["vegetarian", "beans", "lentil", "tofu", "chickpea"],
}


RESTRICTION_RULES = {
    "vegetarian": ["chicken", "turkey", "beef", "pork", "fish", "salmon", "shrimp", "meat"],
    "vegan": ["chicken", "turkey", "beef", "pork", "fish", "salmon", "shrimp", "meat", "egg", "milk", "cheese", "butter", "yogurt", "honey", "feta", "parmesan"],
    "gluten free": ["wheat", "flour", "pasta", "bread", "tortilla", "soy sauce"],
    "dairy free": ["milk", "cheese", "butter", "cream", "yogurt", "feta", "parmesan"],
    "nut free": ["almond", "cashew", "peanut", "walnut", "pecan", "hazelnut", "pistachio"],
    "low sodium": ["soy sauce", "salt", "bouillon", "broth"],
    "pork free": ["pork", "bacon", "ham"],
    "shellfish free": ["shrimp", "crab", "lobster", "shellfish"],
    "halal": ["pork", "ham", "bacon", "wine"],
}


def tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def normalize_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[,\n;]+", value)
    else:
        items = [str(value)]
    return [item.strip().lower() for item in items if str(item).strip()]


def recipe_text(recipe: dict[str, Any]) -> str:
    parts = [recipe.get("name", ""), recipe.get("category", "")]
    parts.extend(recipe.get("tags", []))
    parts.extend(recipe.get("ingredients", []))
    parts.append(str(recipe.get("notes", "")))
    return " ".join(str(part) for part in parts if part)


def recipe_id(recipe: dict[str, Any]) -> str:
    return recipe.get("id") or slugify(recipe.get("name", "recipe"))


def recent_events_for_recipe(history: list[dict[str, Any]], rid: str) -> list[dict[str, Any]]:
    return [event for event in history if event.get("recipe_id") == rid]


def latest_event_date(history: list[dict[str, Any]], rid: str) -> datetime | None:
    dates: list[datetime] = []
    for event in recent_events_for_recipe(history, rid):
        try:
            dates.append(datetime.fromisoformat(str(event.get("made_on"))))
        except ValueError:
            continue
    return max(dates) if dates else None


def average_rating(history: list[dict[str, Any]], rid: str) -> float | None:
    ratings = [float(event.get("rating", 0)) for event in recent_events_for_recipe(history, rid) if event.get("rating") is not None]
    if not ratings:
        return None
    return sum(ratings) / len(ratings)


def blocks_restriction(recipe: dict[str, Any], restriction: str) -> bool:
    restriction = restriction.lower().strip()
    recipe_text_lower = recipe_text(recipe).lower()
    forbidden = RESTRICTION_RULES.get(restriction, [])
    if not forbidden:
        return False
    return any(item in recipe_text_lower for item in forbidden)


def goal_score(recipe: dict[str, Any], goal: str) -> tuple[float, str]:
    goal = goal.lower().strip()
    keywords = GOAL_KEYWORDS.get(goal, GOAL_KEYWORDS["balanced"])
    text = recipe_text(recipe).lower()
    hit_count = sum(1 for keyword in keywords if keyword in text)
    if hit_count:
        return min(1.0, 0.35 + 0.18 * hit_count), f"Fits {goal} goal"
    return 0.15 if goal == "balanced" else 0.05, "Neutral goal fit"


def plan_match_score(recipe: dict[str, Any], tokens: list[str]) -> tuple[float, list[str]]:
    if not tokens:
        return 0.0, []
    text = recipe_text(recipe).lower()
    score = 0.0
    reasons: list[str] = []
    for token in tokens:
        if not token:
            continue
        if token in text:
            score += 0.5
            reasons.append(f"Matches request: {token}")
    if recipe.get("category", "").lower() in tokens:
        score += 0.25
        reasons.append("Matches a requested type")
    return min(score, 1.0), reasons


def variety_bonus(recipe: dict[str, Any], history: list[dict[str, Any]]) -> tuple[float, str]:
    rid = recipe_id(recipe)
    last_used = latest_event_date(history, rid)
    if not last_used:
        return 0.18, "New or infrequent recipe"
    days = (datetime.utcnow() - last_used).days
    if days < 7:
        return -0.30, "Cooked very recently"
    if days < 21:
        return -0.12, "Cooked recently"
    return 0.10, "Enough time since last made"


def enjoyment_score(recipe: dict[str, Any], history: list[dict[str, Any]]) -> tuple[float, str]:
    avg = average_rating(history, recipe_id(recipe))
    if avg is None:
        return 0.12, "No history yet"
    return (avg / 5.0) * 0.8, f"Average rating {avg:.1f}/5"


def should_block(recipe: dict[str, Any], profile: dict[str, Any]) -> tuple[bool, str | None]:
    for restriction in normalize_list(profile.get("dietary_restrictions", [])):
        if blocks_restriction(recipe, restriction):
            return True, f"Blocked by {restriction} restriction"
    for ingredient in normalize_list(profile.get("disliked_ingredients", [])):
        if ingredient and ingredient in recipe_text(recipe).lower():
            return True, f"Contains disliked ingredient: {ingredient}"
    return False, None


def recipe_kind_bonus(recipe: dict[str, Any], preferences: list[str]) -> tuple[float, str]:
    if not preferences:
        return 0.0, ""
    text = recipe_text(recipe).lower()
    hits = [pref for pref in preferences if pref in text]
    if not hits:
        return 0.0, ""
    return min(0.2 + 0.05 * len(hits), 0.35), f"Matches preferences: {', '.join(hits[:3])}"


def normalize_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(recipe)
    normalized["id"] = recipe_id(recipe)
    normalized["name"] = recipe.get("name", "Unnamed recipe")
    normalized["category"] = recipe.get("category", "general")
    normalized["ingredients"] = list(recipe.get("ingredients", []))
    normalized["tags"] = [str(tag).lower() for tag in recipe.get("tags", [])]
    normalized["source"] = recipe.get("source", "manual")
    normalized["nutrition"] = dict(recipe.get("nutrition", {}))
    normalized["url"] = recipe.get("url", "")
    normalized["notes"] = recipe.get("notes", "")
    normalized["sources"] = list(recipe.get("sources", [normalized["source"]]))
    return normalized


def candidate_queries(profile: dict[str, Any], must_include_terms: list[str]) -> list[str]:
    queries = [profile.get("nutrition_goal", "balanced")]
    queries.extend(normalize_list(profile.get("preferred_cuisines", [])))
    queries.extend(must_include_terms)
    seen: set[str] = set()
    ordered: list[str] = []
    for query in queries:
        query = query.strip()
        if query and query.lower() not in seen:
            ordered.append(query)
            seen.add(query.lower())
    return ordered


def build_candidate_pool(store_recipes: list[dict[str, Any]], profile: dict[str, Any], must_include_terms: list[str], include_api: bool = True) -> list[dict[str, Any]]:
    candidates = [normalize_recipe(recipe) for recipe in store_recipes]
    if include_api:
        api = EdamamClient()
        if api.enabled:
            for query in candidate_queries(profile, must_include_terms):
                for result in api.search(query):
                    candidates.append(normalize_recipe(result))
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        rid = recipe_id(candidate)
        if rid not in deduped:
            deduped[rid] = candidate
            continue
        existing = deduped[rid]
        existing_sources = list(existing.get("sources", []))
        for source in candidate.get("sources", []):
            if source not in existing_sources:
                existing_sources.append(source)
        existing["sources"] = existing_sources
        for key in ("ingredients", "tags"):
            merged = list(existing.get(key, []))
            for item in candidate.get(key, []):
                if item not in merged:
                    merged.append(item)
            existing[key] = merged
    return list(deduped.values())


def score_recipe(recipe: dict[str, Any], profile: dict[str, Any], history: list[dict[str, Any]], must_include_terms: list[str]) -> tuple[float, list[str]]:
    blocked, reason = should_block(recipe, profile)
    if blocked:
        return float("-inf"), [reason or "Blocked"]

    reasons: list[str] = []
    score = 0.0

    enjoyment = enjoyment_score(recipe, history)
    score += float(profile.get("enjoyment_weight", 0.45)) * enjoyment[0]
    reasons.append(enjoyment[1])

    goal = goal_score(recipe, profile.get("nutrition_goal", "balanced"))
    score += float(profile.get("nutrition_weight", 0.35)) * goal[0]
    reasons.append(goal[1])

    variety = variety_bonus(recipe, history)
    score += float(profile.get("variety_weight", 0.20)) * variety[0]
    reasons.append(variety[1])

    preference_bonus = recipe_kind_bonus(recipe, normalize_list(profile.get("preferred_cuisines", [])))
    score += preference_bonus[0]
    if preference_bonus[1]:
        reasons.append(preference_bonus[1])

    request_bonus, request_reasons = plan_match_score(recipe, must_include_terms)
    score += request_bonus
    reasons.extend(request_reasons)

    if recipe.get("source") == "edamam":
        score += 0.03
        reasons.append("New recipe candidate")

    return score, [reason for reason in reasons if reason]


def find_best_for_term(candidates: list[dict[str, Any]], term: str, profile: dict[str, Any], history: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, list[str]]:
    term = term.strip().lower()
    if not term:
        return None, float("-inf"), []
    ranked: list[tuple[float, dict[str, Any], list[str]]] = []
    for candidate in candidates:
        score, reasons = score_recipe(candidate, profile, history, [term])
        if score > float("-inf"):
            ranked.append((score, candidate, reasons))
    if not ranked:
        return None, float("-inf"), []
    ranked.sort(key=lambda item: item[0], reverse=True)
    best_score, best_recipe, reasons = ranked[0]
    return best_recipe, best_score, reasons


def generate_week_plan(store: Any, profile: dict[str, Any], meal_count: int, must_include_text: str, include_api: bool = True) -> dict[str, Any]:
    history = store.recent_history(profile["id"], limit=100)
    must_include_terms = [term.strip().lower() for term in re.split(r"[,\n;]+", must_include_text) if term.strip()]
    candidates = build_candidate_pool(store.list_recipes(), profile, must_include_terms, include_api=include_api)

    selected_ids: set[str] = set()
    meals: list[dict[str, Any]] = []
    notes: list[str] = []

    for term in must_include_terms:
        best, score, reasons = find_best_for_term([candidate for candidate in candidates if recipe_id(candidate) not in selected_ids], term, profile, history)
        if best is None:
            notes.append(f"Could not find a confident match for '{term}'.")
            continue
        selected_ids.add(recipe_id(best))
        meals.append(
            {
                "slot": len(meals) + 1,
                "requested": term,
                "recipe": best,
                "score": round(score, 3),
                "reasons": reasons,
            }
        )

    remaining_slots = max(0, meal_count - len(meals))
    scored_candidates: list[tuple[float, dict[str, Any], list[str]]] = []
    for candidate in candidates:
        rid = recipe_id(candidate)
        if rid in selected_ids:
            continue
        score, reasons = score_recipe(candidate, profile, history, must_include_terms)
        if score > float("-inf"):
            scored_candidates.append((score, candidate, reasons))
    scored_candidates.sort(key=lambda item: item[0], reverse=True)

    for score, recipe, reasons in scored_candidates[:remaining_slots]:
        selected_ids.add(recipe_id(recipe))
        meals.append(
            {
                "slot": len(meals) + 1,
                "requested": "",
                "recipe": recipe,
                "score": round(score, 3),
                "reasons": reasons,
            }
        )

    meals = meals[:meal_count]
    if len(meals) < meal_count:
        notes.append(f"Only found {len(meals)} feasible recipes for {meal_count} requested meals.")

    meals.sort(key=lambda item: item["slot"])
    plan_request = {
        "meal_count": meal_count,
        "must_include": must_include_terms,
        "nutrition_goal": profile.get("nutrition_goal", "balanced"),
    }
    plan = store.add_weekly_plan(profile["id"], plan_request, meals)
    return {"plan": plan, "meals": meals, "notes": notes}
