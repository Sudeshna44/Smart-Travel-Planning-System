"""External research integrations and explicitly labeled prototype booking estimates."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
import math
from typing import Any
from urllib.parse import quote

import requests
from ddgs import DDGS

REQUEST_TIMEOUT_SECONDS = 12
USER_AGENT = "SmartTravelPlannerPrototype/1.0 (travel research demo)"
MAX_FORECAST_DAYS = 16
MAX_DRIVING_DISTANCE_KM = 1500


def _current_date() -> date:
    return date.today()


def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the web using DuckDuckGo; returned results are unverified third-party content."""
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as exc:
        return {"status": "unavailable", "error": f"Web search failed: {exc}", "results": []}

    items = [
        {
            "title": result.get("title", ""),
            "snippet": result.get("body", ""),
            "url": result.get("href", ""),
        }
        for result in results
    ]
    return {"status": "ok" if items else "empty", "results": items}


@lru_cache(maxsize=64)
def _geocode(place: str) -> dict[str, Any]:
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": place, "count": 1, "language": "en", "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError(f"No coordinates found for {place!r}.")
    item = results[0]
    return {
        "name": item.get("name", place),
        "country": item.get("country", ""),
        "latitude": item["latitude"],
        "longitude": item["longitude"],
    }


def weather_forecast(destination: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Fetch a forecast when Open-Meteo supports the requested travel dates."""
    source = "https://open-meteo.com/"
    try:
        trip_start = date.fromisoformat(start_date)
        trip_end = date.fromisoformat(end_date)
        today = _current_date()
        last_forecast_date = today + timedelta(days=MAX_FORECAST_DAYS - 1)
        if trip_end < trip_start:
            raise ValueError("The end date must be on or after the start date.")
        if trip_start < today:
            return {
                "status": "unavailable",
                "source": source,
                "error": "A weather forecast is not available for travel dates in the past.",
            }
        if trip_start > last_forecast_date:
            return {
                "status": "unavailable",
                "source": source,
                "forecast_available_until": last_forecast_date.isoformat(),
                "error": (
                    "These dates are beyond the 16-day forecast window. "
                    f"Check again closer to departure (forecast available through "
                    f"{last_forecast_date.isoformat()})."
                ),
            }
        forecast_end = min(trip_end, last_forecast_date)
        location = _geocode(destination)
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "timezone": "auto",
                "start_date": trip_start.isoformat(),
                "end_date": forecast_end.isoformat(),
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return {
            "status": "partial" if forecast_end < trip_end else "ok",
            "source": source,
            "location": location,
            "daily": response.json().get("daily", {}),
            "note": (
                f"Forecast covers {trip_start.isoformat()} through {forecast_end.isoformat()}."
                if forecast_end < trip_end
                else "Forecast availability depends on how soon the travel dates begin."
            ),
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
        return {
            "status": "unavailable",
            "source": source,
            "error": f"Weather lookup unavailable for these dates: {exc}",
        }


def route_estimate(origin: str, destination: str) -> dict[str, Any]:
    """Estimate driving distance/time using Open-Meteo geocoding and the OSRM demo service."""
    source = "https://project-osrm.org/"
    try:
        start = _geocode(origin)
        end = _geocode(destination)
        latitude_delta = math.radians(end["latitude"] - start["latitude"])
        longitude_delta = math.radians(end["longitude"] - start["longitude"])
        start_latitude = math.radians(start["latitude"])
        end_latitude = math.radians(end["latitude"])
        haversine = (
            math.sin(latitude_delta / 2) ** 2
            + math.cos(start_latitude)
            * math.cos(end_latitude)
            * math.sin(longitude_delta / 2) ** 2
        )
        direct_distance_km = 6371 * 2 * math.asin(math.sqrt(haversine))
        if direct_distance_km > MAX_DRIVING_DISTANCE_KM:
            return {
                "status": "unavailable",
                "source": source,
                "direct_distance_km": round(direct_distance_km, 1),
                "error": (
                    "A driving route estimate is not provided for destinations more than "
                    f"{MAX_DRIVING_DISTANCE_KM:,} km apart by direct distance. Use a flight or "
                    "long-distance transport provider for this trip."
                ),
            }
        coordinates = (
            f"{start['longitude']},{start['latitude']};"
            f"{end['longitude']},{end['latitude']}"
        )
        response = requests.get(
            f"https://router.project-osrm.org/route/v1/driving/{quote(coordinates, safe=',;')}",
            params={"overview": "false"},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        routes = response.json().get("routes", [])
        if not routes:
            raise ValueError("The routing service returned no driving route.")
        route = routes[0]
        return {
            "status": "ok",
            "source": source,
            "distance_km": round(route["distance"] / 1000, 1),
            "duration_hours": round(route["duration"] / 3600, 1),
            "note": "Driving route estimate only; it is not a flight or public-transit quote.",
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
        return {"status": "unavailable", "source": source, "error": f"Route lookup failed: {exc}"}


def mock_accommodation_options(
    destination: str, rooms: int, nights: int, nightly_budget: float
) -> dict[str, Any]:
    """Generate illustrative price bands, not live hotel availability or booking offers."""
    return {
        "status": "prototype_estimate",
        "destination": destination,
        "rooms": rooms,
        "nights": nights,
        "options": [
            {"style": "budget", "estimated_inr_per_room_night": 5400.0},
            {"style": "standard", "estimated_inr_per_room_night": round(nightly_budget, 2)},
            {"style": "higher-comfort", "estimated_inr_per_room_night": round(nightly_budget * 1.6, 2)},
        ],
        "note": "Illustrative estimates only; no booking API or live availability is connected.",
    }


def mock_transport_options(
    origin: str, destination: str, travelers: int, round_trip_per_traveler: float
) -> dict[str, Any]:
    """Generate editable transport allowances, not live schedules or fares."""
    return {
        "status": "prototype_estimate",
        "origin": origin,
        "destination": destination,
        "travelers": travelers,
        "options": [
            {"style": "lowest-cost allowance", "estimated_round_trip_inr_per_traveler": round(round_trip_per_traveler * 0.7, 2)},
            {"style": "user planning allowance", "estimated_round_trip_inr_per_traveler": round(round_trip_per_traveler, 2)},
            {"style": "flexible allowance", "estimated_round_trip_inr_per_traveler": round(round_trip_per_traveler * 1.5, 2)},
        ],
        "note": "Illustrative estimates only; no flight, rail, or booking API is connected.",
    }


def collect_research(
    origin: str, destination: str, start_date: str, end_date: str, interests: list[str]
) -> dict[str, Any]:
    """Collect independent source results before the agents plan around them."""
    query = (
        f"travel attractions local experiences in {destination} for "
        f"{', '.join(interests)}; hotels and transport from {origin}"
    )
    return {
        "web_search": web_search(query),
        "weather": weather_forecast(destination, start_date, end_date),
        "driving_route": route_estimate(origin, destination),
    }


def source_urls(research: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for result in research["web_search"].get("results", []):
        url = result.get("url")
        if url and url not in urls:
            urls.append(url)
    for key in ("weather", "driving_route"):
        url = research.get(key, {}).get("source")
        if url and url not in urls:
            urls.append(url)
    return urls
