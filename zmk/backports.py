"""
Backports from Python > 3.10.
"""

# pyright: reportMissingImports = false

try:
    from enum import StrEnum
except ImportError:
    from backports.strenum import StrEnum

__all__ = ["StrEnum"]
