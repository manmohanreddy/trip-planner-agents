"""Diagnostic logging setup.

This is for diagnostics only (retries, timeouts, stage failures, intake
validation errors) -- the chat turns, itinerary, and metrics table are the
product's UI and stay as direct print() calls, not logging.
"""

import logging
import sys


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )
