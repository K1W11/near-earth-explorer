"""Sky-gazing look-angle calculations for Near Earth Explorer.

This module is the orbital-mechanics boundary between a satellite's published
CelesTrak TLE and the frontend's observer-centered map. SGP4 produces a TEME
position, which is rotated to Earth-fixed coordinates, differenced against a
WGS-84 observer position, and projected into the local east/north/up horizon.
The output is azimuth, elevation, range, and a compass direction for the API.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from sgp4.api import SGP4_ERRORS, Satrec, jday

DEFAULT_OBSERVER_LATITUDE = 43.0008
"""Latitude of the default observer at Davis Hall, University at Buffalo."""

DEFAULT_OBSERVER_LONGITUDE = -78.7889
"""Longitude of the default observer at Davis Hall, University at Buffalo."""

_WGS84_EQUATORIAL_RADIUS_KM = 6378.137
_WGS84_ECCENTRICITY_SQUARED = 6.69437999014e-3


def _julian_date(moment: datetime) -> float:
    """Return a UTC Julian date suitable for the SGP4 propagation API."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    utc_moment = moment.astimezone(timezone.utc)
    jd, fraction = jday(
        utc_moment.year,
        utc_moment.month,
        utc_moment.day,
        utc_moment.hour,
        utc_moment.minute,
        utc_moment.second + utc_moment.microsecond / 1_000_000,
    )
    return jd + fraction


def _greenwich_mean_sidereal_time(julian_date: float) -> float:
    """Calculate Greenwich Mean Sidereal Time in radians for TEME conversion.

    The SGP4 library reports positions in the True Equator, Mean Equinox frame.
    For the horizon calculation we apply the standard GMST rotation from TEME
    to the Earth-fixed frame (the usual TEME-to-PEF approximation).
    """
    centuries = (julian_date - 2_451_545.0) / 36_525.0
    degrees = (
        280.46061837
        + 360.98564736629 * (julian_date - 2_451_545.0)
        + 0.000387933 * centuries**2
        - centuries**3 / 38_710_000.0
    )
    return math.radians(degrees % 360.0)


def _teme_to_ecef(position_teme_km: tuple[float, float, float], gmst: float) -> tuple[float, float, float]:
    """Rotate a TEME/ECI position into Earth-fixed coordinates around Z."""
    x_teme, y_teme, z_teme = position_teme_km
    cosine = math.cos(gmst)
    sine = math.sin(gmst)
    # Earth-fixed longitude lags inertial right ascension by sidereal rotation.
    return (
        cosine * x_teme + sine * y_teme,
        -sine * x_teme + cosine * y_teme,
        z_teme,
    )


def _observer_ecef(
    latitude_deg: float,
    longitude_deg: float,
    altitude_m: float,
) -> tuple[float, float, float]:
    """Convert WGS-84 geodetic latitude/longitude/altitude to ECEF kilometers."""
    latitude = math.radians(latitude_deg)
    longitude = math.radians(longitude_deg)
    altitude_km = altitude_m / 1000.0
    sin_latitude = math.sin(latitude)
    cos_latitude = math.cos(latitude)
    prime_vertical_radius = _WGS84_EQUATORIAL_RADIUS_KM / math.sqrt(
        1.0 - _WGS84_ECCENTRICITY_SQUARED * sin_latitude**2
    )
    return (
        (prime_vertical_radius + altitude_km) * cos_latitude * math.cos(longitude),
        (prime_vertical_radius + altitude_km) * cos_latitude * math.sin(longitude),
        (
            prime_vertical_radius * (1.0 - _WGS84_ECCENTRICITY_SQUARED)
            + altitude_km
        )
        * sin_latitude,
    )


def _ecef_to_enu(
    relative_ecef_km: tuple[float, float, float],
    latitude_deg: float,
    longitude_deg: float,
) -> tuple[float, float, float]:
    """Project an ECEF relative-position vector into local east/north/up axes."""
    latitude = math.radians(latitude_deg)
    longitude = math.radians(longitude_deg)
    x, y, z = relative_ecef_km
    sin_latitude = math.sin(latitude)
    cos_latitude = math.cos(latitude)
    sin_longitude = math.sin(longitude)
    cos_longitude = math.cos(longitude)

    # These basis vectors rotate the Earth-fixed difference vector to the
    # observer's tangent plane: east, north, then the local vertical.
    east = -sin_longitude * x + cos_longitude * y
    north = (
        -sin_latitude * cos_longitude * x
        - sin_latitude * sin_longitude * y
        + cos_latitude * z
    )
    up = (
        cos_latitude * cos_longitude * x
        + cos_latitude * sin_longitude * y
        + sin_latitude * z
    )
    return east, north, up


def _compass_direction(azimuth_deg: float) -> str:
    """Map an azimuth to one of eight human-readable compass directions."""
    directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return directions[int((azimuth_deg + 22.5) // 45.0) % len(directions)]


def calculate_look_angles(
    tle_line1: str,
    tle_line2: str,
    latitude_deg: float = DEFAULT_OBSERVER_LATITUDE,
    longitude_deg: float = DEFAULT_OBSERVER_LONGITUDE,
    altitude_m: float = 0.0,
    at: datetime | None = None,
    satellite_name: str | None = None,
) -> dict[str, Any]:
    """Propagate a TLE and return topocentric look angles for an observer.

    Args:
        tle_line1: First line of a satellite Two-Line Element set.
        tle_line2: Second line of the same TLE set.
        latitude_deg: WGS-84 observer latitude, from -90 to +90 degrees.
        longitude_deg: WGS-84 observer longitude, from -180 to +180 degrees.
        altitude_m: Observer altitude above the WGS-84 ellipsoid in meters.
        at: UTC propagation instant; a naive datetime is interpreted as UTC.
        satellite_name: Optional name carried into the API result.

    Returns:
        A JSON-ready mapping with azimuth, elevation, range, compass direction,
        line-of-sight visibility, observer coordinates, and calculation time.

    Raises:
        ValueError: If coordinates are outside valid ranges or SGP4 rejects the
            TLE/epoch propagation. Request-level shape validation is provided by
            the FastAPI/Pydantic models in ``main.py``.
    """
    if not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg must be between -90 and 90 degrees")
    if not -180.0 <= longitude_deg <= 180.0:
        raise ValueError("longitude_deg must be between -180 and 180 degrees")
    if altitude_m < -500.0:
        raise ValueError("altitude_m must be at least -500 meters")
    if not tle_line1.startswith("1 ") or not tle_line2.startswith("2 "):
        raise ValueError("A valid TLE line 1 and line 2 are required")

    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)

    satellite = Satrec.twoline2rv(tle_line1, tle_line2)
    jd, fraction = jday(
        moment.year,
        moment.month,
        moment.day,
        moment.hour,
        moment.minute,
        moment.second + moment.microsecond / 1_000_000,
    )

    # SGP4 propagates the TLE's mean elements to TEME position (kilometers).
    error_code, position_teme_km, _velocity_km_s = satellite.sgp4(jd, fraction)
    if error_code:
        raise ValueError(f"SGP4 propagation failed: {SGP4_ERRORS.get(error_code, error_code)}")

    ecef_satellite = _teme_to_ecef(
        (position_teme_km[0], position_teme_km[1], position_teme_km[2]),
        _greenwich_mean_sidereal_time(jd + fraction),
    )
    ecef_observer = _observer_ecef(latitude_deg, longitude_deg, altitude_m)
    relative_ecef = tuple(
        satellite_component - observer_component
        for satellite_component, observer_component in zip(ecef_satellite, ecef_observer)
    )
    east, north, up = _ecef_to_enu(relative_ecef, latitude_deg, longitude_deg)

    # Azimuth is measured clockwise from true north; elevation is above the
    # observer's horizon plane; the norm is the slant range to the satellite.
    azimuth_deg = math.degrees(math.atan2(east, north)) % 360.0
    elevation_deg = math.degrees(math.atan2(up, math.hypot(east, north)))
    range_km = math.sqrt(east**2 + north**2 + up**2)

    return {
        "satellite_name": satellite_name,
        "azimuth_deg": round(azimuth_deg, 3),
        "elevation_deg": round(elevation_deg, 3),
        "range_km": round(range_km, 3),
        "compass_direction": _compass_direction(azimuth_deg),
        "visible": elevation_deg > 0.0,
        "observer": {
            "latitude": latitude_deg,
            "longitude": longitude_deg,
            "altitude_m": altitude_m,
        },
        "calculated_at": moment.isoformat(),
    }
