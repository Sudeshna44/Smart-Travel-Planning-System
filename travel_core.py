"""Input validation and deterministic travel-budget calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math


@dataclass(frozen=True)
class TripRequest:
    destination: str
    origin: str
    start_date: date
    end_date: date
    budget: float
    interests: tuple[str, ...]
    travelers: int
    hotel_per_room_night: float
    transport_per_traveler: float
    daily_spend_per_traveler: float

    @property
    def nights(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def days(self) -> int:
        return self.nights + 1

    @property
    def rooms(self) -> int:
        return math.ceil(self.travelers / 2)

    def to_dict(self) -> dict[str, object]:
        return {
            "destination": self.destination,
            "origin": self.origin,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "nights": self.nights,
            "days": self.days,
            "budget_inr": self.budget,
            "interests": list(self.interests),
            "travelers": self.travelers,
            "rooms": self.rooms,
            "hotel_per_room_night_inr": self.hotel_per_room_night,
            "transport_per_traveler_inr": self.transport_per_traveler,
            "daily_spend_per_traveler_inr": self.daily_spend_per_traveler,
        }


def make_trip_request(
    *,
    destination: str,
    origin: str,
    start_date: date,
    end_date: date,
    budget: float,
    interests: tuple[str, ...],
    travelers: int,
    hotel_per_room_night: float,
    transport_per_traveler: float,
    daily_spend_per_traveler: float,
) -> TripRequest:
    """Validate user input and return a normalized trip request."""
    destination = destination.strip()
    origin = origin.strip()
    if not destination:
        raise ValueError("Enter a travel destination.")
    if not origin:
        raise ValueError("Enter a starting location.")
    if end_date <= start_date:
        raise ValueError("The return date must be after the departure date.")
    if not interests:
        raise ValueError("Choose at least one preferred activity.")
    if isinstance(travelers, bool) or travelers < 1:
        raise ValueError("Travelers must be at least one.")

    amounts = {
        "Total budget": budget,
        "Hotel estimate": hotel_per_room_night,
        "Transport estimate": transport_per_traveler,
        "Daily spending estimate": daily_spend_per_traveler,
    }
    for label, amount in amounts.items():
        if not math.isfinite(amount) or amount < 0:
            raise ValueError(f"{label} must be a finite, non-negative amount.")
    if budget <= 0:
        raise ValueError("Total budget must be greater than zero.")
    if hotel_per_room_night <= 0:
        raise ValueError("Hotel estimate must be greater than zero.")

    return TripRequest(
        destination=destination,
        origin=origin,
        start_date=start_date,
        end_date=end_date,
        budget=float(budget),
        interests=tuple(interest.strip() for interest in interests if interest.strip()),
        travelers=int(travelers),
        hotel_per_room_night=float(hotel_per_room_night),
        transport_per_traveler=float(transport_per_traveler),
        daily_spend_per_traveler=float(daily_spend_per_traveler),
    )


def format_inr(amount: float) -> str:
    """Format rupees using Indian digit grouping, for example ₹1,23,456.00."""
    formatted = f"{abs(amount):.2f}"
    whole, decimals = formatted.split(".")
    if len(whole) > 3:
        last_group = whole[-3:]
        leading = whole[:-3]
        groups: list[str] = []
        while leading:
            groups.insert(0, leading[-2:])
            leading = leading[:-2]
        whole = f"{','.join(groups)},{last_group}"
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{whole}.{decimals}"


def calculate_trip_budget(
    *,
    hotel_per_room_night: float,
    rooms: int,
    nights: int,
    transport_per_traveler: float,
    travelers: int,
    daily_spend_per_traveler: float,
    days: int,
) -> dict[str, float]:
    """Calculate a transparent INR estimate from explicit user-editable assumptions."""
    values = (
        hotel_per_room_night,
        transport_per_traveler,
        daily_spend_per_traveler,
    )
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Cost assumptions must be finite and non-negative.")
    if rooms < 1 or travelers < 1 or nights < 0 or days < 1:
        raise ValueError("Rooms, travelers, nights, or trip days are invalid.")

    hotel = hotel_per_room_night * rooms * nights
    transport = transport_per_traveler * travelers
    daily = daily_spend_per_traveler * travelers * days
    return {
        "hotel_inr": round(hotel, 2),
        "transport_inr": round(transport, 2),
        "food_activities_local_transport_inr": round(daily, 2),
        "total_inr": round(hotel + transport + daily, 2),
    }


def budget_alternative(request: TripRequest) -> dict[str, object]:
    """Estimate a lower-cost plan without claiming that it will meet the budget."""
    lower_hotel = min(request.hotel_per_room_night, 5400.0)
    lower_transport = request.transport_per_traveler * 0.7
    lower_daily = max(2490.0, request.daily_spend_per_traveler * 0.7)
    estimate = calculate_trip_budget(
        hotel_per_room_night=lower_hotel,
        rooms=request.rooms,
        nights=request.nights,
        transport_per_traveler=lower_transport,
        travelers=request.travelers,
        daily_spend_per_traveler=lower_daily,
        days=request.days,
    )
    return {
        "assumptions": {
            "hotel_per_room_night_inr": round(lower_hotel, 2),
            "transport_per_traveler_inr": round(lower_transport, 2),
            "daily_spend_per_traveler_inr": round(lower_daily, 2),
        },
        "estimate": estimate,
        "fits_budget": estimate["total_inr"] <= request.budget,
    }


def day_schedule(start_date: date, days: int) -> list[str]:
    if days < 1:
        raise ValueError("A trip must include at least one day.")
    return [(start_date + timedelta(days=offset)).isoformat() for offset in range(days)]
