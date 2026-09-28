from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.seed import seed_demo


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    admin_password = os.getenv("SIM_ADMIN_PASSWORD")
    player_password = os.getenv("SIM_PLAYER_PASSWORD")
    if not admin_password or not player_password:
        raise SystemExit(
            "Set SIM_ADMIN_PASSWORD and SIM_PLAYER_PASSWORD before seeding."
        )
    database_url = os.getenv(
        "SIM_DATABASE_URL", f"sqlite:///{(ROOT / 'simulation.db').as_posix()}"
    )
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        users = seed_demo(session, admin_password, player_password)
    print(f"Seed complete: {users}")


if __name__ == "__main__":
    main()
