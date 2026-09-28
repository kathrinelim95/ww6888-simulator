"""Vercel serverless entry point.

Uses in-memory SQLite with StaticPool so each warm instance has a consistent
database during its lifetime. The database is seeded on first request.
"""

import os
import sys

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.seed import seed_demo
from app.main import create_app

_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_engine)

# Seed on cold start
with Session(_engine) as session:
    seed_demo(session, "SimAdmin2026!", "SimPlayer2026!")

_app = create_app(engine=_engine)


def handler(request):
    """ASGI handler for Vercel Python."""
    return _app(request)