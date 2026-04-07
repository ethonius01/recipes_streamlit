# Weekly Meal Planner

A Streamlit app that helps plan meals for a week based on meal count, must-include recipe requests, recipe history, nutrition goals, and dietary restrictions.

## Features

- Multiple profile support
- Manual recipe entry with enjoyment rating
- PDF recipe upload with extraction and manual correction
- Recipe history and repeat-suggestion logic
- Balanced meal planning with nutrition and restriction checks
- Optional Edamam recipe search for new ideas

## Local run

Install the packages in `requirements.txt`, then run:

```bash
streamlit run app.py
```

## Notes

- The app creates its local storage file on first run in `Food_Schedule_App/data/meal_planner_store.json`.
- If Edamam credentials are not configured, the app still works with the saved recipe library.
- OCR support for image-based PDFs needs Linux system libraries in `packages.txt` when running on Streamlit Community Cloud.
