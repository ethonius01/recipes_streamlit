from __future__ import annotations

import os
from typing import Any

import requests


class EdamamClient:
    def __init__(self) -> None:
        self.app_id = os.getenv("EDAMAM_APP_ID", "")
        self.app_key = os.getenv("EDAMAM_APP_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.app_id and self.app_key)

    def search(self, query: str, max_results: int = 6) -> list[dict[str, Any]]:
        if not self.enabled or not query.strip():
            return []
        url = "https://api.edamam.com/api/recipes/v2"
        params = [
            ("type", "public"),
            ("q", query),
            ("app_id", self.app_id),
            ("app_key", self.app_key),
            ("random", "false"),
        ]
        params.extend(
            ("field", field)
            for field in [
                "uri",
                "label",
                "image",
                "source",
                "url",
                "yield",
                "ingredientLines",
                "cuisineType",
                "mealType",
                "dishType",
                "dietLabels",
                "healthLabels",
                "calories",
                "totalTime",
                "totalNutrients",
            ]
        )
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            return []

        payload = response.json()
        hits = payload.get("hits", [])[:max_results]
        results: list[dict[str, Any]] = []
        for hit in hits:
            recipe = hit.get("recipe", {})
            labels = []
            labels.extend(recipe.get("dietLabels", []))
            labels.extend(recipe.get("healthLabels", []))
            labels.extend(recipe.get("cuisineType", []))
            labels.extend(recipe.get("mealType", []))
            labels.extend(recipe.get("dishType", []))
            normalized_labels = sorted({str(label).lower() for label in labels if label})
            results.append(
                {
                    "id": recipe.get("uri", recipe.get("label", "")).split("#")[-1].lower(),
                    "name": recipe.get("label", "Untitled recipe"),
                    "category": ", ".join(recipe.get("dishType", [])[:2]) or ", ".join(recipe.get("mealType", [])[:1]) or "internet",
                    "ingredients": recipe.get("ingredientLines", []),
                    "tags": normalized_labels,
                    "nutrition": {
                        "calories": round(recipe.get("calories", 0) or 0),
                    },
                    "source": "edamam",
                    "url": recipe.get("url", ""),
                    "notes": f"Found via Edamam search for {query}",
                    "sources": ["edamam"],
                    "created_at": "",
                    "updated_at": "",
                }
            )
        return results
