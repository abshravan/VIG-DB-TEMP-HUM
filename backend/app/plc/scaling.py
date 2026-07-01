def scale_raw_to_engineering(
    raw: float, raw_min: float, raw_max: float, eng_min: float, eng_max: float
) -> float:
    """Linear conversion from PLC raw counts to engineering units, e.g. an S7-1200
    analog input's 0-27648 raw range mapped to a 0-50 °C sensor span.
    """
    if raw_max == raw_min:
        raise ValueError("raw_max must differ from raw_min")
    ratio = (raw - raw_min) / (raw_max - raw_min)
    return eng_min + ratio * (eng_max - eng_min)
