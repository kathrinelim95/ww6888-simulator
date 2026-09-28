from decimal import Decimal
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth import hash_password, verify_password
from app.main import create_app
from app.models import AuditLog, Base, LedgerEntry, Market, Selection, User, UserRole
from app.services.ledger import credit


def make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def make_user(engine, username, role=UserRole.PLAYER, parent_id=None):
    with Session(engine) as s:
        u = User(
            username=username,
            password_hash=hash_password("test-password"),
            role=role,
            parent_id=parent_id,
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        return u.id


# ─── Password change ───

def test_user_can_change_own_password():
    engine = make_engine()
    uid = make_user(engine, "changer", UserRole.PLAYER)
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "changer", "password": "test-password"})

    resp = client.post(
        "/profile/password",
        data={
            "current_password": "test-password",
            "new_password": "new-strong-pass",
            "confirm_password": "new-strong-pass",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Password updated" in resp.text

    with Session(engine) as s:
        user = s.get(User, uid)
        assert verify_password("new-strong-pass", user.password_hash)
        audit = s.scalar(select(AuditLog).where(AuditLog.action == "CHANGE_PASSWORD"))
        assert audit is not None


def test_password_change_rejects_wrong_current():
    engine = make_engine()
    make_user(engine, "changer2", UserRole.PLAYER)
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "changer2", "password": "test-password"})

    resp = client.post(
        "/profile/password",
        data={
            "current_password": "wrong-password",
            "new_password": "new-strong-pass",
            "confirm_password": "new-strong-pass",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Current password is incorrect" in resp.text


def test_password_change_rejects_mismatched_confirm():
    engine = make_engine()
    make_user(engine, "changer3", UserRole.PLAYER)
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "changer3", "password": "test-password"})

    resp = client.post(
        "/profile/password",
        data={
            "current_password": "test-password",
            "new_password": "new-strong-pass",
            "confirm_password": "different-pass",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "do not match" in resp.text


# ─── Downlines ───

def test_agent_can_view_downlines():
    engine = make_engine()
    agent_id = make_user(engine, "agent1", UserRole.AGENT)
    player_id = make_user(engine, "player1", UserRole.PLAYER, parent_id=agent_id)
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "agent1", "password": "test-password"})

    resp = client.get("/downlines")
    assert resp.status_code == 200
    assert "Downlines" in resp.text
    assert "player1" in resp.text


def test_player_cannot_view_downlines():
    engine = make_engine()
    make_user(engine, "lonely-player", UserRole.PLAYER)
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "lonely-player", "password": "test-password"})

    assert client.get("/downlines").status_code == 403


# ─── Statement ───

def test_user_can_view_own_statement():
    engine = make_engine()
    uid = make_user(engine, "stmt-user", UserRole.PLAYER)
    with Session(engine) as s:
        user = s.get(User, uid)
        credit(s, user, Decimal("5000.00"), "OPENING", "Initial allocation")
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "stmt-user", "password": "test-password"})

    resp = client.get("/statement")
    assert resp.status_code == 200
    assert "Statement" in resp.text
    assert "5,000.00" in resp.text


# ─── Payment (agent → downline credit transfer) ───

def test_agent_can_transfer_credit_to_downline():
    engine = make_engine()
    agent_id = make_user(engine, "pay-agent", UserRole.AGENT)
    player_id = make_user(engine, "pay-player", UserRole.PLAYER, parent_id=agent_id)
    with Session(engine) as s:
        agent = s.get(User, agent_id)
        credit(s, agent, Decimal("10000.00"), "OPENING", "Agent allocation")

    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "pay-agent", "password": "test-password"})

    resp = client.post(
        f"/payments/{player_id}",
        data={"amount": "2000.00", "description": "Test transfer", "direction": "send"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Payment recorded" in resp.text

    with Session(engine) as s:
        player = s.get(User, player_id)
        agent = s.get(User, agent_id)
        from app.services.ledger import get_balance
        assert get_balance(s, player) == Decimal("2000.00")
        assert get_balance(s, agent) == Decimal("8000.00")
        audit = s.scalar(select(AuditLog).where(AuditLog.action == "PAYMENT"))
        assert audit is not None


def test_agent_cannot_transfer_more_than_balance():
    engine = make_engine()
    agent_id = make_user(engine, "broke-agent", UserRole.AGENT)
    player_id = make_user(engine, "broke-player", UserRole.PLAYER, parent_id=agent_id)
    with Session(engine) as s:
        agent = s.get(User, agent_id)
        credit(s, agent, Decimal("100.00"), "OPENING", "Small allocation")

    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "broke-agent", "password": "test-password"})

    resp = client.post(
        f"/payments/{player_id}",
        data={"amount": "500.00", "description": "Too much", "direction": "send"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Insufficient" in resp.text


def test_player_cannot_send_payments():
    engine = make_engine()
    make_user(engine, "no-pay-agent", UserRole.AGENT)
    player_id = make_user(engine, "no-pay-player", UserRole.PLAYER, parent_id=None)
    app = create_app(engine=engine)
    client = TestClient(app)
    client.post("/login", data={"username": "no-pay-player", "password": "test-password"})

    resp = client.post(
        f"/payments/{player_id}",
        data={"amount": "10.00", "description": "x", "direction": "send"},
    )
    assert resp.status_code == 403


# ─── 4D payout calculations ───

def test_4d_ordinary_payouts():
    from app.services.payouts import ordinary_payout, BetType, PrizeLevel
    assert ordinary_payout(BetType.BIG, PrizeLevel.FIRST) == Decimal("4000.00")
    assert ordinary_payout(BetType.SMALL, PrizeLevel.FIRST) == Decimal("3000.00")
    assert ordinary_payout(BetType.BIG, PrizeLevel.STARTER) == Decimal("500.00")
    assert ordinary_payout(BetType.SMALL, PrizeLevel.STARTER) == Decimal("0.00")
    assert ordinary_payout(BetType.BIG, PrizeLevel.CONSOLATION) == Decimal("150.00")
    assert ordinary_payout(BetType.SMALL, PrizeLevel.CONSOLATION) == Decimal("0.00")


def test_4d_ibet_payout_divides_by_permutation_count():
    from app.services.payouts import ibet_payout, BetType, PrizeLevel
    assert ibet_payout(BetType.BIG, PrizeLevel.FIRST, 24) == Decimal("166.67")
    assert ibet_payout(BetType.SMALL, PrizeLevel.FIRST, 4) == Decimal("750.00")
    assert ibet_payout(BetType.BIG, PrizeLevel.CONSOLATION, 24) == Decimal("6.25")


def test_4d_kbet_payout_applies_factor():
    from app.services.payouts import kbet_payout, BetType, PrizeLevel
    # k-Bet big: factor 0.625
    assert kbet_payout(BetType.BIG, PrizeLevel.FIRST, 24) == Decimal("104.17")
    # k-Bet small: factor 1.429
    assert kbet_payout(BetType.SMALL, PrizeLevel.FIRST, 24) == Decimal("178.57")