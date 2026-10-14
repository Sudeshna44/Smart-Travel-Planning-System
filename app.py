"""Streamlit interface for the multi-agent Smart Travel Planning System."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

from integrations import collect_research, source_urls
from travel_core import budget_alternative, calculate_trip_budget, format_inr, make_trip_request
from travel_planner import create_travel_crew, gemini_failure_guidance

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Smart Travel Planner", page_icon="✈️", layout="wide")
st.title("✈️ Smart Travel Planning System")
st.caption(
    "A CrewAI planning crew with OpenRouter and live public research sources. "
    "Booking and price bands are clearly marked as prototype estimates."
)

with st.sidebar:
    st.header("Google Gemini")
    gemini_key = st.text_input(
        "API key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help="Used for this session only. It is not written to the project files.",
    )
    model = st.text_input(
        "Model ID",
        value=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
        help="Enter a Gemini model ID available to your Google AI Studio project.",
    )
    st.caption("Set GEMINI_API_KEY and GEMINI_MODEL in .env to avoid re-entering them.")

with st.form("trip_requirements"):
    st.subheader("Your trip")
    location_col, date_col = st.columns(2)
    with location_col:
        origin = st.text_input("Starting location", placeholder="e.g. Boston, USA")
        destination = st.text_input("Destination", placeholder="e.g. Kyoto, Japan")
    with date_col:
        selected_dates = st.date_input(
            "Departure and return dates",
            value=(date.today() + timedelta(days=30), date.today() + timedelta(days=35)),
            min_value=date.today(),
        )
        travelers = st.number_input("Travelers", min_value=1, max_value=20, value=2, step=1)

    interests = st.multiselect(
        "Preferred activities",
        ["Sightseeing", "Shopping", "Adventure", "Relaxation", "Food", "Culture", "Nature", "Nightlife"],
        default=["Sightseeing", "Food", "Culture"],
    )
    budget_col, hotel_col, transport_col, daily_col = st.columns(4)
    with budget_col:
        budget = st.number_input("Total budget (INR)", min_value=1.0, value=250000.0, step=5000.0)
    with hotel_col:
        hotel_per_night = st.number_input(
            "Hotel / room / night (INR)", min_value=1.0, value=10000.0, step=500.0
        )
    with transport_col:
        transport_per_person = st.number_input(
            "Round-trip transport / person (INR)", min_value=0.0, value=25000.0, step=1000.0
        )
    with daily_col:
        daily_spend = st.number_input(
            "Food, activities & local transport / person / day (INR)",
            min_value=0.0,
            value=6000.0,
            step=500.0,
        )
    st.caption(
        "Cost fields are editable planning assumptions, not live quotes. Hotel rooms are estimated "
        "at two travelers per room."
    )
    submitted = st.form_submit_button("Research and build my travel plan", type="primary")

if submitted:
    if not gemini_key.strip():
        st.error("Enter your Google AI Studio API key or set GEMINI_API_KEY in .env.")
        st.stop()
    if not model.strip():
        st.error("Enter a Gemini model ID or set GEMINI_MODEL in .env.")
        st.stop()
    if not isinstance(selected_dates, (tuple, list)) or len(selected_dates) != 2:
        st.error("Select both a departure date and a return date.")
        st.stop()

    try:
        request = make_trip_request(
            destination=destination,
            origin=origin,
            start_date=selected_dates[0],
            end_date=selected_dates[1],
            budget=budget,
            interests=tuple(interests),
            travelers=int(travelers),
            hotel_per_room_night=hotel_per_night,
            transport_per_traveler=transport_per_person,
            daily_spend_per_traveler=daily_spend,
        )
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        st.stop()

    trip = request.to_dict()
    estimate = calculate_trip_budget(
        hotel_per_room_night=request.hotel_per_room_night,
        rooms=request.rooms,
        nights=request.nights,
        transport_per_traveler=request.transport_per_traveler,
        travelers=request.travelers,
        daily_spend_per_traveler=request.daily_spend_per_traveler,
        days=request.days,
    )
    alternative = budget_alternative(request)
    with st.spinner("Collecting research and coordinating the CrewAI agents..."):
        research = collect_research(
            request.origin,
            request.destination,
            request.start_date.isoformat(),
            request.end_date.isoformat(),
            list(request.interests),
        )
        try:
            crew = create_travel_crew(
                api_key=gemini_key.strip(),
                model=model.strip(),
                trip=trip,
                research=research,
                budget=estimate,
                alternative=alternative,
            )
            result = crew.kickoff()
        except Exception as exc:
            logger.exception("Travel planning crew failed")
            error_title, error_guidance = gemini_failure_guidance(exc)
            st.error(error_title)
            st.info(error_guidance)
            st.stop()

    st.subheader("Your travel plan")
    st.markdown(str(result))

    st.subheader("Budget check")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Estimated total", format_inr(estimate["total_inr"]))
    metric_cols[1].metric("Your budget", format_inr(request.budget))
    difference = request.budget - estimate["total_inr"]
    metric_cols[2].metric(
        "Budget status",
        f"{format_inr(abs(difference))} {'remaining' if difference >= 0 else 'over'}",
    )
    metric_cols[3].metric("Duration", f"{request.days} days / {request.nights} nights")
    st.dataframe(
        [
            {"Expense": "Accommodation", "Estimated cost (INR)": format_inr(estimate["hotel_inr"])},
            {"Expense": "Round-trip transport", "Estimated cost (INR)": format_inr(estimate["transport_inr"])},
            {
                "Expense": "Food, activities and local transport",
                "Estimated cost (INR)": format_inr(
                    estimate["food_activities_local_transport_inr"]
                ),
            },
        ],
        hide_index=True,
        use_container_width=True,
    )
    if estimate["total_inr"] > request.budget:
        lower_estimate = alternative["estimate"]
        st.warning(
            f"The estimate is {format_inr(estimate['total_inr'] - request.budget)} over budget. "
            f"The lower-cost scenario estimates {format_inr(lower_estimate['total_inr'])} "
            f"({'within budget' if alternative['fits_budget'] else 'still over budget'}). "
            "It assumes budget lodging, 30% lower transport allowance, and 30% lower daily spend."
        )

    with st.expander("Research sources and availability"):
        st.write("Source results provided to the agents:")
        for name, data in research.items():
            st.markdown(f"**{name.replace('_', ' ').title()}** — `{data.get('status', 'unknown')}`")
            if data.get("error"):
                st.caption(data["error"])
            if name == "web_search":
                for item in data.get("results", []):
                    if item.get("url"):
                        st.markdown(f"- [{item.get('title') or item['url']}]({item['url']})")
                        if item.get("snippet"):
                            st.caption(item["snippet"])
            elif data.get("status") in {"ok", "partial"}:
                st.json(data)
        st.caption("Search results and public API data may be incomplete; verify details with providers.")

    with st.expander("Planning assumptions"):
        st.json(
            {
                "budget_estimate_inr": estimate,
                "lower_cost_scenario": alternative,
                "source_urls": source_urls(research),
                "hotel_and_transport_quotes": (
                    "Illustrative user-entered assumptions; no booking or fare inventory was queried."
                ),
            }
        )

st.divider()
st.caption(
    "Prototype only: no reservations or purchases are made. Confirm prices, schedules, visa rules, "
    "weather, accessibility, and opening hours with official providers before traveling."
)
