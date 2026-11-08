"""Transform published satellite TLEs into an observer's local sky coordinates.

This module is the orbital-mechanics boundary between CelesTrak's published
Two-Line Element (TLE) sets and Near Earth Explorer's observer-centered map.
SGP4 parses each TLE and propagates the satellite's position in the
True-Equator, Mean-Equinox frame (TEME, commonly treated as the ECI frame for
this calculation). Greenwich Mean Sidereal Time rotates that inertial position
into an Earth-fixed (ECEF) position. The observer's WGS-84 geodetic location is
also converted to ECEF; subtracting the two positions gives the topocentric
line-of-sight vector. Finally, a rotation into the observer's local
East-North-Up (ENU) horizon frame yields azimuth, elevation, range, and compass
direction for the frontend.

The route layer in ``main.py`` supplies the selected satellite's TLE and user
location to ``calculate_look_angles``. Its response is directly JSON-ready,
with the display-oriented fields (``cardinal_direction`` and ``formatted``)
alongside compatibility aliases consumed by the existing API gateway.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict

from sgp4.api import Satrec, jday

_WGS84_SEMI_MAJOR_AXIS_KM = 6378.137
"""WGS-84 ellipsoid semi-major axis, in kilometers."""

_WGS84_FLATTENING = 1.0 / 298.257223563
"""WGS-84 ellipsoid flattening."""

_COMPASS_DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
"""Eight compass sectors in clockwise order, with north centered on 0 degrees."""


def _utc_julian_date(moment: datetime) -> tuple[float, float]:
    """Convert a datetime to the two-part UTC Julian date used by SGP4.

    Two-part Julian dates retain sub-day precision more reliably than combining
    the integer day and fractional day into one floating-point value. A naive
    datetime is interpreted as UTC; an aware datetime is normalized to UTC.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    utc_moment = moment.astimezone(timezone.utc)
    return jday(
        utc_moment.year,
        utc_moment.month,
        utc_moment.day,
        utc_moment.hour,
        utc_moment.minute,
        utc_moment.second + utc_moment.microsecond / 1_000_000.0,
    )


def calculate_altitude_km(
    tle_line1: str,
    tle_line2: str,
    *,
    at: datetime | None = None,
) -> float:
    """Propagate a TLE and return its geocentric altitude in kilometers."""
    if not tle_line1.startswith("1 ") or not tle_line2.startswith("2 "):
        raise ValueError("A valid TLE line 1 and line 2 are required")

    try:
        satellite = Satrec.twoline2rv(tle_line1, tle_line2)
    except ValueError as error:
        raise ValueError(f"Could not parse satellite TLE: {error}") from error

    moment = at if at is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    jd, fraction = _utc_julian_date(moment.astimezone(timezone.utc))
    error_code, position_eci_km, _ = satellite.sgp4(jd, fraction)
    if error_code != 0:
        raise ValueError(f"SGP4 propagation failed with error code {error_code}")

    distance_km = math.sqrt(sum(axis**2 for axis in position_eci_km))
    return max(0.0, distance_km - _WGS84_SEMI_MAJOR_AXIS_KM)


def _greenwich_mean_sidereal_time(julian_date: float) -> float:
    """Calculate Greenwich Mean Sidereal Time in radians.

    The polynomial is evaluated in Julian centuries from J2000.0. Its angle is
    reduced to one full turn before conversion to radians, giving the Earth
    rotation angle used to relate the satellite's TEME/ECI coordinates to the
    rotating Earth-fixed frame.
    """
    centuries = (julian_date - 2_451_545.0) / 36_525.0
    gmst_degrees = (
        280.46061837
        + 360.98564736629 * (julian_date - 2_451_545.0)
        + 0.000387933 * centuries**2
        - centuries**3 / 38_710_000.0
    ) % 360.0
    return math.radians(gmst_degrees)


def _observer_geodetic_to_ecef(
    latitude_rad: float,
    longitude_rad: float,
    altitude_km: float,
) -> tuple[float, float, float]:
    """Convert WGS-84 geodetic coordinates to Earth-centered ECEF kilometers.

    The prime-vertical radius accounts for the WGS-84 ellipsoid's flattening at
    the observer's latitude. The returned axes are Earth-fixed X at the
    equator/Greenwich meridian, Y at the equator/90 degrees east, and Z at the
    north pole.
    """
    eccentricity_squared = _WGS84_FLATTENING * (2.0 - _WGS84_FLATTENING)
    sin_latitude = math.sin(latitude_rad)
    cos_latitude = math.cos(latitude_rad)
    prime_vertical_radius_km = _WGS84_SEMI_MAJOR_AXIS_KM / math.sqrt(
        1.0 - eccentricity_squared * sin_latitude**2
    )
    radial_distance_km = prime_vertical_radius_km + altitude_km

    x_ecef = radial_distance_km * cos_latitude * math.cos(longitude_rad)
    y_ecef = radial_distance_km * cos_latitude * math.sin(longitude_rad)
    z_ecef = (
        prime_vertical_radius_km * (1.0 - eccentricity_squared) + altitude_km
    ) * sin_latitude
    return x_ecef, y_ecef, z_ecef


def _eci_to_ecef(
    position_eci_km: tuple[float, float, float],
    gmst_rad: float,
) -> tuple[float, float, float]:
    """Rotate a TEME/ECI position vector into the Earth-fixed frame.

    Earth-fixed longitude is behind inertial right ascension by GMST. Applying
    the corresponding negative Z-axis rotation gives ECEF X/Y while Z remains
    aligned with Earth's rotation axis. The result is the conventional
    TEME-to-pseudo-Earth-fixed (PEF) approximation used with TLE propagation.
    """
    x_eci, y_eci, z_eci = position_eci_km
    cos_gmst = math.cos(gmst_rad)
    sin_gmst = math.sin(gmst_rad)
    return (
        cos_gmst * x_eci + sin_gmst * y_eci,
        -sin_gmst * x_eci + cos_gmst * y_eci,
        z_eci,
    )


def _ecef_delta_to_enu(
    delta_ecef_km: tuple[float, float, float],
    latitude_rad: float,
    longitude_rad: float,
) -> tuple[float, float, float]:
    """Rotate an ECEF line-of-sight vector into local east/north/up axes.

    This is a rotation of the satellite-minus-observer ECEF vector (not a
    conversion of the satellite's absolute position). The observer's geodetic
    latitude defines the local vertical, and longitude defines the local east
    direction. ENU is a tangent plane: positive east, positive true north, and
    positive up away from the WGS-84 ellipsoid.
    """
    delta_x, delta_y, delta_z = delta_ecef_km
    sin_latitude = math.sin(latitude_rad)
    cos_latitude = math.cos(latitude_rad)
    sin_longitude = math.sin(longitude_rad)
    cos_longitude = math.cos(longitude_rad)

    east_km = -sin_longitude * delta_x + cos_longitude * delta_y
    north_km = (
        -sin_latitude * cos_longitude * delta_x
        - sin_latitude * sin_longitude * delta_y
        + cos_latitude * delta_z
    )
    up_km = (
        cos_latitude * cos_longitude * delta_x
        + cos_latitude * sin_longitude * delta_y
        + sin_latitude * delta_z
    )
    return east_km, north_km, up_km


def _cardinal_direction(azimuth_deg: float) -> str:
    """Map a clockwise-from-north azimuth to its nearest 8-point compass sector."""
    sector_index = int((azimuth_deg + 22.5) // 45.0) % len(_COMPASS_DIRECTIONS)
    return _COMPASS_DIRECTIONS[sector_index]


def calculate_look_angles(
    tle_line1: str,
    tle_line2: str,
    observer_lat: float,
    observer_lon: float,
    observer_alt_m: float = 180.0,
    *,
    at: datetime | None = None,
    satellite_name: str | None = None,
) -> Dict[str, Any]:
    """Propagate a TLE and calculate its topocentric look angles.

    Args:
        tle_line1: First line of a satellite Two-Line Element set.
        tle_line2: Second line of that same TLE set.
        observer_lat: WGS-84 observer latitude in degrees, in ``[-90, 90]``.
        observer_lon: WGS-84 observer longitude in degrees, in ``[-180, 180]``.
        observer_alt_m: Observer altitude above the ellipsoid, in meters.
            Defaults to 180 meters for the UB campus.
        at: Optional propagation instant. If omitted, the current UTC time is
            used. Naive datetimes are interpreted as UTC.
        satellite_name: Optional name included in the response for API callers.

    Returns:
        A JSON-ready mapping with ``azimuth``, ``elevation``, ``range_km``,
        ``cardinal_direction``, and a human-readable ``formatted`` summary.
        Compatibility fields (``azimuth_deg``, ``elevation_deg``,
        ``compass_direction``, ``visible``, and observer/time metadata) are also
        included for the existing FastAPI response schema.

    Raises:
        ValueError: If coordinates or TLE line labels are invalid, the observer
            and satellite positions coincide, SGP4 rejects propagation, or the
            TLE cannot be parsed.
    """
    if not math.isfinite(observer_lat) or not -90.0 <= observer_lat <= 90.0:
        raise ValueError("observer_lat must be a finite value between -90 and 90 degrees")
    if not math.isfinite(observer_lon) or not -180.0 <= observer_lon <= 180.0:
        raise ValueError("observer_lon must be a finite value between -180 and 180 degrees")
    if not math.isfinite(observer_alt_m) or observer_alt_m < -500.0:
        raise ValueError("observer_alt_m must be finite and at least -500 meters")
    if not tle_line1.startswith("1 ") or not tle_line2.startswith("2 "):
        raise ValueError("A valid TLE line 1 and line 2 are required")

    # Step 1: parse the element set and propagate its mean orbital elements.
    # SGP4 returns TEME position (kilometers) and velocity (kilometers/second).
    try:
        satellite = Satrec.twoline2rv(tle_line1, tle_line2)
    except ValueError as error:
        raise ValueError(f"Could not parse satellite TLE: {error}") from error

    moment = at if at is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    jd, fraction = _utc_julian_date(moment)
    error_code, position_eci_km, _ = satellite.sgp4(jd, fraction)
    if error_code != 0:
        raise ValueError(f"SGP4 propagation failed with error code {error_code}")

    # Step 2: convert the observer's geodetic location to WGS-84 Earth-fixed
    # coordinates. SGP4 uses kilometers, so convert the observer altitude too.
    latitude_rad = math.radians(observer_lat)
    longitude_rad = math.radians(observer_lon)
    observer_alt_km = observer_alt_m / 1000.0
    observer_ecef = _observer_geodetic_to_ecef(
        latitude_rad,
        longitude_rad,
        observer_alt_km,
    )

    # Step 3: GMST aligns the inertial satellite position with Earth's rotation.
    # The SGP4 TEME vector is transformed to the ECEF frame at the same instant.
    gmst_rad = _greenwich_mean_sidereal_time(jd + fraction)
    satellite_ecef = _eci_to_ecef(
        (position_eci_km[0], position_eci_km[1], position_eci_km[2]),
        gmst_rad,
    )

    # Step 4: subtract observer from satellite to obtain the relative
    # topocentric vector, then rotate it from ECEF into the observer's ENU frame.
    delta_ecef = (
        satellite_ecef[0] - observer_ecef[0],
        satellite_ecef[1] - observer_ecef[1],
        satellite_ecef[2] - observer_ecef[2],
    )
    east_km, north_km, up_km = _ecef_delta_to_enu(
        delta_ecef,
        latitude_rad,
        longitude_rad,
    )

    # Step 5: derive slant range and sky angles from the local horizon vector.
    # Clamp the arcsine input to its mathematical domain to absorb roundoff.
    range_km = math.sqrt(east_km**2 + north_km**2 + up_km**2)
    if range_km == 0.0:
        raise ValueError("Satellite position coincides with the observer position")
    elevation_deg = math.degrees(
        math.asin(max(-1.0, min(1.0, up_km / range_km)))
    )
    azimuth_deg = math.degrees(math.atan2(east_km, north_km)) % 360.0
    cardinal_direction = _cardinal_direction(azimuth_deg)

    # Keep numeric API fields precise to hundredths; the compact label rounds
    # azimuth and elevation to whole degrees for easy use in a sky-gazing prompt.
    azimuth = round(azimuth_deg, 2)
    elevation = round(elevation_deg, 2)
    rounded_range_km = round(range_km, 2)
    formatted = (
        f"{cardinal_direction} ({azimuth:.0f}°) at {elevation:.0f}° elevation"
    )

    return {
        "azimuth": azimuth,
        "elevation": elevation,
        "range_km": rounded_range_km,
        "cardinal_direction": cardinal_direction,
        "formatted": formatted,
        # Compatibility aliases preserve the currently documented API response.
        "satellite_name": satellite_name,
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "compass_direction": cardinal_direction,
        "visible": elevation_deg > 0.0,
        "observer": {
            "latitude": observer_lat,
            "longitude": observer_lon,
            "altitude_m": observer_alt_m,
        },
        "calculated_at": moment.isoformat(),
    }
