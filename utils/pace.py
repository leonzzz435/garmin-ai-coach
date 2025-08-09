def meters_per_second_to_kmh(speed_ms: float) -> float:
    if not speed_ms or speed_ms == 0:
        return 0.0
    return round(speed_ms * 3.6, 2)


def kmh_to_meters_per_second(speed_kmh: float) -> float:
    if not speed_kmh or speed_kmh == 0:
        return 0.0
    return round(speed_kmh / 3.6, 3)


def meters_per_second_to_min_per_km(speed_ms: float) -> tuple[int, int]:
    if not speed_ms or speed_ms == 0:
        return (0, 0)

    # Convert to minutes per kilometer
    pace_decimal = (1000 / speed_ms) / 60
    minutes = int(pace_decimal)
    seconds = int((pace_decimal - minutes) * 60)
    return (minutes, seconds)


def min_per_km_to_meters_per_second(minutes: int, seconds: int) -> float:
    if minutes == 0 and seconds == 0:
        return 0.0
    total_seconds = (minutes * 60) + seconds
    return round(1000 / total_seconds, 3)


def meters_per_second_to_min_per_mile(speed_ms: float) -> tuple[int, int]:
    if not speed_ms or speed_ms == 0:
        return (0, 0)

    # Convert to minutes per mile (1 mile = 1609.34 meters)
    pace_decimal = (1609.34 / speed_ms) / 60
    minutes = int(pace_decimal)
    seconds = int((pace_decimal - minutes) * 60)
    return (minutes, seconds)


def min_per_mile_to_meters_per_second(minutes: int, seconds: int) -> float:
    if minutes == 0 and seconds == 0:
        return 0.0
    total_seconds = (minutes * 60) + seconds
    return round(1609.34 / total_seconds, 3)
