#!/usr/bin/env python3
"""
Configuration validator — catches misconfigurations at startup.

Validates all critical settings BEFORE the bot starts trading.
Prevents runtime surprises from invalid env vars, missing API keys,
or contradictory settings.

Usage:
    from core.config_validator import validate_config
    issues = validate_config()
    if issues['errors']:
        print("Cannot start — fix these first:")
        for e in issues['errors']:
            print(f"  ❌ {e}")
        sys.exit(1)
"""
import os
import logging
from typing import Dict, List, Any

logger = logging.getLogger("ConfigValidator")


def validate_config() -> Dict[str, List[str]]:
    """
    Validate all configuration settings.

    Returns:
        {
            'errors': [...],    # Fatal — bot cannot start
            'warnings': [...],  # Non-fatal — bot can start but behavior may be unexpected
        }
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Import settings after .env is loaded
    import settings

    # ========================================================================
    # 1. API Key Validation
    # ========================================================================
    exchanges = {
        'Bybit': ('BYBIT_API_KEY', 'BYBIT_API_SECRET'),
        'KuCoin': ('KUCOIN_API_KEY', 'KUCOIN_API_SECRET', 'KUCOIN_PASSPHRASE'),
        'HTX': ('HTX_API_KEY', 'HTX_API_SECRET'),
        'MEXC': ('MEXC_API_KEY', 'MEXC_API_SECRET'),
        'Binance': ('BINANCE_API_KEY', 'BINANCE_API_SECRET'),
    }

    configured_exchanges = 0
    for name, keys in exchanges.items():
        all_present = True
        for key in keys:
            val = os.getenv(key, '').strip()
            if not val:
                all_present = False
            elif len(val) < 10:
                warnings.append(
                    f"{name}: {key} looks too short ({len(val)} chars) — "
                    f"may be a placeholder"
                )
        if all_present:
            configured_exchanges += 1
        else:
            warnings.append(f"{name}: Missing API keys — exchange will be skipped")

    if configured_exchanges < 2:
        errors.append(
            f"Need at least 2 exchanges configured for cross-exchange arbitrage "
            f"(found {configured_exchanges})"
        )

    # ========================================================================
    # 2. Trading Mode Validation
    # ========================================================================
    dry_run = getattr(settings, 'DRY_RUN', True)
    if not dry_run:
        warnings.append(
            "🔴 LIVE TRADING MODE — real money will be used! "
            "Set ARB_DRY_RUN=true for testing."
        )

    # ========================================================================
    # 3. Numeric Parameter Ranges
    # ========================================================================
    checks = [
        ('MIN_NET_ROI_PCT', 0.001, 5.0, "Minimum ROI threshold"),
        ('MAX_EXPOSURE_USDT', 1.0, 100000.0, "Maximum exposure per trade"),
        ('MAX_DAILY_LOSS_USDT', 1.0, 100000.0, "Maximum daily loss"),
        ('PER_SYMBOL_COOLDOWN_SEC', 0.1, 300.0, "Per-symbol cooldown"),
        ('MAX_TRADES_PER_MINUTE', 1, 1000, "Max trades per minute"),
        ('SCAN_INTERVAL_SEC', 0.01, 60.0, "Scan interval"),
    ]

    for attr, min_val, max_val, desc in checks:
        val = getattr(settings, attr, None)
        if val is not None:
            if val < min_val:
                warnings.append(
                    f"{attr}={val} is below minimum {min_val} — {desc}"
                )
            elif val > max_val:
                warnings.append(
                    f"{attr}={val} is above maximum {max_val} — {desc}"
                )

    # ========================================================================
    # 4. Staleness Threshold Validation
    # ========================================================================
    max_ob_age = getattr(settings, 'MAX_ORDERBOOK_AGE_MS', 2000)
    if max_ob_age < 500:
        warnings.append(
            f"MAX_ORDERBOOK_AGE_MS={max_ob_age}ms is very low — "
            f"on home PCs with 200-400ms latency, this may reject ALL data. "
            f"Recommended: 2000ms"
        )
    elif max_ob_age > 10000:
        warnings.append(
            f"MAX_ORDERBOOK_AGE_MS={max_ob_age}ms is very high — "
            f"stale data may trigger false arbitrage signals"
        )

    # ========================================================================
    # 5. Fee Configuration Validation
    # ========================================================================
    slippage = getattr(settings, 'GLOBAL_SLIPPAGE_PER_LEG_PCT', 0.01)
    if slippage > 0.1:
        warnings.append(
            f"GLOBAL_SLIPPAGE_PER_LEG_PCT={slippage} is very high — "
            f"this adds {slippage * 2} pct points to every trade's cost"
        )

    # ========================================================================
    # 6. Contradictory Settings
    # ========================================================================
    maker_first = getattr(settings, 'MAKER_FIRST_ENABLED', False)
    if maker_first:
        # Maker-first mode requires careful slippage handling
        slippage_legs = 1  # Only sell leg has slippage
    else:
        slippage_legs = 2  # Both legs market order

    # Check if settings are internally consistent
    scan_interval = getattr(settings, 'SCAN_INTERVAL_SEC', 0.15)
    event_driven = getattr(settings, 'EVENT_DRIVEN_SCAN', True)
    if event_driven and scan_interval > 1.0:
        warnings.append(
            f"EVENT_DRIVEN_SCAN=True but SCAN_INTERVAL_SEC={scan_interval}s "
            f"— event-driven scanning overrides interval-based scanning"
        )

    # ========================================================================
    # 7. Capital Validation
    # ========================================================================
    max_exposure = getattr(settings, 'MAX_EXPOSURE_USDT', 12.0)
    max_daily_loss = getattr(settings, 'MAX_DAILY_LOSS_USDT', 10.0)
    if max_exposure > max_daily_loss:
        warnings.append(
            f"MAX_EXPOSURE_USDT (${max_exposure}) > MAX_DAILY_LOSS_USDT "
            f"(${max_daily_loss}) — a single bad trade could hit daily loss limit"
        )

    return {'errors': errors, 'warnings': warnings}


def print_validation_report(issues: Dict[str, List[str]]) -> bool:
    """
    Print validation results and return True if safe to proceed.
    """
    if issues['errors']:
        logger.error("=" * 60)
        logger.error("CONFIGURATION ERRORS — Cannot start!")
        logger.error("=" * 60)
        for e in issues['errors']:
            logger.error(f"  ❌ {e}")

    if issues['warnings']:
        logger.warning("=" * 60)
        logger.warning("CONFIGURATION WARNINGS")
        logger.warning("=" * 60)
        for w in issues['warnings']:
            logger.warning(f"  ⚠️  {w}")

    if not issues['errors'] and not issues['warnings']:
        logger.info("✅ Configuration validation passed — all settings OK")

    return len(issues['errors']) == 0
