"""Only the pure extracted seam is unit-tested here -- gather_requirements()'s
input()/ClaudeSDKClient-driven loop is integration-shaped, not unit-shaped.
"""

import pytest
from pydantic import ValidationError

from trip_planner.cli import _extract_trip_brief


def test_non_ready_text_returns_none() -> None:
    assert _extract_trip_brief("What's your budget?") is None


def test_valid_ready_line_parses() -> None:
    text = (
        'READY: {"origin": "DFW", "destination": "FLL", "travel_dates": "Oct 12-14, 2026", '
        '"travelers": 1, "budget": "$250", "interests": []}'
    )

    brief = _extract_trip_brief(text)

    assert brief is not None
    assert brief.origin == "DFW"
    assert brief.destination == "FLL"


def test_malformed_ready_json_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        _extract_trip_brief("READY: {not valid json")
