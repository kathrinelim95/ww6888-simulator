from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.models import AuditLog, Base, User, UserRole


def make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_admin_disabling_account_revokes_existing_session():
    engine = make_engine()
    with Session(engine) as session:
        admin = User(
            username="admin",
            password_hash=hash_password("admin-password"),
            role=UserRole.ADMIN,
        )
        player = User(
            username="player",
            password_hash=hash_password("player-password"),
            role=UserRole.PLAYER,
        )
        session.add_all([admin, player])
        session.commit()
        player_id = player.id

    app = create_app(engine=engine)
    admin_client = TestClient(app)
    player_client = TestClient(app)
    admin_client.post("/login", data={"username": "admin", "password": "admin-password"})
    player_client.post("/login", data={"username": "player", "password": "player-password"})
    assert player_client.get("/dashboard").status_code == 200

    response = admin_client.post(
        f"/accounts/{player_id}/status",
        data={"active": "false"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Disabled" in response.text
    revoked = player_client.get("/dashboard", follow_redirects=False)
    assert revoked.status_code == 303
    assert revoked.headers["location"] == "/login"
    with Session(engine) as session:
        player = session.get(User, player_id)
        assert player.active is False
        assert player.session_version == 1
        audit = session.scalar(
            select(AuditLog).where(AuditLog.action == "SET_ACCOUNT_STATUS")
        )
        assert audit is not None
        assert "active=False" in audit.details
