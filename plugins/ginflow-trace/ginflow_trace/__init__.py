"""Opt-in, non-blocking tracing helpers for Ginflow plugins."""

from .decorator import trace
from .identity import resolve_identity

__all__ = ["trace", "resolve_identity"]
