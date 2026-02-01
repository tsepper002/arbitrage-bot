# Trader-level configuration: starting capital and simple RUB -> USDT conversion helper.
# Edit DEFAULT_RUB_PER_USDT to actual market rate or call get_starting_capital_usdt(rate=...)
STARTING_CAPITAL_RUB: float = 10000.0
DEFAULT_RUB_PER_USDT: float | None = None  # e.g. 90.0; set to None to disable auto-conversion

def get_starting_capital_usdt(rate: float | None = None) -> float | None:
    """
    Return starting capital in USDT if rate is available (RUB per USDT).
    If no rate provided and DEFAULT_RUB_PER_USDT is None, returns None.
    """
    r = rate if rate is not None else DEFAULT_RUB_PER_USDT
    if r is None or r <= 0:
        return None
    return STARTING_CAPITAL_RUB / r