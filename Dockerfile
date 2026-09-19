# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRIP_PLANNER_OUTPUT_DIR=/app/output

WORKDIR /app

COPY pyproject.toml README.md ./
COPY trip_planner ./trip_planner
RUN pip install .

RUN useradd --create-home --uid 1000 tripplanner \
    && mkdir -p /app/output \
    && chown -R tripplanner:tripplanner /app
USER tripplanner

ENTRYPOINT ["trip-planner"]
