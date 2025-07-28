# src/oxide/core/__init__.py
"""
Core components of the Oxide framework.
"""

# Import core modules for easier access
from . import (
    api,
    client,
    config,
    otypes,
    ologger,
    multiproc,
    progress,
)

# Set up logging
from .ologger import get_logger
logger = get_logger(__name__)

__all__ = [
    "api",
    "client",
    "config",
    "otypes",
    "ologger",
    "multiproc",
    "progress",
    "get_logger",
]
