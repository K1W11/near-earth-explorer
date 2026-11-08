"""Structured satellite facts and deterministic narration messages."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from look_angles import calculate_altitude_km


def _epoch_text(line1: str) -> str:
    try:
        year = int(line1[18:20])
        day = float(line1[20:32])
    except (IndexError, ValueError):
        return "No info"
    full_year = 2000 + year if year < 57 else 1900 + year
    epoch = datetime(full_year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)
    return epoch.strftime("%B %-d, %Y at %H:%M UTC")


def satellite_overview(record: dict[str, str]) -> dict[str, Any]:
    """Return display-ready structured facts derived from one satellite TLE."""
    line1 = record["tle1"]
    line2 = record["tle2"]
    try:
        mean_motion = float(line2[52:63])
    except (IndexError, ValueError):
        mean_motion = None
    if mean_motion is not None and not math.isfinite(mean_motion):
        mean_motion = None
    try:
        eccentricity = float(f"0.{line2[26:33]}")
    except (IndexError, ValueError):
        eccentricity = None
    if eccentricity is not None and not math.isfinite(eccentricity):
        eccentricity = None
    try:
        altitude_km = round(calculate_altitude_km(line1, line2), 1)
    except (IndexError, ValueError):
        altitude_km = None
    orbit_class = (
        "LEO" if altitude_km is not None and altitude_km < 2_000 else
        "MEO" if altitude_km is not None and altitude_km < 35_286 else
        "GEO" if altitude_km is not None and altitude_km < 36_286 else
        "HEO" if altitude_km is not None else "No info"
    )
    orbit_description = {
        "LEO": "Low Earth orbit",
        "MEO": "Medium Earth orbit",
        "GEO": "Geostationary region",
        "HEO": "Highly elliptical orbit",
    }[orbit_class]
    return {
        "name": record["name"],
        "norad_catalog_number": line1[2:7].strip(),
        "classification": line1[7:8],
        "international_designator": line1[9:17].strip(),
        "elements_epoch": _epoch_text(line1),
        "altitude_km": altitude_km,
        "orbit_class": orbit_class if altitude_km is not None else "No info",
        "orbit_description": orbit_description if altitude_km is not None else "Orbital data unavailable",
        "orbital_period_minutes": round(1_440 / mean_motion, 1) if mean_motion else None,
        "inclination_degrees": _float_field(line2, 8, 16, 2),
        "eccentricity": eccentricity,
        "right_ascension_ascending_node_degrees": _float_field(line2, 17, 25, 2),
        "argument_of_perigee_degrees": _float_field(line2, 34, 42, 2),
        "mean_anomaly_degrees": _float_field(line2, 43, 51, 2),
        "mean_motion_revolutions_per_day": round(mean_motion, 8) if mean_motion is not None else None,
        "revolutions_at_epoch": line2[63:68].strip(),
        "tle1": line1,
        "tle2": line2,
    }


def _float_field(line: str, start: int, end: int, digits: int) -> float | None:
    """Parse one optional fixed-width TLE field."""
    try:
        value = float(line[start:end])
        return round(value, digits) if math.isfinite(value) else None
    except (IndexError, ValueError):
        return None


def format_satellite_message(
    overview: dict[str, Any],
    category: str = "overview",
) -> str:
    """Create a category-filtered satellite message for the speech provider."""
    def value_text(value: Any, suffix: str = "") -> str:
        return f"{value}{suffix}" if value is not None else "not available"

    if category == "orbital_position":
        return (
            f"{overview['name']} has an orbital inclination of "
            f"{value_text(overview['inclination_degrees'], ' degrees')}. Its right ascension "
            f"of the ascending node is {value_text(overview['right_ascension_ascending_node_degrees'], ' degrees')}, "
            f"its argument of perigee is {value_text(overview['argument_of_perigee_degrees'], ' degrees')}, "
            f"and its mean anomaly is {value_text(overview['mean_anomaly_degrees'], ' degrees')}."
        )
    if category == "tracking":
        return (
            f"{overview['name']} has NORAD catalog number "
            f"{overview['norad_catalog_number']}. Its international designator is "
            f"{overview['international_designator'] or 'not available'}, and its "
            f"orbital elements epoch is {overview['elements_epoch']}. "
            f"The recorded revolution number is {overview['revolutions_at_epoch']}."
        )
    if category != "overview":
        raise ValueError(f"Unsupported satellite narration category: {category}")
    period = overview["orbital_period_minutes"]
    period_text = "not available" if period is None else (
        f"{period / 60:.1f} hours" if period >= 60 else f"{period:.1f} minutes"
    )
    return (
        f"{overview['name']} is in {overview['orbit_description']}, "
        f"{'at an altitude of ' + format(overview['altitude_km'], '.1f') + ' kilometers' if overview['altitude_km'] is not None else 'its current altitude is not available'}. "
        f"Its orbital period is {period_text}, with an inclination of "
        f"{value_text(overview['inclination_degrees'], ' degrees')}. "
        f"Its eccentricity is {value_text(overview['eccentricity'])}, "
        f"with a mean motion of "
        f"{value_text(overview['mean_motion_revolutions_per_day'], ' revolutions per day')}. "
        f"The NORAD catalog number is {overview['norad_catalog_number']}."
    )
