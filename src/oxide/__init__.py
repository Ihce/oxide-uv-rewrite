# src/oxide/__init__.py
"""
Oxide - A flexible, modular, distributed framework for performing analysis of executable code.
"""

__version__ = "4.0.0"
__author__ = "Program Understanding Lab"

# Make core components available at package level
from .core import api, client, config, otypes

__all__ = ["api", "client", "config", "otypes", "__version__"]
