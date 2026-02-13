#!/usr/bin/env python3
"""
REST clients for authenticated exchange operations.
Provides unified interface for order placement, balance queries, and withdrawals.
"""
from .base_client import BaseRESTClient
from .bybit_client import BybitRESTClient
from .kucoin_client import KuCoinRESTClient
from .htx_client import HTXRESTClient
from .mexc_client import MEXCRESTClient

__all__ = [
    'BaseRESTClient',
    'BybitRESTClient',
    'KuCoinRESTClient',
    'HTXRESTClient',
    'MEXCRESTClient'
]
