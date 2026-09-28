from decimal import Decimal
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.models import (
    Announcement,
    AuditLog,
    Base,
    LedgerEntry,
    Market,
    Selection,
    Ticket,
    User,
    UserRole,
)
from app.services.ledger import credit, get_balance
from app.services.tickets import place_ticket


def test_login_opens_authenticated_dashboard_with_simulation_banner():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            username="demo-admin",
            password_hash=hash_password("local-test-password"),
            role=UserRole.ADMIN,
        )
        session.add(user)
        session.commit()
        credit(session, user, 10000, "OPENING", "Demo allocation")

    app = create_app(engine=engine)
    client = TestClient(app)

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "SIMULATION ONLY" in login_page.text

    response = client.post(
        "/login",
        data={"username": "demo-admin", "password": "local-test-password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "10,000.00" in response.text
    assert "No cash value" in response.text


def test_inactive_account_cannot_sign_in():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                username="disabled-player",
                password_hash=hash_password("local-test-password"),
                role=UserRole.PLAYER,
                active=False,
            )
        )
        session.commit()

    client = TestClient(create_app(engine=engine))
    response = client.post(
        "/login",
        data={"username": "disabled-player", "password": "local-test-password"},
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_authenticated_player_can_submit_virtual_credit_ticket():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(
            username="demo-player",
            password_hash=hash_password("local-test-password"),
            role=UserRole.PLAYER,
        )
        market = Market(
            name="Sandbox Draw",
            closes_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        selection = Selection(
            market=market,
            code="5678",
            label="Demo 5678",
            odds=Decimal("3.00"),
        )
        session.add_all([user, market, selection])
        session.commit()
        selection_id = selection.id
        credit(session, user, Decimal("500.00"), "OPENING", "Demo allocation")

    client = TestClient(create_app(engine=engine))
    client.post(
        "/login",
        data={"username": "demo-player", "password": "local-test-password"},
    )
    response = client.post(
        "/betting/place",
        data={"selection_id": selection_id, "stake": "25.00"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Ticket accepted" in response.text
    assert "475.00" in response.text
    assert "SIM-" in response.text
    with Session(engine) as session:
        audit = session.scalar(
            select(AuditLog).where(AuditLog.action == "PLACE_TICKET")
        )
        assert audit is not None
        assert audit.user.username == "demo-player"


def test_authenticated_management_modules_are_available():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(
            username="module-admin",
            password_hash=hash_password("local-test-password"),
            role=UserRole.ADMIN,
        )
        session.add_all(
            [admin, Announcement(title="Test notice", body="Sandbox maintenance")]
        )
        session.commit()
        credit(session, admin, Decimal("2500.00"), "OPENING", "Demo allocation")

    client = TestClient(create_app(engine=engine))
    client.post(
        "/login",
        data={"username": "module-admin", "password": "local-test-password"},
    )

    expected = {
        "/results": "Results",
        "/announcements": "Test notice",
        "/reports": "Reports",
        "/accounts": "Accounts",
        "/logs": "Audit Log",
        "/draw-dates": "Draw Dates",
        "/profile": "My Profile",
    }
    for path, text in expected.items():
        response = client.get(path)
        assert response.status_code == 200, path
        assert text in response.text, path
        assert "SIMULATION ONLY" in response.text, path


def test_admin_can_settle_virtual_ticket_and_audit_is_recorded():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(username="settle-admin", password_hash=hash_password("admin-pass"), role=UserRole.ADMIN)
        player = User(username="settle-player", password_hash=hash_password("player-pass"), role=UserRole.PLAYER)
        market = Market(name="Settlement Demo", closes_at=datetime.now(timezone.utc) + timedelta(hours=1))
        selection = Selection(market=market, code="9999", label="Demo 9999", odds=Decimal("2.00"))
        session.add_all([admin, player, market, selection])
        session.commit()
        credit(session, player, Decimal("500.00"), "OPENING", "Demo allocation")
        ticket = place_ticket(session, player, selection, Decimal("50.00"))
        ticket_id = ticket.id

    client = TestClient(create_app(engine=engine))
    client.post("/login", data={"username": "settle-admin", "password": "admin-pass"})
    response = client.post(
        f"/settlements/{ticket_id}",
        data={"outcome": "won"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "100.00" in response.text
    log_page = client.get("/logs")
    assert "SETTLE_TICKET" in log_page.text
    assert "won" in log_page.text


def test_player_cannot_access_administrative_accounts_or_logs():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        player = User(username="restricted-player", password_hash=hash_password("player-pass"), role=UserRole.PLAYER)
        session.add(player)
        session.commit()

    client = TestClient(create_app(engine=engine))
    client.post("/login", data={"username": "restricted-player", "password": "player-pass"})

    assert client.get("/accounts").status_code == 403
    assert client.get("/logs").status_code == 403


def test_admin_can_create_player_and_allocate_virtual_credit():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(username="account-admin", password_hash=hash_password("admin-pass"), role=UserRole.ADMIN)
        session.add(admin)
        session.commit()

    client = TestClient(create_app(engine=engine))
    client.post("/login", data={"username": "account-admin", "password": "admin-pass"})
    create_response = client.post(
        "/accounts/create",
        data={"username": "new-player", "password": "temporary-pass", "role": "player"},
        follow_redirects=True,
    )
    assert create_response.status_code == 200
    assert "new-player" in create_response.text

    with Session(engine) as session:
        player = session.scalar(select(User).where(User.username == "new-player"))
        player_id = player.id

    credit_response = client.post(
        f"/accounts/{player_id}/credit",
        data={"amount": "750.00", "description": "Test allocation"},
        follow_redirects=True,
    )
    assert credit_response.status_code == 200
    assert "750.00" in credit_response.text
    assert "ALLOCATE_CREDIT" in client.get("/logs").text


def test_credit_allocation_and_audit_are_atomic():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(username="atomic-admin", password_hash=hash_password("admin-pass"), role=UserRole.ADMIN)
        player = User(username="atomic-player", password_hash=hash_password("player-pass"), role=UserRole.PLAYER)
        session.add_all([admin, player])
        session.commit()
        player_id = player.id

    client = TestClient(create_app(engine=engine), raise_server_exceptions=False)
    client.post("/login", data={"username": "atomic-admin", "password": "admin-pass"})

    def reject_audit(*_args):
        raise RuntimeError("simulated audit persistence failure")

    event.listen(AuditLog, "before_insert", reject_audit)
    try:
        response = client.post(
            f"/accounts/{player_id}/credit",
            data={"amount": "100.00", "description": "Atomic test"},
        )
    finally:
        event.remove(AuditLog, "before_insert", reject_audit)

    assert response.status_code == 500
    with Session(engine) as session:
        entry_count = session.scalar(
            select(func.count(LedgerEntry.id)).where(LedgerEntry.user_id == player_id)
        )
    assert entry_count == 0


def test_settlement_and_audit_are_atomic():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(username="atomic-settle-admin", password_hash=hash_password("admin-pass"), role=UserRole.ADMIN)
        player = User(username="atomic-settle-player", password_hash=hash_password("player-pass"), role=UserRole.PLAYER)
        market = Market(name="Atomic Settlement", closes_at=datetime.now(timezone.utc) + timedelta(hours=1))
        selection = Selection(market=market, code="A1", label="Atomic A1", odds=Decimal("2.00"))
        session.add_all([admin, player, market, selection])
        session.commit()
        credit(session, player, Decimal("500.00"), "OPENING", "Demo allocation")
        ticket = place_ticket(session, player, selection, Decimal("50.00"))
        ticket_id = ticket.id
        player_id = player.id

    client = TestClient(create_app(engine=engine), raise_server_exceptions=False)
    client.post("/login", data={"username": "atomic-settle-admin", "password": "admin-pass"})

    def reject_audit(*_args):
        raise RuntimeError("simulated audit persistence failure")

    event.listen(AuditLog, "before_insert", reject_audit)
    try:
        response = client.post(
            f"/settlements/{ticket_id}", data={"outcome": "won"}
        )
    finally:
        event.remove(AuditLog, "before_insert", reject_audit)

    assert response.status_code == 500
    with Session(engine) as session:
        persisted = session.get(Ticket, ticket_id)
        player = session.get(User, player_id)
        assert persisted.status.value == "pending"
        assert get_balance(session, player) == Decimal("450.00")


def test_admin_can_create_simulation_market_with_initial_selection():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                username="market-admin",
                password_hash=hash_password("admin-pass"),
                role=UserRole.ADMIN,
            )
        )
        session.commit()

    client = TestClient(create_app(engine=engine))
    client.post("/login", data={"username": "market-admin", "password": "admin-pass"})
    response = client.post(
        "/markets/create",
        data={
            "name": "Demo Evening Draw",
            "closes_at": "2030-01-02T20:00",
            "code": "D123",
            "label": "Demo 123",
            "odds": "2.75",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Demo Evening Draw" in response.text
    with Session(engine) as session:
        market = session.scalar(select(Market).where(Market.name == "Demo Evening Draw"))
        assert market is not None
        assert [(item.code, item.odds) for item in market.selections] == [
            ("D123", Decimal("2.75"))
        ]
    assert "CREATE_MARKET" in client.get("/logs").text
