from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    ADMIN = "admin"
    AGENT = "agent"
    PLAYER = "player"


class MarketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    SETTLED = "settled"


class TicketStatus(StrEnum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    VOID = "void"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    parent: Mapped[User | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[User]] = relationship(back_populates="parent")
    ledger_entries: Mapped[list[LedgerEntry]] = relationship(
        back_populates="user",
        order_by="LedgerEntry.id",
        foreign_keys="LedgerEntry.user_id",
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    entry_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(255))
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(
        back_populates="ledger_entries", foreign_keys=[user_id]
    )
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[MarketStatus] = mapped_column(
        Enum(MarketStatus), default=MarketStatus.OPEN
    )

    selections: Mapped[list[Selection]] = relationship(back_populates="market")


class Selection(Base):
    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    odds: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    market: Mapped[Market] = relationship(back_populates="selections")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="selection")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"), index=True)
    stake: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    captured_odds: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    potential_payout: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.PENDING
    )
    settled_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship()
    selection: Mapped[Selection] = relationship(back_populates="tickets")


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User | None] = relationship()
