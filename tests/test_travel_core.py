from datetime import date

import pytest

from travel_core import (
    budget_alternative,
    calculate_trip_budget,
    day_schedule,
    format_inr,
    make_trip_request,
)


def request(**overrides):
    values = {
        "destination": "Kyoto",
        "origin": "Boston",
        "start_date": date(2027, 4, 1),
        "end_date": date(2027, 4, 6),
        "budget": 250000,
        "interests": ("Culture", "Food"),
        "travelers": 2,
        "hotel_per_room_night": 10000,
        "transport_per_traveler": 25000,
        "daily_spend_per_traveler": 6000,
    }
    values.update(overrides)
    return make_trip_request(**values)


def test_budget_breakdown_uses_rooms_nights_and_travelers():
    trip = request()
    result = calculate_trip_budget(
        hotel_per_room_night=trip.hotel_per_room_night,
        rooms=trip.rooms,
        nights=trip.nights,
        transport_per_traveler=trip.transport_per_traveler,
        travelers=trip.travelers,
        daily_spend_per_traveler=trip.daily_spend_per_traveler,
        days=trip.days,
    )

    assert result == {
        "hotel_inr": 50000.0,
        "transport_inr": 50000.0,
        "food_activities_local_transport_inr": 72000.0,
        "total_inr": 172000.0,
    }


def test_trip_request_rejects_return_date_before_or_on_departure():
    with pytest.raises(ValueError, match="return date"):
        request(end_date=date(2027, 4, 1))


def test_trip_request_requires_at_least_one_interest():
    with pytest.raises(ValueError, match="activity"):
        request(interests=())


def test_trip_request_rejects_non_finite_cost_assumption():
    with pytest.raises(ValueError, match="finite"):
        request(transport_per_traveler=float("inf"))


def test_day_schedule_includes_each_calendar_day():
    assert day_schedule(date(2027, 4, 1), 3) == [
        "2027-04-01",
        "2027-04-02",
        "2027-04-03",
    ]


def test_lower_cost_alternative_reports_whether_it_meets_budget():
    trip = request(budget=120000)
    alternative = budget_alternative(trip)

    assert alternative["estimate"]["total_inr"] == 112400.0
    assert alternative["fits_budget"] is True


def test_format_inr_uses_indian_digit_grouping():
    assert format_inr(123456.5) == "₹1,23,456.50"
