"""
Backports from Python > 3.10.
"""

# pyright: reportMissingImports = false

# NOTE(elpekenin): aliased import prevents "unused import" error

try:
    from enum import StrEnum as StrEnum
except ImportError:
    from backports.strenum import StrEnum as StrEnum
