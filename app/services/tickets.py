from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import (
    LedgerEntry,
    MarketStatus,
    Selection,
    Ticket,
    TicketStatus,
    User,
)
from app.services.ledger import get_balance


CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def place_ticket(
    session: Session,
    user: User,
    selection: Selection,
    stake: Decimal,
    *,
    commit: bool = True,
) -> Ticket:
    stake = _money(stake)
    if stake <= 0:
        raise ValueError("Stake must be positive")
    if selection.market.status != MarketStatus.OPEN:
        raise ValueError("Market is not open")
    if _as_utc(selection.market.closes_at) <= datetime.now(timezone.utc):
        raise ValueError("Market is closed")
    if get_balance(session, user) < stake:
        raise ValueError("Insufficient virtual credits")

    odds = _money(selection.odds)
    ticket_no = f"SIM-{uuid4().hex[:12].upper()}"
    ticket = Ticket(
        ticket_no=ticket_no,
        user=user,
        selection=selection,
        stake=stake,
        captured_odds=odds,
        potential_payout=_money(stake * odds),
        status=TicketStatus.PENDING,
    )
    debit_entry = LedgerEntry(
        user=user,
        amount=-stake,
        entry_type="STAKE",
        description=f"Virtual stake for {ticket_no}",
        reference=ticket_no,
    )
    session.add_all([ticket, debit_entry])
    if commit:
        session.commit()
        session.refresh(ticket)
    else:
        session.flush()
    return ticket


def settle_ticket(
    session: Session,
    ticket: Ticket,
    outcome: TicketStatus,
    *,
    commit: bool = True,
) -> Ticket:
    if ticket.status != TicketStatus.PENDING:
        raise ValueError("Ticket is already settled")
    if outcome not in {TicketStatus.WON, TicketStatus.LOST, TicketStatus.VOID}:
        raise ValueError("Invalid settlement outcome")

    if outcome == TicketStatus.WON:
        settled_amount = _money(ticket.potential_payout)
    elif outcome == TicketStatus.VOID:
        settled_amount = _money(ticket.stake)
    else:
        settled_amount = Decimal("0.00")

    ticket.status = outcome
    ticket.settled_amount = settled_amount
    ticket.settled_at = datetime.now(timezone.utc)

    if settled_amount > 0:
        session.add(
            LedgerEntry(
                user=ticket.user,
                amount=settled_amount,
                entry_type="SETTLEMENT",
                description=f"{outcome.value.title()} settlement for {ticket.ticket_no}",
                reference=ticket.ticket_no,
            )
        )

    if commit:
        session.commit()
        session.refresh(ticket)
    else:
        session.flush()
    return ticket
