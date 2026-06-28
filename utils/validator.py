from config.constants import VALID_AIRFLOW_MODES, VALID_FAN_SPEEDS, VALID_WINDOWS, VALID_ZONES, VALID_SEAT_TYPE, VALID_LIGHT_TYPES


def validate_vehicle_action(action: str, parameters: dict | None) -> str | None:
    """
    Returns:
        None -> validation passed.
        str  -> validation error message.
    """

    parameters = parameters or {}

    # Climate action validation
    if action == "set_temperature":
        zone = parameters.get("zone")
        temperature = parameters.get("temperature")

        if zone not in VALID_ZONES:
            return "Invalid climate zone."

        if not isinstance(temperature, (int, float)):
            return "Invalid temperature."

        if not (16 <= temperature <= 30):
            return "Temperature must be between 16 and 30."

    elif action == "set_fan_speed":
        speed = parameters.get("speed")

        if speed not in VALID_FAN_SPEEDS:
            return "Invalid fan speed."

    elif action == "set_airflow_mode":
        mode = parameters.get("mode")

        if mode not in VALID_AIRFLOW_MODES:
            return "Invalid airflow mode."

    elif action == "climate_auto":
        enabled = parameters.get("enabled")

        if not isinstance(enabled, bool):
            return "Invalid auto mode."

    elif action == "climate_sync":
        enabled = parameters.get("enabled")

        if not isinstance(enabled, bool):
            return "Invalid sync mode."

    # Window action validation
    elif action in {"window_open", "window_close"}:
        window = parameters.get("window")
        percentage = parameters.get("percentage")

        if window not in VALID_WINDOWS:
            return "Invalid window."

        if not isinstance(percentage, int):
            return "Invalid percentage."

        if not (0 <= percentage <= 100):
            return "Percentage must be between 0 and 100."

    # Media action validation
    elif action == "set_volume":
        change = parameters.get("change")

        if not isinstance(change, int):
            return "Invalid volume change."

        if not (-100 <= change <= 100):
            return "Volume change must be between -100 and 100."

    elif action in ("seat_position", "seat_recline","seat_height"):
        seat = parameters.get("seat")
        percentage = parameters.get("percentage")

        if seat not in VALID_SEAT_TYPE:
            return "not supported seat"

        if not isinstance(percentage, int):
            return "Invalid percentage."

        if action == "seat_recline" and not (-90 <= percentage <= 100):
            return "Percentage must be between -90 and 100"

        if action in ("seat_position", "seat_height") and not (-0 <= percentage <= 100):
            return "Percentage must be between 0 and 100"


    elif action in ("reading_light_on", "reading_light_off"):
        light = parameters.get("light")

        if light not in VALID_LIGHT_TYPES:
            return "not supported light"

    return None
