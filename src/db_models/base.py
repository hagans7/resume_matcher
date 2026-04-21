"""SQLAlchemy declarative base.

All ORM models inherit from Base.
Imported by alembic/env.py for migration detection.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass
