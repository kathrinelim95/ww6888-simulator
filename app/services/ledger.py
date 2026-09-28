from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, User


CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT)


def get_balance(session: Session, user: User) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
            LedgerEntry.user_id == user.id
        )
    )
    return _money(Decimal(value))


def credit(
    session: Session,
    user: User,
    amount: Decimal,
    entry_type: str,
    description: str,
    reference: str | None = None,
    created_by: int | None = None,
    commit: bool = True,
) -> LedgerEntry:
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Credit amount must be positive")
    entry = LedgerEntry(
        user=user,
        amount=amount,
        entry_type=entry_type,
        description=description,
        reference=reference,
        created_by_id=created_by,
    )
    session.add(entry)
    if commit:
        session.commit()
        session.refresh(entry)
    else:
        session.flush()
    return entry


def debit(
    session: Session,
    user: User,
    amount: Decimal,
    entry_type: str,
    description: str,
    reference: str | None = None,
    created_by: int | None = None,
    commit: bool = True,
) -> LedgerEntry:
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Debit amount must be positive")
    if get_balance(session, user) < amount:
        raise ValueError("Insufficient virtual credits")
    entry = LedgerEntry(
        user=user,
        amount=-amount,
        entry_type=entry_type,
        description=description,
        reference=reference,
        created_by_id=created_by,
    )
    session.add(entry)
    if commit:
        session.commit()
        session.refresh(entry)
    else:
        session.flush()
    return entry
