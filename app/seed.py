from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import Announcement, AuditLog, Market, Selection, User, UserRole
from app.services.ledger import credit, get_balance


def seed_demo(session: Session, admin_password: str, player_password: str) -> dict[str, str]:
    """Create deterministic sandbox records without duplicating existing demo data."""
    admin = session.scalar(select(User).where(User.username == "sim-admin"))
    if admin is None:
        admin = User(
            username="sim-admin",
            password_hash=hash_password(admin_password),
            role=UserRole.ADMIN,
        )
        session.add(admin)
        session.flush()

    agent = session.scalar(select(User).where(User.username == "sim-agent"))
    if agent is None:
        agent = User(
            username="sim-agent",
            password_hash=hash_password(player_password),
            role=UserRole.AGENT,
            parent_id=admin.id,
        )
        session.add(agent)
        session.flush()

    player = session.scalar(select(User).where(User.username == "sim-player"))
    if player is None:
        player = User(
            username="sim-player",
            password_hash=hash_password(player_password),
            role=UserRole.PLAYER,
            parent_id=agent.id,
        )
        session.add(player)
        session.flush()

    if get_balance(session, player) == Decimal("0.00"):
        credit(
            session,
            player,
            Decimal("10000.00"),
            "OPENING",
            "Initial non-redeemable demo allocation",
        )

    market_specs = [
        ("Sandbox Midday Draw", 1, [("1234", "Demo 1234", "2.00"), ("2468", "Demo 2468", "3.50"), ("8080", "Demo 8080", "5.00")]),
        ("Sandbox Evening Draw", 2, [("1111", "Demo 1111", "2.50"), ("6789", "Demo 6789", "4.00"), ("9090", "Demo 9090", "6.00")]),
    ]
    for name, days, selections in market_specs:
        market = session.scalar(select(Market).where(Market.name == name))
        if market is None:
            market = Market(
                name=name,
                closes_at=datetime.now(timezone.utc) + timedelta(days=days),
            )
            market.selections = [
                Selection(code=code, label=label, odds=Decimal(odds))
                for code, label, odds in selections
            ]
            session.add(market)

    if session.scalar(select(Announcement).limit(1)) is None:
        session.add(
            Announcement(
                title="Simulation environment ready",
                body="All credits and settlements are virtual, non-redeemable and have no cash value.",
            )
        )

    if session.scalar(select(AuditLog).where(AuditLog.action == "SEED_DEMO")) is None:
        session.add(
            AuditLog(
                user_id=admin.id,
                action="SEED_DEMO",
                entity_type="system",
                details="Created sandbox users, markets and virtual credits",
            )
        )
    session.commit()
    return {"admin": admin.username, "agent": agent.username, "player": player.username}
