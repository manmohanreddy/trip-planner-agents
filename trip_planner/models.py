"""Structured intake contract between INTAKE_PROMPT and cli.py.

Kept to a str-in/str-out boundary deliberately: only cli.py's intake parsing
deals in TripBrief objects. agent.py's prompts and orchestrator.py's
signatures still take a plain trip-brief string (via to_prompt_text()), so
this validation improvement doesn't ripple through the whole pipeline.
"""

from pydantic import BaseModel, Field


class TripBrief(BaseModel):
    origin: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    travel_dates: str = Field(min_length=1)
    travelers: int = Field(ge=1, default=1)
    budget: str = Field(min_length=1)
    interests: list[str] = Field(default_factory=list)

    def to_prompt_text(self) -> str:
        interests = ", ".join(self.interests) if self.interests else "no specific preference"
        return (
            f"Origin: {self.origin}\n"
            f"Destination: {self.destination}\n"
            f"Dates: {self.travel_dates}\n"
            f"Travelers: {self.travelers}\n"
            f"Budget: {self.budget}\n"
            f"Interests: {interests}"
        )
