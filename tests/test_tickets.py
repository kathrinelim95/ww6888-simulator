from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Market, Selection, TicketStatus, User, UserRole
from app.services.ledger import credit, get_balance
from app.services.tickets import place_ticket, settle_ticket


def make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_ticket_debits_test_credit_and_winning_settlement_credits_payout_once():
    with make_session() as session:
        user = User(username="player-one", password_hash="test", role=UserRole.PLAYER)
        market = Market(
            name="Demo Draw",
            closes_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        selection = Selection(market=market, code="1234", label="Demo 1234", odds=Decimal("2.50"))
        session.add_all([user, market, selection])
        session.commit()
        credit(session, user, Decimal("1000.00"), "OPENING", "Initial test credit")

        ticket = place_ticket(session, user, selection, Decimal("100.00"))

        assert ticket.status == TicketStatus.PENDING
        assert get_balance(session, user) == Decimal("900.00")

        settle_ticket(session, ticket, TicketStatus.WON)

        assert ticket.status == TicketStatus.WON
        assert ticket.settled_amount == Decimal("250.00")
        assert get_balance(session, user) == Decimal("1150.00")

        with pytest.raises(ValueError, match="already settled"):
            settle_ticket(session, ticket, TicketStatus.WON)
