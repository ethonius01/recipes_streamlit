from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from pdf_ingest import extract_recipe_from_pdf, parser_capabilities
from recommendation import generate_week_plan
from storage import LocalStore, now_iso, recipe_summary, slugify


APP_DIR = Path(__file__).resolve().parent


st.set_page_config(page_title="Weekly Meal Planner", page_icon="🍽️", layout="wide")


st.markdown(
    """
<style>
    .stApp {
        background: linear-gradient(180deg, #fffdf8 0%, #f7f1e8 100%);
    }
    .hero {
        padding: 1.1rem 1.2rem;
        border-radius: 1rem;
        background: linear-gradient(135deg, #183153 0%, #2d6a4f 100%);
        color: white;
        margin-bottom: 1rem;
    }
    .muted {
        color: #5c5c5c;
    }
    .card {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 0.9rem;
        padding: 0.9rem 1rem;
        background: rgba(255,255,255,0.85);
        margin-bottom: 0.75rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def get_store() -> LocalStore:
    return LocalStore()


def split_values(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,\n;]+", value or "") if item.strip()]


def parse_nutrition_goal(choice: str) -> str:
    return choice.strip().lower()


def get_profile_options(store: LocalStore) -> list[dict[str, object]]:
    profiles = store.list_profiles()
    profiles.sort(key=lambda item: item.get("name", ""))
    return profiles


def set_active_profile(profile_id: str) -> None:
    st.session_state["active_profile_id"] = profile_id


def active_profile(store: LocalStore) -> dict[str, object]:
    profiles = get_profile_options(store)
    if not profiles:
        return store.upsert_profile({"name": "Default profile"})
    current = st.session_state.get("active_profile_id")
    if current:
        for profile in profiles:
            if profile.get("id") == current:
                return profile
    return profiles[0]


def recipe_choice_label(recipe: dict[str, object]) -> str:
    return f"{recipe.get('name', 'Unnamed recipe')} ({recipe.get('category', 'general')})"


def recipe_table(recipes: list[dict[str, object]]) -> pd.DataFrame:
    rows = []
    for recipe in recipes:
        rows.append(
            {
                "Name": recipe.get("name", ""),
                "Category": recipe.get("category", ""),
                "Tags": ", ".join(recipe.get("tags", [])),
                "Source": recipe.get("source", ""),
                "Ingredients": ", ".join(recipe.get("ingredients", [])[:6]),
            }
        )
    return pd.DataFrame(rows)


def save_recipe_from_form(store: LocalStore, profile_id: str, name: str, category: str, ingredients_text: str, tags_text: str, notes: str, enjoyment: int) -> dict[str, object]:
    recipe = {
        "id": slugify(name),
        "name": name.strip(),
        "category": category.strip() or "general",
        "ingredients": split_values(ingredients_text),
        "tags": [tag.lower() for tag in split_values(tags_text)],
        "nutrition": {},
        "source": "manual",
        "url": "",
        "notes": notes.strip(),
        "sources": ["manual"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    recipe = store.upsert_recipe(recipe)
    store.add_recipe_event(profile_id, recipe["id"], enjoyment, made_on=date.today().isoformat(), note="Added from manual entry")
    return recipe


def save_pdf_recipe(store: LocalStore, profile_id: str, candidate: dict[str, object], name: str, category: str, ingredients_text: str, tags_text: str, notes: str, enjoyment: int) -> dict[str, object]:
    recipe = {
        "id": slugify(name or candidate.get("title", "imported recipe")),
        "name": name.strip() or candidate.get("title", "Imported recipe"),
        "category": category.strip() or "imported",
        "ingredients": split_values(ingredients_text) or candidate.get("ingredients", []),
        "tags": [tag.lower() for tag in split_values(tags_text)],
        "nutrition": {},
        "source": "pdf",
        "url": "",
        "notes": notes.strip(),
        "sources": ["pdf"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    recipe = store.upsert_recipe(recipe)
    store.add_recipe_event(profile_id, recipe["id"], enjoyment, made_on=date.today().isoformat(), note="Added from PDF upload")
    return recipe


@st.cache_data(show_spinner=False)
def parse_pdf_bytes(file_bytes: bytes) -> dict[str, object]:
    class UploadedBytes:
        def __init__(self, data: bytes):
            self._data = data

        def getvalue(self) -> bytes:
            return self._data

    return extract_recipe_from_pdf(UploadedBytes(file_bytes))


store = get_store()
profiles = get_profile_options(store)
current_profile = active_profile(store)
profile_index = 0
for idx, profile in enumerate(profiles):
    if profile.get("id") == current_profile.get("id"):
        profile_index = idx
        break

st.sidebar.header("Profile")
selected_profile = st.sidebar.selectbox(
    "Choose profile",
    profiles,
    index=profile_index if profiles else 0,
    format_func=lambda profile: profile.get("name", "Unnamed profile"),
)
if profiles:
    set_active_profile(selected_profile["id"])
    current_profile = selected_profile

with st.sidebar.expander("Create new profile", expanded=False):
    with st.form("new_profile_form", clear_on_submit=True):
        new_name = st.text_input("Profile name")
        create = st.form_submit_button("Create profile")
    if create and new_name.strip():
        created = store.upsert_profile({"name": new_name.strip()})
        set_active_profile(created["id"])
        st.rerun()

st.markdown(
    f"""
    <div class="hero">
        <h1>Weekly Meal Planner</h1>
        <p>Plan meals for the week, reuse recipes you already like, and keep nutrition and restrictions in view.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

profiles_count = len(profiles)
recipes_count = len(store.list_recipes())
history_count = len(store.recent_history(current_profile["id"], limit=999))

metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Profiles", profiles_count)
metric_b.metric("Saved recipes", recipes_count)
metric_c.metric("Recipe history", history_count)

tab_plan, tab_memory, tab_profile, tab_library = st.tabs(["Plan week", "Recipe memory", "Profile", "Library"])


with tab_profile:
    st.subheader(f"Profile settings: {current_profile.get('name', 'Profile')}")
    with st.form("profile_form"):
        goal = st.selectbox(
            "Nutrition goal",
            ["balanced", "low fat", "low carb", "mediterranean", "high protein", "vegetarian"],
            index=["balanced", "low fat", "low carb", "mediterranean", "high protein", "vegetarian"].index(str(current_profile.get("nutrition_goal", "balanced"))),
        )
        restrictions = st.multiselect(
            "Dietary restrictions",
            ["vegetarian", "vegan", "gluten free", "dairy free", "nut free", "low sodium", "pork free", "shellfish free", "halal"],
            default=current_profile.get("dietary_restrictions", []),
        )
        cuisines = st.multiselect(
            "Preferred cuisines / styles",
            ["mediterranean", "pasta", "curry", "salad", "stir fry", "tacos", "bowl", "sheet pan", "chili"],
            default=current_profile.get("preferred_cuisines", []),
        )
        disliked = st.text_input("Disliked ingredients", value=", ".join(current_profile.get("disliked_ingredients", [])))
        notes = st.text_area("Notes", value=str(current_profile.get("notes", "")))
        weights_col_a, weights_col_b, weights_col_c = st.columns(3)
        with weights_col_a:
            enjoyment_weight = st.slider("Enjoyment weight", 0.0, 1.0, float(current_profile.get("enjoyment_weight", 0.45)), 0.05)
        with weights_col_b:
            nutrition_weight = st.slider("Nutrition weight", 0.0, 1.0, float(current_profile.get("nutrition_weight", 0.35)), 0.05)
        with weights_col_c:
            variety_weight = st.slider("Variety weight", 0.0, 1.0, float(current_profile.get("variety_weight", 0.20)), 0.05)
        save_profile = st.form_submit_button("Save profile")
    if save_profile:
        updated = {
            **current_profile,
            "nutrition_goal": parse_nutrition_goal(goal),
            "dietary_restrictions": restrictions,
            "preferred_cuisines": cuisines,
            "disliked_ingredients": split_values(disliked),
            "notes": notes,
            "enjoyment_weight": enjoyment_weight,
            "nutrition_weight": nutrition_weight,
            "variety_weight": variety_weight,
        }
        saved = store.upsert_profile(updated)
        set_active_profile(saved["id"])
        st.success("Profile saved.")
        st.rerun()

    st.markdown("### Recent history")
    history = store.recent_history(current_profile["id"], limit=10)
    if history:
        rows = []
        for event in history:
            recipe = event.get("recipe", {})
            rows.append(
                {
                    "Date": event.get("made_on", ""),
                    "Recipe": recipe.get("name", ""),
                    "Rating": event.get("rating", ""),
                    "Source": recipe.get("source", ""),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.info("No recipe history yet for this profile.")


with tab_plan:
    st.subheader("Build a weekly plan")
    with st.form("plan_form"):
        meal_count = st.slider("How many meals do you need this week?", 1, 14, 7)
        must_include = st.text_area(
            "Must-include recipes or recipe types",
            placeholder="Example: curry, pasta, Greek chicken salad",
            height=110,
        )
        include_web = st.checkbox("Include new recipe suggestions from Edamam when available", value=True)
        generate = st.form_submit_button("Generate plan")

    if generate:
        result = generate_week_plan(store, current_profile, meal_count, must_include, include_api=include_web)
        st.session_state["latest_plan"] = result
        if result.get("notes"):
            for note in result["notes"]:
                st.warning(note)
        st.success("Plan generated.")

    latest = st.session_state.get("latest_plan")
    if latest:
        meals = latest.get("meals", [])
        if meals:
            plan_rows = []
            for meal in meals:
                recipe = meal.get("recipe", {})
                plan_rows.append(
                    {
                        "Slot": meal.get("slot", ""),
                        "Recipe": recipe.get("name", ""),
                        "Category": recipe.get("category", ""),
                        "Source": recipe.get("source", ""),
                        "Score": meal.get("score", ""),
                        "Why it was picked": "; ".join(meal.get("reasons", [])[:4]),
                    }
                )
            st.dataframe(pd.DataFrame(plan_rows), hide_index=True, use_container_width=True)
        else:
            st.info("No meals generated yet.")

        st.markdown("### Meal details")
        for meal in meals:
            recipe = meal.get("recipe", {})
            with st.container(border=True):
                st.markdown(f"**Meal {meal.get('slot', '')}: {recipe.get('name', 'Unnamed recipe')}**")
                st.caption(f"{recipe.get('category', 'general')} | {recipe.get('source', 'manual')} | score {meal.get('score', 0)}")
                if recipe.get("tags"):
                    st.write("Tags:", ", ".join(recipe.get("tags", [])))
                if recipe.get("ingredients"):
                    st.write("Ingredients:", ", ".join(recipe.get("ingredients", [])[:8]))
                if meal.get("reasons"):
                    st.write("Why this was chosen:")
                    st.write([reason for reason in meal.get("reasons", []) if reason])

        if st.button("Save latest plan to history") and latest:
            st.success("Latest plan is already saved when generated.")
    else:
        st.info("Generate a plan to see meal suggestions.")


with tab_memory:
    st.subheader("Save recipes to memory")
    manual_col, pdf_col = st.columns(2)

    with manual_col:
        st.markdown("#### Add by name")
        with st.form("manual_recipe_form"):
            recipe_name = st.text_input("Recipe name")
            recipe_category = st.text_input("Recipe type", placeholder="Example: curry or pasta")
            recipe_ingredients = st.text_area("Ingredients", placeholder="One ingredient per line or comma-separated")
            recipe_tags = st.text_input("Tags", placeholder="Example: mediterranean, low carb")
            recipe_notes = st.text_area("Notes")
            enjoyment = st.slider("How much did you enjoy it?", 1, 5, 4)
            save_manual = st.form_submit_button("Save recipe")
        if save_manual and recipe_name.strip():
            saved = save_recipe_from_form(
                store,
                current_profile["id"],
                recipe_name,
                recipe_category,
                recipe_ingredients,
                recipe_tags,
                recipe_notes,
                enjoyment,
            )
            st.success(f"Saved {saved['name']}.")
        elif save_manual:
            st.warning("Please provide a recipe name.")

    with pdf_col:
        st.markdown("#### Add from PDF")
        uploaded_pdf = st.file_uploader("Upload a recipe PDF", type=["pdf"], key="recipe_pdf")
        if uploaded_pdf is not None:
            candidate = parse_pdf_bytes(uploaded_pdf.getvalue())
            st.session_state["pdf_candidate"] = candidate
        candidate = st.session_state.get("pdf_candidate")
        if candidate:
            st.caption("Review and correct the extracted recipe before saving.")
            if candidate.get("extraction_method"):
                st.caption(f"Extraction method: {candidate.get('extraction_method')}")
            if candidate.get("warning"):
                st.warning(str(candidate.get("warning")))
            diagnostics = candidate.get("diagnostics", [])
            if diagnostics:
                st.caption("Parser diagnostics: " + " | ".join(str(item) for item in diagnostics))
            with st.expander("Parser runtime capabilities", expanded=False):
                st.json(parser_capabilities())
            with st.form("pdf_recipe_form"):
                pdf_name = st.text_input("Recipe name", value=str(candidate.get("title", "")))
                pdf_category = st.text_input("Recipe type", value="imported")
                pdf_ingredients = st.text_area("Ingredients", value="\n".join(candidate.get("ingredients", [])))
                pdf_tags = st.text_input("Tags", value="")
                pdf_notes = st.text_area("Notes", value="Imported from PDF")
                pdf_enjoyment = st.slider("How much did you enjoy it?", 1, 5, 4, key="pdf_enjoyment")
                save_pdf = st.form_submit_button("Save PDF recipe")
            if save_pdf and pdf_name.strip():
                saved = save_pdf_recipe(
                    store,
                    current_profile["id"],
                    candidate,
                    pdf_name,
                    pdf_category,
                    pdf_ingredients,
                    pdf_tags,
                    pdf_notes,
                    pdf_enjoyment,
                )
                st.success(f"Saved {saved['name']}.")
            if st.checkbox("Show extracted text preview", value=False):
                st.text_area("Extracted PDF text", value=str(candidate.get("raw_text", ""))[:5000], height=180)
        else:
            st.info("Upload a PDF to extract the recipe name and ingredients.")

    st.markdown("### Mark a recipe as recently made")
    recipes = store.list_recipes()
    if recipes:
        recipe_map = {recipe_choice_label(recipe): recipe for recipe in recipes}
        with st.form("recent_recipe_form"):
            selected_recipe_label = st.selectbox("Choose recipe", list(recipe_map.keys()))
            recent_rating = st.slider("Enjoyment rating", 1, 5, 4, key="recent_rating")
            recent_note = st.text_input("Note", value="")
            save_recent = st.form_submit_button("Record recipe")
        if save_recent and selected_recipe_label:
            recipe = recipe_map[selected_recipe_label]
            store.add_recipe_event(current_profile["id"], recipe["id"], recent_rating, made_on=date.today().isoformat(), note=recent_note)
            st.success(f"Recorded {recipe['name']} as recently made.")
    else:
        st.info("No recipes saved yet.")


with tab_library:
    st.subheader("Recipe library")
    recipes = store.list_recipes()
    if recipes:
        search = st.text_input("Search recipes")
        filtered = recipes
        if search.strip():
            query = search.lower().strip()
            filtered = [recipe for recipe in recipes if query in recipe_summary(recipe).lower() or query in " ".join(recipe.get("ingredients", [])).lower()]
        st.dataframe(recipe_table(filtered), hide_index=True, use_container_width=True)

        st.markdown("### Recipe details")
        detail_map = {recipe_choice_label(recipe): recipe for recipe in filtered}
        if detail_map:
            chosen_detail = st.selectbox("View recipe", list(detail_map.keys()))
            recipe = detail_map[chosen_detail]
            st.markdown(f"**{recipe.get('name', '')}**")
            st.caption(f"{recipe.get('category', '')} | {recipe.get('source', '')}")
            if recipe.get("tags"):
                st.write("Tags:", ", ".join(recipe.get("tags", [])))
            if recipe.get("ingredients"):
                st.write("Ingredients:", ", ".join(recipe.get("ingredients", [])))
            if recipe.get("notes"):
                st.write(recipe.get("notes"))
            nutrition = recipe.get("nutrition", {})
            if nutrition:
                st.write("Nutrition:", nutrition)
    else:
        st.info("Recipe library is empty.")
