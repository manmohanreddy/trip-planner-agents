import pytest
from pydantic import ValidationError

from trip_planner.models import TripBrief


def test_valid_json_round_trips() -> None:
    payload = (
        '{"origin": "DFW", "destination": "FLL", "travel_dates": "Oct 12-14, 2026", '
        '"travelers": 1, "budget": "$250 total", "interests": ["beach", "food"]}'
    )

    brief = TripBrief.model_validate_json(payload)

    assert brief.origin == "DFW"
    assert brief.destination == "FLL"
    assert brief.travelers == 1
    assert brief.interests == ["beach", "food"]


def test_missing_required_field_raises() -> None:
    payload = '{"origin": "DFW", "travel_dates": "soon", "budget": "$250"}'

    with pytest.raises(ValidationError):
        TripBrief.model_validate_json(payload)


def test_travelers_must_be_int() -> None:
    payload = (
        '{"origin": "DFW", "destination": "FLL", "travel_dates": "soon", '
        '"travelers": "one", "budget": "$250"}'
    )

    with pytest.raises(ValidationError):
        TripBrief.model_validate_json(payload)


def test_to_prompt_text_includes_all_fields() -> None:
    brief = TripBrief(
        origin="DFW",
        destination="FLL",
        travel_dates="Oct 12-14, 2026",
        travelers=2,
        budget="$500",
        interests=["beach", "food"],
    )

    text = brief.to_prompt_text()

    for value in ["DFW", "FLL", "Oct 12-14, 2026", "2", "$500", "beach", "food"]:
        assert value in text


def test_to_prompt_text_no_interests_says_no_preference() -> None:
    brief = TripBrief(
        origin="DFW",
        destination="FLL",
        travel_dates="soon",
        travelers=1,
        budget="$250",
        interests=[],
    )

    assert "no specific preference" in brief.to_prompt_text()
