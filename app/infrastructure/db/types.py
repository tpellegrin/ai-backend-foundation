"""Database types for the application."""

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]  # missing stubs

__all__ = ["Vector"]
