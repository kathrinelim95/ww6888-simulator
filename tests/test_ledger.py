from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, User, UserRole
from app.services.ledger import credit, debit, get_balance


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_virtual_ledger_balance_is_sum_of_immutable_entries():
    with make_session() as session:
        user = User(username="sim-player", password_hash="test", role=UserRole.PLAYER)
        session.add(user)
        session.commit()

        credit(session, user, Decimal("1000.00"), "OPENING", "Initial test credit")
        debit(session, user, Decimal("125.50"), "STAKE", "Simulation ticket")

        assert get_balance(session, user) == Decimal("874.50")
        assert [entry.amount for entry in user.ledger_entries] == [
            Decimal("1000.00"),
            Decimal("-125.50"),
        ]
