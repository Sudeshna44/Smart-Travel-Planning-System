# Smart Travel Planning System

A Streamlit travel-planning prototype using CrewAI agents and Google Gemini through Google AI Studio. The coordinator, destination researcher, hotel/transport researcher, budget analyst, and itinerary planner share task outputs in a sequential CrewAI workflow.

## Features

- Collects origin, destination, dates, interests, traveler count, and a total budget.
- Uses DuckDuckGo search, Open-Meteo weather/geocoding, and OSRM driving-route estimates when available.
- Handles trips outside the 16-day weather forecast window and skips implausible long-distance driving routes.
- Gives agents dedicated search, weather, route, accommodation, transport, calculator, and schedule tools.
- Calculates the budget deterministically from editable user assumptions, then asks the budget agent to verify the calculation and recommend revisions.
- Shows all trip budgets, estimates, and illustrative prices in Indian rupees (INR).
- Labels accommodation and transport price bands as prototype estimates; no booking APIs or live availability are connected.
- Displays source links and errors/limitations from unavailable data sources.

## Run locally on Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your Google AI Studio key and an available Gemini model ID to `.env`, then start Streamlit:

```powershell
streamlit run app.py
```

Alternatively, enter the API key in the app sidebar. It is used only for the current run and is not saved.

## Configuration

- `GEMINI_API_KEY`: Google AI Studio API key (required).
- `GEMINI_MODEL`: Gemini model ID available to your Google AI Studio project (defaults to `gemini-3.8-flash`).

Budget and price inputs are in Indian rupees (INR). The displayed sample amounts are planning assumptions, not currency conversions or provider quotes. The search, weather, and route sources are public services and may have rate limits, coverage limits, or downtime. Weather forecasts are only available for supported dates. Hotel and transport amounts entered in the form are planning assumptions, not provider prices. The prototype does not make reservations or purchases.

If Gemini reports a quota or rate-limit error, wait for the quota to reset or check the model and rate limits for your Google AI Studio project.

## Tests

```powershell
python -m pytest
```
