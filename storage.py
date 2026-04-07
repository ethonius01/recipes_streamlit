from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-") or "item"


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def today_iso() -> str:
    return date.today().isoformat()


def default_profile() -> dict[str, Any]:
    return {
        "id": "default",
        "name": "Default profile",
        "nutrition_goal": "balanced",
        "dietary_restrictions": [],
        "preferred_cuisines": [],
        "disliked_ingredients": [],
        "enjoyment_weight": 0.45,
        "nutrition_weight": 0.35,
        "variety_weight": 0.20,
        "notes": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def seed_recipes() -> list[dict[str, Any]]:
    return [
        {
            "id": "mediterranean-chickpea-bowl",
            "name": "Mediterranean Chickpea Bowl",
            "category": "bowl",
            "ingredients": ["chickpeas", "cucumber", "tomatoes", "olive oil", "feta", "lemon"],
            "tags": ["mediterranean", "vegetarian", "high fiber", "low fat"],
            "nutrition": {"calories": 460, "protein_g": 19, "carbs_g": 52, "fat_g": 16},
            "source": "seed",
            "url": "",
            "notes": "Fresh, filling, and easy to batch prep.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "lemon-herb-salmon",
            "name": "Lemon Herb Salmon",
            "category": "dinner",
            "ingredients": ["salmon", "lemon", "garlic", "parsley", "asparagus"],
            "tags": ["mediterranean", "high protein", "low carb"],
            "nutrition": {"calories": 520, "protein_g": 39, "carbs_g": 12, "fat_g": 31},
            "source": "seed",
            "url": "",
            "notes": "Best for a high-protein lower-carb day.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "coconut-lentil-curry",
            "name": "Coconut Lentil Curry",
            "category": "curry",
            "ingredients": ["lentils", "coconut milk", "onion", "garlic", "spinach", "curry paste"],
            "tags": ["curry", "vegetarian", "dairy free", "high fiber"],
            "nutrition": {"calories": 480, "protein_g": 21, "carbs_g": 54, "fat_g": 18},
            "source": "seed",
            "url": "",
            "notes": "Warm and satisfying with leftovers.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "whole-wheat-pasta-primavera",
            "name": "Whole Wheat Pasta Primavera",
            "category": "pasta",
            "ingredients": ["whole wheat pasta", "zucchini", "bell pepper", "tomatoes", "parmesan", "olive oil"],
            "tags": ["pasta", "vegetarian", "balanced"],
            "nutrition": {"calories": 560, "protein_g": 20, "carbs_g": 70, "fat_g": 19},
            "source": "seed",
            "url": "",
            "notes": "Good default pasta night option.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "turkey-taco-skillet",
            "name": "Turkey Taco Skillet",
            "category": "skillet",
            "ingredients": ["ground turkey", "black beans", "corn", "salsa", "taco seasoning", "rice"],
            "tags": ["high protein", "weeknight", "gluten free"],
            "nutrition": {"calories": 540, "protein_g": 34, "carbs_g": 46, "fat_g": 22},
            "source": "seed",
            "url": "",
            "notes": "Fast and flexible for leftovers.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "sheet-pan-chicken-vegetables",
            "name": "Sheet Pan Chicken and Vegetables",
            "category": "sheet pan",
            "ingredients": ["chicken breast", "broccoli", "carrots", "potatoes", "olive oil", "rosemary"],
            "tags": ["high protein", "balanced", "low fat"],
            "nutrition": {"calories": 510, "protein_g": 38, "carbs_g": 32, "fat_g": 21},
            "source": "seed",
            "url": "",
            "notes": "Simple meal prep staple.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "veggie-chili",
            "name": "Veggie Chili",
            "category": "chili",
            "ingredients": ["kidney beans", "black beans", "tomatoes", "onion", "bell pepper", "chili powder"],
            "tags": ["vegetarian", "high fiber", "dairy free"],
            "nutrition": {"calories": 420, "protein_g": 19, "carbs_g": 56, "fat_g": 10},
            "source": "seed",
            "url": "",
            "notes": "Great for batch cooking.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "greek-chicken-salad",
            "name": "Greek Chicken Salad",
            "category": "salad",
            "ingredients": ["chicken", "romaine", "cucumber", "olives", "feta", "red onion"],
            "tags": ["mediterranean", "high protein", "low carb"],
            "nutrition": {"calories": 430, "protein_g": 36, "carbs_g": 18, "fat_g": 24},
            "source": "seed",
            "url": "",
            "notes": "Works well for a lighter lunch or dinner.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "tomato-basil-pasta",
            "name": "Tomato Basil Pasta",
            "category": "pasta",
            "ingredients": ["pasta", "tomatoes", "garlic", "basil", "parmesan", "olive oil"],
            "tags": ["pasta", "vegetarian", "balanced"],
            "nutrition": {"calories": 540, "protein_g": 17, "carbs_g": 78, "fat_g": 16},
            "source": "seed",
            "url": "",
            "notes": "Classic comfort meal.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "miso-ginger-noodles",
            "name": "Miso Ginger Noodles",
            "category": "noodles",
            "ingredients": ["noodles", "miso", "ginger", "scallions", "bok choy", "soy sauce"],
            "tags": ["balanced", "vegetarian", "quick"],
            "nutrition": {"calories": 500, "protein_g": 18, "carbs_g": 67, "fat_g": 16},
            "source": "seed",
            "url": "",
            "notes": "A fast weeknight option.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "beef-and-broccoli",
            "name": "Beef and Broccoli",
            "category": "stir fry",
            "ingredients": ["beef", "broccoli", "garlic", "soy sauce", "rice", "ginger"],
            "tags": ["high protein", "weeknight"],
            "nutrition": {"calories": 570, "protein_g": 37, "carbs_g": 38, "fat_g": 28},
            "source": "seed",
            "url": "",
            "notes": "Classic takeout-style dinner.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
        {
            "id": "black-bean-sweet-potato-tacos",
            "name": "Black Bean Sweet Potato Tacos",
            "category": "tacos",
            "ingredients": ["black beans", "sweet potato", "tortillas", "avocado", "lime", "cumin"],
            "tags": ["vegetarian", "high fiber", "balanced"],
            "nutrition": {"calories": 480, "protein_g": 15, "carbs_g": 64, "fat_g": 16},
            "source": "seed",
            "url": "",
            "notes": "Useful when you want a meatless main.",
            "sources": ["seed"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        },
    ]


def default_store() -> dict[str, Any]:
    return {
        "profiles": [default_profile()],
        "recipes": seed_recipes(),
        "recipe_events": [],
        "weekly_plans": [],
    }


def merge_recipe(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)
    for key, value in incoming.items():
        if key in {"ingredients", "tags", "sources"}:
            current = list(merged.get(key, []))
            for item in value or []:
                if item not in current:
                    current.append(item)
            merged[key] = current
        elif key == "nutrition":
            merged[key] = {**merged.get(key, {}), **(value or {})}
        elif value not in (None, "", []):
            merged[key] = value
    merged["updated_at"] = now_iso()
    return merged


@dataclass
class LocalStore:
    path: Path

    def __init__(self, path: Path | None = None):
        base = Path(__file__).resolve().parent
        self.path = path or (base / "data" / "meal_planner_store.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(default_store())
        else:
            self._ensure_seed_data()

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default_store()

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _ensure_seed_data(self) -> None:
        data = self._read()
        changed = False
        if not data.get("profiles"):
            data["profiles"] = [default_profile()]
            changed = True
        if not data.get("recipes"):
            data["recipes"] = seed_recipes()
            changed = True
        if "recipe_events" not in data:
            data["recipe_events"] = []
            changed = True
        if "weekly_plans" not in data:
            data["weekly_plans"] = []
            changed = True
        if changed:
            self._write(data)

    def load(self) -> dict[str, Any]:
        self._ensure_seed_data()
        return self._read()

    def save(self, data: dict[str, Any]) -> None:
        self._write(data)

    def list_profiles(self) -> list[dict[str, Any]]:
        return self.load().get("profiles", [])

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        for profile in self.list_profiles():
            if profile.get("id") == profile_id:
                return profile
        return None

    def upsert_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        profiles = data.setdefault("profiles", [])
        profile = deepcopy(profile)
        profile["id"] = profile.get("id") or slugify(profile.get("name", f"profile-{uuid.uuid4().hex[:8]}"))
        profile["created_at"] = profile.get("created_at") or now_iso()
        profile["updated_at"] = now_iso()
        for index, existing in enumerate(profiles):
            if existing.get("id") == profile["id"]:
                profiles[index] = {**existing, **profile}
                self.save(data)
                return profiles[index]
        profiles.append(profile)
        self.save(data)
        return profile

    def list_recipes(self) -> list[dict[str, Any]]:
        data = self.load()
        return sorted(data.get("recipes", []), key=lambda item: item.get("name", ""))

    def upsert_recipe(self, recipe: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        recipes = data.setdefault("recipes", [])
        recipe = deepcopy(recipe)
        recipe_id = recipe.get("id") or slugify(recipe.get("name", f"recipe-{uuid.uuid4().hex[:8]}"))
        recipe["id"] = recipe_id
        recipe.setdefault("sources", [recipe.get("source", "manual")])
        recipe.setdefault("created_at", now_iso())
        recipe["updated_at"] = now_iso()
        for index, existing in enumerate(recipes):
            if existing.get("id") == recipe_id:
                recipes[index] = merge_recipe(existing, recipe)
                self.save(data)
                return recipes[index]
        recipes.append(recipe)
        self.save(data)
        return recipe

    def add_recipe_event(self, profile_id: str, recipe_id: str, rating: int, made_on: str | None = None, note: str = "") -> dict[str, Any]:
        data = self.load()
        event = {
            "id": uuid.uuid4().hex,
            "profile_id": profile_id,
            "recipe_id": recipe_id,
            "rating": int(rating),
            "made_on": made_on or today_iso(),
            "note": note,
            "created_at": now_iso(),
        }
        data.setdefault("recipe_events", []).append(event)
        self.save(data)
        return event

    def recent_history(self, profile_id: str, limit: int = 50) -> list[dict[str, Any]]:
        data = self.load()
        recipes = {recipe["id"]: recipe for recipe in data.get("recipes", [])}
        events = [
            {**event, "recipe": recipes.get(event.get("recipe_id"), {})}
            for event in data.get("recipe_events", [])
            if event.get("profile_id") == profile_id
        ]
        events.sort(key=lambda item: item.get("made_on", ""), reverse=True)
        return events[:limit]

    def add_weekly_plan(self, profile_id: str, request: dict[str, Any], meals: list[dict[str, Any]]) -> dict[str, Any]:
        data = self.load()
        plan = {
            "id": uuid.uuid4().hex,
            "profile_id": profile_id,
            "created_at": now_iso(),
            "request": request,
            "meals": meals,
        }
        data.setdefault("weekly_plans", []).append(plan)
        self.save(data)
        return plan


def recipe_summary(recipe: dict[str, Any]) -> str:
    parts = [recipe.get("name", "Unnamed recipe")]
    if recipe.get("category"):
        parts.append(recipe["category"])
    if recipe.get("tags"):
        parts.append(", ".join(recipe.get("tags", [])[:3]))
    return " | ".join(parts)
