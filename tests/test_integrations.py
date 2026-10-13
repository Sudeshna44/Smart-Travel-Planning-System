from datetime import date, timedelta

import integrations


def test_weather_skips_api_for_dates_beyond_forecast_window(monkeypatch):
    today = date(2026, 10, 13)
    monkeypatch.setattr(integrations, "_current_date", lambda: today)
    monkeypatch.setattr(
        integrations.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("API should not be called")),
    )

    result = integrations.weather_forecast(
        "Goa",
        (today + timedelta(days=30)).isoformat(),
        (today + timedelta(days=35)).isoformat(),
    )

    assert result["status"] == "unavailable"
    assert result["forecast_available_until"] == (today + timedelta(days=15)).isoformat()
    assert "16-day forecast window" in result["error"]


def test_weather_truncates_trip_to_forecast_window(monkeypatch):
    today = date(2026, 10, 13)
    monkeypatch.setattr(integrations, "_current_date", lambda: today)
    monkeypatch.setattr(integrations, "_geocode", lambda place: {
        "name": place,
        "country": "India",
        "latitude": 15.5,
        "longitude": 73.8,
    })
    requested: dict[str, str] = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"daily": {"time": ["2026-10-20"]}}

    def fake_get(url, *, params, **kwargs):
        requested.update(params)
        return Response()

    monkeypatch.setattr(integrations.requests, "get", fake_get)
    result = integrations.weather_forecast(
        "Goa",
        (today + timedelta(days=7)).isoformat(),
        (today + timedelta(days=20)).isoformat(),
    )

    assert result["status"] == "partial"
    assert requested["end_date"] == (today + timedelta(days=15)).isoformat()
    assert "Forecast covers" in result["note"]


def test_route_skips_osrm_for_intercontinental_trip(monkeypatch):
    locations = {
        "Boston": {"latitude": 42.36, "longitude": -71.06},
        "Goa": {"latitude": 15.5, "longitude": 73.8},
    }
    monkeypatch.setattr(integrations, "_geocode", lambda place: locations[place])
    monkeypatch.setattr(
        integrations.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("OSRM should not be called")),
    )

    result = integrations.route_estimate("Boston", "Goa")

    assert result["status"] == "unavailable"
    assert result["direct_distance_km"] > integrations.MAX_DRIVING_DISTANCE_KM
    assert "flight or long-distance transport" in result["error"]


def test_route_still_uses_osrm_for_local_trip(monkeypatch):
    locations = {
        "Boston": {"latitude": 42.36, "longitude": -71.06},
        "Providence": {"latitude": 41.82, "longitude": -71.41},
    }
    monkeypatch.setattr(integrations, "_geocode", lambda place: locations[place])
    requested = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"routes": [{"distance": 80000, "duration": 3600}]}

    def fake_get(url, **kwargs):
        requested.append(url)
        return Response()

    monkeypatch.setattr(integrations.requests, "get", fake_get)

    result = integrations.route_estimate("Boston", "Providence")

    assert result["status"] == "ok"
    assert result["distance_km"] == 80.0
    assert len(requested) == 1
