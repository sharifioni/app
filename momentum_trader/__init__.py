"""
Polymarket Momentum Trading System
A real-time momentum-following quantitative trading system for live sports events.
"""

from .config import config, Config, load_config_from_env

__version__ = "1.0.0"
__author__ = "Momentum Trader"

__all__ = [
    "config",
    "Config",
    "load_config_from_env",
]
