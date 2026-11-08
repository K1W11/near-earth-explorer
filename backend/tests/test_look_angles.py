"""Numerical and integration-level checks for the SGP4 look-angle engine.

These tests cover the transformations between TLE-propagated TEME/ECI state,
Earth-fixed coordinates, and the observer's local ENU horizon. Fixed timestamps
near the ISS TLE epoch keep propagation deterministic and avoid dependence on
the current date.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from look_angles import (
    _cardinal_direction,
    _ecef_delta_to_enu,
    _eci_to_ecef,
    _greenwich_mean_sidereal_time,
    _observer_geodetic_to_ecef,
    calculate_look_angles,
)

UB_LATITUDE_DEG = 43.0008
UB_LONGITUDE_DEG = -78.7889
UB_ALTITUDE_M = 180.0

# Public ISS (ZARYA) TLE from the shared CelesTrak fixture. Its epoch is
# 2021-10-02 12:14:29 UTC, used as the deterministic propagation instant.
ISS_TLE_LINE_1 = (
    "1 25544U 98067A   21275.51005787  .00001446  00000-0  33231-4 0  9993"
)
ISS_TLE_LINE_2 = (
    "2 25544  51.6442 208.9163 0003886  92.4401  33.3421 15.48815329302845"
)
ISS_EPOCH = datetime(2021, 10, 2, 12, 14, 29, tzinfo=timezone.utc)
CARDINALS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def test_calculate_look_angles_valid_iss(mock_celestrak_payload: str) -> None:
    """Propagate the shared ISS TLE and validate API fields and sector mapping."""
    lines = mock_celestrak_payload.strip().splitlines()
    assert len(lines) == 3
    tle_line1, tle_line2 = lines[1], lines[2]

    result = calculate_look_angles(
        tle_line1,
        tle_line2,
        observer_lat=UB_LATITUDE_DEG,
        observer_lon=UB_LONGITUDE_DEG,
        observer_alt_m=UB_ALTITUDE_M,
        at=ISS_EPOCH,
        satellite_name="ISS (ZARYA)",
    )

    azimuth = result["azimuth"]
    elevation = result["elevation"]
    assert 0.0 <= azimuth <= 360.0
    assert -90.0 <= elevation <= 90.0
    assert result["range_km"] > 0.0
    assert result["cardinal_direction"] == CARDINALS[
        int((azimuth + 22.5) // 45) % 8
    ]
    assert {
        "formatted",
        "visible",
        "azimuth_deg",
        "elevation_deg",
        "compass_direction",
        "observer",
        "calculated_at",
    }.issubset(result)
    assert isinstance(result["visible"], bool)
    assert result["azimuth_deg"] == result["azimuth"]
    assert result["elevation_deg"] == result["elevation"]
    assert result["compass_direction"] == result["cardinal_direction"]

    # This fixed-time result is a regression check for SGP4 propagation as
    # well as the downstream GMST/ECEF/ENU calculation.
    assert result["azimuth"] == pytest.approx(322.47, abs=0.02)
    assert result["elevation"] == pytest.approx(-40.47, abs=0.02)
    assert result["range_km"] == pytest.approx(8916.48, abs=0.1)


def test_observer_ecef_math_correctness() -> None:
    """Compare Davis Hall ECEF output with independently calculated WGS-84 values.

    At 43.0008 degrees north and 78.7889 degrees west, WGS-84 yields
    approximately X=908.36 km, Y=-4582.87 km, Z=4327.69 km at 180 m altitude.
    These values follow the stated ellipsoid equations; the originally supplied
    X/Y estimates do not correspond to the specified UB latitude/longitude.
    """
    latitude = math.radians(UB_LATITUDE_DEG)
    longitude = math.radians(UB_LONGITUDE_DEG)
    actual = _observer_geodetic_to_ecef(latitude, longitude, 0.18)

    semi_major_axis_km = 6378.137
    flattening = 1.0 / 298.257223563
    eccentricity_squared = flattening * (2.0 - flattening)
    prime_vertical_radius_km = semi_major_axis_km / math.sqrt(
        1.0 - eccentricity_squared * math.sin(latitude) ** 2
    )
    expected = (
        (prime_vertical_radius_km + 0.18)
        * math.cos(latitude)
        * math.cos(longitude),
        (prime_vertical_radius_km + 0.18)
        * math.cos(latitude)
        * math.sin(longitude),
        (
            prime_vertical_radius_km * (1.0 - eccentricity_squared)
            + 0.18
        )
        * math.sin(latitude),
    )

    assert actual == pytest.approx(expected, rel=1e-3)
    assert actual == pytest.approx(
        (908.35548, -4582.87047, 4327.68952),
        abs=0.01,
    )


def test_eci_to_ecef_gmst_rotation() -> None:
    """Verify GMST's Earth-rotation sign and its effect on a known vector."""
    gmst_rad = math.pi / 2.0
    actual = _eci_to_ecef((1000.0, 0.0, 500.0), gmst_rad)
    assert actual == pytest.approx((0.0, -1000.0, 500.0), abs=1e-12)

    # J2000.0 is a published reference epoch for the GMST polynomial.
    expected_j2000_gmst = math.radians(280.46061837)
    assert _greenwich_mean_sidereal_time(2451545.0) == pytest.approx(
        expected_j2000_gmst,
        abs=1e-12,
    )


def test_ecef_delta_to_enu_and_look_angle_equations() -> None:
    """Check ENU basis directions and the range/azimuth/elevation definitions."""
    # At the equator and Greenwich, ECEF +Y is local east, +Z is north, and
    # +X is up. These orthogonal tests detect sign or axis-order regressions.
    assert _ecef_delta_to_enu((0.0, 1.0, 0.0), 0.0, 0.0) == pytest.approx(
        (1.0, 0.0, 0.0)
    )
    assert _ecef_delta_to_enu((0.0, 0.0, 1.0), 0.0, 0.0) == pytest.approx(
        (0.0, 1.0, 0.0)
    )
    assert _ecef_delta_to_enu((1.0, 0.0, 0.0), 0.0, 0.0) == pytest.approx(
        (0.0, 0.0, 1.0)
    )

    east_km, north_km, up_km = (3.0, 4.0, 12.0)
    range_km = math.sqrt(east_km**2 + north_km**2 + up_km**2)
    elevation_deg = math.degrees(math.asin(up_km / range_km))
    azimuth_deg = math.degrees(math.atan2(east_km, north_km)) % 360.0
    assert range_km == pytest.approx(13.0)
    assert elevation_deg == pytest.approx(math.degrees(math.asin(12.0 / 13.0)))
    assert 0.0 <= azimuth_deg < 360.0
    assert -90.0 <= elevation_deg <= 90.0
    assert _cardinal_direction(azimuth_deg) == "NE"


@pytest.mark.parametrize(
    ("latitude", "longitude", "altitude_m"),
    [
        (95.0, UB_LONGITUDE_DEG, UB_ALTITUDE_M),
        (-91.0, UB_LONGITUDE_DEG, UB_ALTITUDE_M),
        (UB_LATITUDE_DEG, 185.0, UB_ALTITUDE_M),
        (UB_LATITUDE_DEG, UB_LONGITUDE_DEG, -600.0),
    ],
)
def test_look_angles_invalid_coordinates(
    latitude: float,
    longitude: float,
    altitude_m: float,
) -> None:
    """Reject observers outside supported latitude, longitude, or altitude bounds."""
    with pytest.raises(ValueError, match="observer_"):
        calculate_look_angles(
            ISS_TLE_LINE_1,
            ISS_TLE_LINE_2,
            observer_lat=latitude,
            observer_lon=longitude,
            observer_alt_m=altitude_m,
            at=ISS_EPOCH,
        )


@pytest.mark.parametrize(
    ("tle_line1", "tle_line2"),
    [
        ("corrupted line 1", ISS_TLE_LINE_2),
        (ISS_TLE_LINE_1, "corrupted line 2"),
    ],
)
def test_look_angles_invalid_tle_format(tle_line1: str, tle_line2: str) -> None:
    """Reject element lines missing the required TLE line-number prefixes."""
    with pytest.raises(ValueError, match="TLE"):
        calculate_look_angles(
            tle_line1,
            tle_line2,
            observer_lat=UB_LATITUDE_DEG,
            observer_lon=UB_LONGITUDE_DEG,
            observer_alt_m=UB_ALTITUDE_M,
            at=ISS_EPOCH,
        )


def test_look_angles_timestamp_normalization() -> None:
    """Ensure naive timestamps are interpreted as UTC like UTC-aware timestamps."""
    utc_instant = datetime(2021, 10, 2, 12, 14, 29, tzinfo=timezone.utc)
    naive_instant = datetime(2021, 10, 2, 12, 14, 29)

    utc_result = calculate_look_angles(
        ISS_TLE_LINE_1,
        ISS_TLE_LINE_2,
        observer_lat=UB_LATITUDE_DEG,
        observer_lon=UB_LONGITUDE_DEG,
        observer_alt_m=UB_ALTITUDE_M,
        at=utc_instant,
    )
    naive_result = calculate_look_angles(
        ISS_TLE_LINE_1,
        ISS_TLE_LINE_2,
        observer_lat=UB_LATITUDE_DEG,
        observer_lon=UB_LONGITUDE_DEG,
        observer_alt_m=UB_ALTITUDE_M,
        at=naive_instant,
    )

    assert naive_result["azimuth"] == utc_result["azimuth"]
    assert naive_result["elevation"] == utc_result["elevation"]
    assert naive_result["range_km"] == utc_result["range_km"]
    assert utc_result["calculated_at"] == "2021-10-02T12:14:29+00:00"
    assert naive_result["calculated_at"] == utc_result["calculated_at"]