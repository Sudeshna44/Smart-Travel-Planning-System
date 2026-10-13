"""CrewAI agents, tool definitions, and sequential travel-planning workflow."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

from integrations import (
    mock_accommodation_options,
    mock_transport_options,
    route_estimate,
    weather_forecast,
    web_search,
)
from travel_core import calculate_trip_budget, day_schedule


def gemini_failure_guidance(error: Exception) -> tuple[str, str]:
    """Return safe Gemini troubleshooting guidance without raw provider details."""
    message = str(error).lower()
    if (
        "429" in message
        or "resource_exhausted" in message
        or "quota" in message
        or "rate limit" in message
    ):
        return (
            "The Gemini API quota or rate limit was reached.",
            "Wait for the quota to reset, check your Google AI Studio project’s model limits, "
            "or select another Gemini model available to your project.",
        )
    return (
        "The CrewAI planning run could not be completed.",
        "Check your Google AI Studio API key, Gemini model ID, project access, and internet connection, "
        "then retry.",
    )


@tool("Search the web for destination information")
def search_web_tool(query: str) -> str:
    """Search the web for attractions, local experiences, hotels, or transport and return source URLs."""
    return json.dumps(web_search(query), ensure_ascii=False)


@tool("Get weather forecast for travel dates")
def weather_tool(destination: str, start_date: str, end_date: str) -> str:
    """Fetch Open-Meteo daily forecast for the destination and requested date range."""
    return json.dumps(weather_forecast(destination, start_date, end_date), ensure_ascii=False)


@tool("Estimate driving route")
def route_tool(origin: str, destination: str) -> str:
    """Estimate road distance and driving time using Open-Meteo geocoding and OSRM."""
    return json.dumps(route_estimate(origin, destination), ensure_ascii=False)


@tool("Find prototype accommodation options")
def accommodation_options_tool(
    destination: str, rooms: int, nights: int, nightly_budget: float
) -> str:
    """Return clearly labeled illustrative accommodation price bands; this is not live inventory."""
    return json.dumps(
        mock_accommodation_options(destination, rooms, nights, nightly_budget),
        ensure_ascii=False,
    )


@tool("Find prototype transport options")
def transport_options_tool(
    origin: str, destination: str, travelers: int, round_trip_per_traveler: float
) -> str:
    """Return clearly labeled editable transport allowances; this is not a live fare search."""
    return json.dumps(
        mock_transport_options(origin, destination, travelers, round_trip_per_traveler),
        ensure_ascii=False,
    )


@tool("Calculate trip expenses")
def calculator_tool(
    hotel_per_room_night: float,
    rooms: int,
    nights: int,
    transport_per_traveler: float,
    travelers: int,
    daily_spend_per_traveler: float,
    days: int,
) -> str:
    """Calculate hotel, round-trip transport, and daily food/activity/local-transport estimates in INR."""
    return json.dumps(
        calculate_trip_budget(
            hotel_per_room_night=hotel_per_room_night,
            rooms=rooms,
            nights=nights,
            transport_per_traveler=transport_per_traveler,
            travelers=travelers,
            daily_spend_per_traveler=daily_spend_per_traveler,
            days=days,
        ),
        ensure_ascii=False,
    )


@tool("Create a dated day-by-day schedule")
def schedule_tool(start_date: str, days: int) -> str:
    """Return ISO calendar dates for every day in the trip."""
    return json.dumps(day_schedule(date.fromisoformat(start_date), days))


def create_travel_crew(
    *,
    api_key: str,
    model: str,
    trip: dict[str, Any],
    research: dict[str, Any],
    budget: dict[str, float],
    alternative: dict[str, Any],
) -> Crew:
    """Configure a sequential CrewAI workflow with explicit task context dependencies."""
    model_name = model.strip()
    if model_name.startswith("gemini/"):
        model_name = model_name.removeprefix("gemini/")
    llm = LLM(
        model=f"gemini/{model_name}",
        api_key=api_key,
        temperature=0.3,
    )

    coordinator = Agent(
        role="Travel Coordinator",
        goal="Translate the customer's requirements into a coordinated, realistic travel plan.",
        backstory="You coordinate specialist research and ensure the final plan follows the customer's constraints.",
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=False,
    )
    destination_researcher = Agent(
        role="Destination Research Agent",
        goal="Find relevant attractions, local experiences, travel information, and weather facts.",
        backstory="You are a careful destination researcher who distinguishes sourced facts from suggestions.",
        tools=[search_web_tool, weather_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=False,
    )
    hotel_transport_agent = Agent(
        role="Hotel and Transport Agent",
        goal="Compare practical accommodation and transportation options for the requested trip.",
        backstory="You make options clear and never present prototype estimates as confirmed bookings.",
        tools=[search_web_tool, route_tool, accommodation_options_tool, transport_options_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=False,
    )
    budget_analyst = Agent(
        role="Budget Analyst",
        goal="Calculate the estimated total, compare it with the budget, and identify savings.",
        backstory="You are numerate and show assumptions, totals, and budget gaps transparently.",
        tools=[calculator_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=False,
    )
    itinerary_planner = Agent(
        role="Itinerary Planner",
        goal="Build a feasible day-by-day itinerary using the approved research and budget.",
        backstory="You balance travel time, opening-hour uncertainty, interests, and a comfortable pace.",
        tools=[schedule_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=4,
        verbose=False,
    )

    coordinator_intake = Task(
        description=(
            "Review this request and research bundle; state the constraints that all specialist work "
            f"must follow. Customer request: {json.dumps(trip)}. "
            f"Collected research: {json.dumps(research, ensure_ascii=False)}"
        ),
        expected_output="A concise constraint summary with dates, origin, destination, interests, and budget.",
        agent=coordinator,
    )
    destination_task = Task(
        description=(
            "Research useful attractions and local experiences that match the customer's interests. "
            "You MUST call search_web_tool and weather_tool at least once each. Cite URLs from results. "
            "Do not make up source-backed facts; label uncertain or unavailable data. "
            f"Trip: {json.dumps(trip)}. Pre-collected results: {json.dumps(research, ensure_ascii=False)}"
        ),
        expected_output="A sourced shortlist of attractions and experiences, weather outlook or limitation, and URLs.",
        agent=destination_researcher,
        context=[coordinator_intake],
    )
    lodging_transport_task = Task(
        description=(
            "Research appropriate places to stay and transport options. You MUST call "
            "accommodation_options_tool, transport_options_tool, and route_tool. You may use "
            "search_web_tool to find destination-specific options. Identify all mock estimates as "
            "illustrative, not live availability or fares. "
            f"Trip and user assumptions: {json.dumps(trip)}. "
            f"Collected research: {json.dumps(research, ensure_ascii=False)}"
        ),
        expected_output="Accommodation and transport options, route facts if available, and clear source/estimate labels.",
        agent=hotel_transport_agent,
        context=[coordinator_intake],
    )
    budget_task = Task(
        description=(
            "You MUST call calculator_tool with the customer's exact assumptions and verify its result "
            "against the supplied deterministic estimate. All costs and budget amounts are in INR. "
            "Compare total with budget. If over budget, "
            "report the exact gap and use the supplied lower-cost alternative; say plainly if it still "
            "does not fit. Do not silently change the user's budget. "
            f"Trip assumptions: {json.dumps(trip)}. Current calculation: {json.dumps(budget)}. "
            f"Alternative scenario: {json.dumps(alternative)}"
        ),
        expected_output="A checked itemized estimate, budget comparison, and quantified alternatives if needed.",
        agent=budget_analyst,
        context=[coordinator_intake, lodging_transport_task],
    )
    budget_revision_task = Task(
        description=(
            "Review the budget analyst's result and the initial lodging/transport options. "
            "If the calculated total exceeds the user's budget, use accommodation_options_tool and "
            "transport_options_tool with the supplied lower-cost assumptions, then recommend the "
            "cheapest practical revision. If the lower-cost scenario still exceeds budget, state the "
            "remaining gap and do not claim it fits. If the estimate already fits, confirm no revision "
            "is needed. Never present mock estimates as live availability or fares. "
            f"Trip assumptions: {json.dumps(trip)}. "
            f"Current calculation: {json.dumps(budget)}. "
            f"Lower-cost scenario: {json.dumps(alternative)}"
        ),
        expected_output="A budget-aware lodging and transport revision, or confirmation that none is needed.",
        agent=hotel_transport_agent,
        context=[lodging_transport_task, budget_task],
    )
    itinerary_task = Task(
        description=(
            "Create a dated day-by-day itinerary, balancing travel time and the requested interests. "
            "You MUST call schedule_tool for the travel dates. If the baseline exceeds the budget, "
            "use the hotel/transport revision and supplied lower-cost alternative, then state any "
            "remaining shortfall. All costs and budget amounts are in INR. "
            "Use only sourced research as facts; label suggestions as suggestions. "
            f"Trip: {json.dumps(trip)}. Budget calculation: {json.dumps(budget)}. "
            f"Alternative: {json.dumps(alternative)}. Collected research: {json.dumps(research, ensure_ascii=False)}"
        ),
        expected_output="A dated itinerary with attractions, pacing, transport/hotel notes, and budget-aware revisions.",
        agent=itinerary_planner,
        context=[destination_task, lodging_transport_task, budget_task, budget_revision_task],
    )
    final_task = Task(
        description=(
            "Deliver the customer's complete travel plan by integrating the dependent task outputs. "
            "Include day-by-day itinerary, attractions, accommodation and transport options, the "
            "itemized estimated expenses, budget comparison, cheaper alternatives if needed, and "
            "a source list. Never imply any option is booked or that mock prices are live quotes. "
            "Show all cost amounts in INR (Indian rupees). "
            f"Customer constraints: {json.dumps(trip)}. "
            f"Verified calculation: {json.dumps(budget)}. Alternative: {json.dumps(alternative)}. "
            f"Source URLs: {json.dumps(research)}"
        ),
        expected_output="A complete, well-structured travel plan meeting all customer requirements.",
        agent=coordinator,
        context=[
            coordinator_intake,
            destination_task,
            lodging_transport_task,
            budget_task,
            budget_revision_task,
            itinerary_task,
        ],
    )
    return Crew(
        agents=[
            coordinator,
            destination_researcher,
            hotel_transport_agent,
            budget_analyst,
            itinerary_planner,
        ],
        tasks=[
            coordinator_intake,
            destination_task,
            lodging_transport_task,
            budget_task,
            budget_revision_task,
            itinerary_task,
            final_task,
        ],
        process=Process.sequential,
        verbose=False,
    )
