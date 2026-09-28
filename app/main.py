from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from decimal import Decimal

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import hash_password, verify_password
from app.models import (
    Announcement,
    AuditLog,
    Base,
    LedgerEntry,
    Market,
    MarketStatus,
    Selection,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
from app.services.ledger import credit, get_balance, debit
from app.services.payouts import BetType, PrizeLevel, ordinary_payout, ibet_payout, kbet_payout
from app.services.tickets import place_ticket, settle_ticket


ROOT = Path(__file__).parent


def create_app(engine: Engine | None = None) -> FastAPI:
    if engine is None:
        database_url = os.getenv(
            "SIM_DATABASE_URL", f"sqlite:///{(ROOT.parent / 'simulation.db').as_posix()}"
        )
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )

    Base.metadata.create_all(engine)
    app = FastAPI(title="Virtual-Credit Simulation Platform")
    app.state.engine = engine
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("SIM_SESSION_SECRET", "local-simulation-only-change-me"),
        same_site="lax",
        https_only=False,
    )
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")

    def signed_in_user(request: Request, session: Session) -> User | None:
        user_id = request.session.get("user_id")
        user = session.get(User, user_id) if user_id else None
        if (
            user is None
            or not user.active
            or request.session.get("session_version") != user.session_version
        ):
            request.session.clear()
            return None
        return user

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "mode": "simulation",
            "real_money_enabled": False,
        }

    @app.get("/")
    def index() -> RedirectResponse:
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/login")
    def login_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": None, "title": "Simulation Sign In"},
        )

    @app.post("/login")
    def login(request: Request, username: str = Form(), password: str = Form()):
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.username == username))
            if (
                user is None
                or not user.active
                or not verify_password(password, user.password_hash)
            ):
                return templates.TemplateResponse(
                    request=request,
                    name="login.html",
                    context={"error": "Invalid username or password"},
                    status_code=401,
                )
            request.session["user_id"] = user.id
            request.session["session_version"] = user.session_version
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/dashboard")
    def dashboard(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            balance = get_balance(session, user)
            markets = list(session.scalars(select(Market).order_by(Market.closes_at).limit(3)).unique())
            announcements = list(session.scalars(select(Announcement).where(Announcement.active.is_(True)).order_by(Announcement.created_at.desc()).limit(5)))
            return templates.TemplateResponse(
                request=request,
                name="dashboard.html",
                context={
                    "user": user,
                    "balance": balance,
                    "markets": markets,
                    "announcements": announcements,
                    "title": "Dashboard",
                    "page_title": "Dashboard",
                    "active": "dashboard",
                },
            )

    @app.get("/betting")
    def betting(request: Request, ticket: str | None = None, error: str | None = None):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            markets = list(
                session.scalars(
                    select(Market)
                    .where(Market.status == MarketStatus.OPEN)
                    .order_by(Market.closes_at)
                ).unique()
            )
            tickets = list(
                session.scalars(
                    select(Ticket)
                    .where(Ticket.user_id == user.id)
                    .order_by(Ticket.created_at.desc())
                )
            )
            return templates.TemplateResponse(
                request=request,
                name="betting.html",
                context={
                    "user": user,
                    "balance": get_balance(session, user),
                    "markets": markets,
                    "tickets": tickets,
                    "ticket_no": ticket,
                    "error": error,
                    "title": "Betting Simulator",
                    "page_title": "Betting Simulator",
                    "active": "betting",
                },
            )

    @app.post("/betting/place")
    def place_betting_ticket(
        request: Request,
        selection_id: int = Form(),
        stake: Decimal = Form(),
    ):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            selection = session.get(Selection, selection_id)
            if selection is None:
                return RedirectResponse("/betting?error=Selection+not+found", status_code=303)
            try:
                ticket = place_ticket(session, user, selection, stake, commit=False)
                session.add(
                    AuditLog(
                        user_id=user.id,
                        action="PLACE_TICKET",
                        entity_type="ticket",
                        entity_id=str(ticket.id),
                        details=(
                            f"reference={ticket.ticket_no}; stake={ticket.stake}; "
                            f"selection={selection.code}"
                        ),
                    )
                )
                session.commit()
            except ValueError as exc:
                message = str(exc).replace(" ", "+")
                return RedirectResponse(f"/betting?error={message}", status_code=303)
            return RedirectResponse(f"/betting?ticket={ticket.ticket_no}", status_code=303)

    @app.post("/settlements/{ticket_id}")
    def settle_virtual_ticket(
        ticket_id: int,
        request: Request,
        outcome: TicketStatus = Form(),
    ):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            if user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            ticket = session.get(Ticket, ticket_id)
            if ticket is None:
                raise HTTPException(status_code=404, detail="Ticket not found")
            settle_ticket(session, ticket, outcome, commit=False)
            session.add(
                AuditLog(
                    user_id=user.id,
                    action="SETTLE_TICKET",
                    entity_type="ticket",
                    entity_id=str(ticket.id),
                    details=f"outcome={outcome.value}; amount={ticket.settled_amount}",
                )
            )
            session.commit()
        return RedirectResponse("/reports", status_code=303)

    def module_response(
        request: Request,
        session: Session,
        user: User,
        active: str,
        heading: str,
        kicker: str,
        description: str,
        **data,
    ) -> templates.TemplateResponse:
        context = {
            "user": user,
            "active": active,
            "title": heading,
            "page_title": heading,
            "heading": heading,
            "kicker": kicker,
            "description": description,
            "badge": "Sandbox",
            "balance": get_balance(session, user),
            "markets": list(session.scalars(select(Market).order_by(Market.closes_at).limit(3)).unique()),
            **data,
        }
        return templates.TemplateResponse(
            request=request, name="module.html", context=context
        )

    @app.get("/results")
    def results(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            markets = list(session.scalars(select(Market).order_by(Market.closes_at.desc())).unique())
            return module_response(request, session, user, "results", "Results", "OUTCOMES", "Published simulation market outcomes and statuses.", markets=markets)

    @app.get("/announcements")
    def announcements(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            items = list(session.scalars(select(Announcement).where(Announcement.active.is_(True)).order_by(Announcement.created_at.desc())))
            return module_response(request, session, user, "announcements", "Announcements", "NOTICES", "Operational messages for this simulation environment.", announcements=items)

    @app.get("/reports")
    def reports(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            query = select(Ticket).order_by(Ticket.created_at.desc())
            if user.role == UserRole.PLAYER:
                query = query.where(Ticket.user_id == user.id)
            tickets = list(session.scalars(query))
            total_stake = sum((ticket.stake for ticket in tickets), Decimal("0.00"))
            total_settled = sum((ticket.settled_amount for ticket in tickets), Decimal("0.00"))
            return module_response(request, session, user, "reports", "Reports", "FINANCIAL SIMULATION", "Test-credit stake and settlement activity.", tickets=tickets, total_stake=total_stake, total_settled=total_settled)

    @app.post("/accounts/create")
    def create_account(
        request: Request,
        username: str = Form(),
        password: str = Form(),
        role: UserRole = Form(),
        parent_id: int | None = Form(default=None),
    ):
        with Session(engine) as session:
            admin = signed_in_user(request, session)
            if admin is None:
                return RedirectResponse("/login", status_code=303)
            if admin.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            if len(password) < 8:
                raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
            if session.scalar(select(User).where(User.username == username.strip())):
                raise HTTPException(status_code=409, detail="Username already exists")
            account = User(
                username=username.strip(),
                password_hash=hash_password(password),
                role=role,
                parent_id=parent_id,
            )
            session.add(account)
            session.flush()
            session.add(AuditLog(user_id=admin.id, action="CREATE_ACCOUNT", entity_type="user", entity_id=str(account.id), details=f"username={account.username}; role={role.value}"))
            session.commit()
        return RedirectResponse("/accounts", status_code=303)

    @app.post("/accounts/{account_id}/credit")
    def allocate_credit(
        account_id: int,
        request: Request,
        amount: Decimal = Form(),
        description: str = Form(default="Test allocation"),
    ):
        with Session(engine) as session:
            admin = signed_in_user(request, session)
            if admin is None:
                return RedirectResponse("/login", status_code=303)
            if admin.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            account = session.get(User, account_id)
            if account is None:
                raise HTTPException(status_code=404, detail="Account not found")
            credit(
                session,
                account,
                amount,
                "ALLOCATION",
                description,
                created_by=admin.id,
                commit=False,
            )
            session.add(AuditLog(user_id=admin.id, action="ALLOCATE_CREDIT", entity_type="user", entity_id=str(account.id), details=f"amount={amount}; description={description}"))
            session.commit()
        return RedirectResponse("/accounts", status_code=303)

    @app.post("/accounts/{account_id}/status")
    def set_account_status(
        account_id: int,
        request: Request,
        active: bool = Form(),
    ):
        with Session(engine) as session:
            admin = signed_in_user(request, session)
            if admin is None:
                return RedirectResponse("/login", status_code=303)
            if admin.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            account = session.get(User, account_id)
            if account is None:
                raise HTTPException(status_code=404, detail="Account not found")
            if account.id == admin.id and not active:
                raise HTTPException(status_code=422, detail="Cannot disable current account")
            account.active = active
            account.session_version += 1
            session.add(
                AuditLog(
                    user_id=admin.id,
                    action="SET_ACCOUNT_STATUS",
                    entity_type="user",
                    entity_id=str(account.id),
                    details=f"active={active}",
                )
            )
            session.commit()
        return RedirectResponse("/accounts", status_code=303)

    @app.get("/accounts")
    def accounts(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            if user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            accounts = list(session.scalars(select(User).order_by(User.username)))
            balances = {account.id: get_balance(session, account) for account in accounts}
            return module_response(request, session, user, "accounts", "Accounts", "ACCOUNT HIERARCHY", "Virtual-credit users, roles, parent relationships and status.", accounts=accounts, balances=balances)

    @app.get("/logs")
    def logs(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            if user.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            logs = list(session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc())))
            return module_response(request, session, user, "logs", "Audit Log", "IMMUTABLE HISTORY", "Administrative and settlement events.", logs=logs)

    @app.post("/markets/create")
    def create_market(
        request: Request,
        name: str = Form(),
        closes_at: str = Form(),
        code: str = Form(),
        label: str = Form(),
        odds: Decimal = Form(),
    ):
        with Session(engine) as session:
            admin = signed_in_user(request, session)
            if admin is None:
                return RedirectResponse("/login", status_code=303)
            if admin.role != UserRole.ADMIN:
                raise HTTPException(status_code=403, detail="Admin role required")
            close_time = datetime.fromisoformat(closes_at)
            if close_time.tzinfo is None:
                close_time = close_time.replace(tzinfo=timezone.utc)
            if close_time <= datetime.now(timezone.utc):
                raise HTTPException(status_code=422, detail="Close time must be in the future")
            if odds <= 0:
                raise HTTPException(status_code=422, detail="Odds must be positive")
            market = Market(name=name.strip(), closes_at=close_time)
            market.selections.append(
                Selection(
                    code=code.strip(),
                    label=label.strip(),
                    odds=odds.quantize(Decimal("0.01")),
                )
            )
            session.add(market)
            session.flush()
            session.add(
                AuditLog(
                    user_id=admin.id,
                    action="CREATE_MARKET",
                    entity_type="market",
                    entity_id=str(market.id),
                    details=f"name={market.name}; selection={code.strip()}; odds={odds}",
                )
            )
            session.commit()
        return RedirectResponse("/draw-dates", status_code=303)

    @app.get("/draw-dates")
    def draw_dates(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            markets = list(session.scalars(select(Market).order_by(Market.closes_at)).unique())
            return module_response(request, session, user, "draw-dates", "Draw Dates", "SCHEDULE", "Open, closed and settled test-market schedule.", markets=markets)

    @app.get("/profile")
    def profile(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            ledger = list(session.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.created_at.desc())))
            return module_response(request, session, user, "profile", "My Profile", "ACCOUNT", "Identity, permissions and virtual-credit ledger.", balance=get_balance(session, user), ledger=ledger)

    # ─── Password change ───

    @app.post("/profile/password")
    def change_password(
        request: Request,
        current_password: str = Form(),
        new_password: str = Form(),
        confirm_password: str = Form(),
    ):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            if not verify_password(current_password, user.password_hash):
                return module_response(
                    request, session, user, "profile", "My Profile", "ACCOUNT",
                    "Identity, permissions and virtual-credit ledger.",
                    balance=get_balance(session, user),
                    ledger=list(session.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.created_at.desc()))),
                    password_error="Current password is incorrect",
                )
            if new_password != confirm_password:
                return module_response(
                    request, session, user, "profile", "My Profile", "ACCOUNT",
                    "Identity, permissions and virtual-credit ledger.",
                    balance=get_balance(session, user),
                    ledger=list(session.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.created_at.desc()))),
                    password_error="New password and confirmation do not match",
                )
            if len(new_password) < 8:
                return module_response(
                    request, session, user, "profile", "My Profile", "ACCOUNT",
                    "Identity, permissions and virtual-credit ledger.",
                    balance=get_balance(session, user),
                    ledger=list(session.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.created_at.desc()))),
                    password_error="Password must be at least 8 characters",
                )
            user.password_hash = hash_password(new_password)
            user.session_version += 1
            session.add(
                AuditLog(
                    user_id=user.id,
                    action="CHANGE_PASSWORD",
                    entity_type="user",
                    entity_id=str(user.id),
                    details="Password changed",
                )
            )
            session.commit()
            request.session["session_version"] = user.session_version
        return RedirectResponse("/profile?msg=Password+updated", status_code=303)

    # ─── Downlines (agent & admin) ───

    @app.get("/downlines")
    def downlines(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            if user.role == UserRole.PLAYER:
                raise HTTPException(status_code=403, detail="Agent or admin role required")
            children = list(
                session.scalars(
                    select(User).where(User.parent_id == user.id).order_by(User.username)
                )
            )
            balances = {child.id: get_balance(session, child) for child in children}
            return module_response(
                request, session, user, "downlines", "Downlines",
                "HIERARCHY", "Direct sub-accounts and their virtual-credit balances.",
                accounts=children, balances=balances,
            )

    # ─── Statement (own transaction history) ───

    @app.get("/statement")
    def statement(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            ledger = list(
                session.scalars(
                    select(LedgerEntry)
                    .where(LedgerEntry.user_id == user.id)
                    .order_by(LedgerEntry.created_at.desc())
                )
            )
            return module_response(
                request, session, user, "statement", "Statement",
                "TRANSACTIONS", "Virtual-credit transaction history.",
                ledger=ledger, balance=get_balance(session, user),
            )

    # ─── Payment (agent → downline credit transfer) ───

    @app.post("/payments/{account_id}")
    def make_payment(
        account_id: int,
        request: Request,
        amount: Decimal = Form(),
        description: str = Form(default="Test transfer"),
        direction: str = Form(default="send"),
    ):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            if user.role == UserRole.PLAYER:
                raise HTTPException(status_code=403, detail="Agent or admin role required")
            target = session.get(User, account_id)
            if target is None:
                raise HTTPException(status_code=404, detail="Account not found")
            if direction == "send":
                try:
                    debit(session, user, amount, "PAYMENT_OUT", description, created_by=user.id)
                except ValueError as exc:
                    return RedirectResponse(
                        f"/downlines?error={str(exc).replace(' ', '+')}", status_code=303
                    )
                credit(session, target, amount, "PAYMENT_IN", description, created_by=user.id, commit=False)
            else:
                try:
                    debit(session, target, amount, "PAYMENT_OUT", description, created_by=user.id)
                except ValueError as exc:
                    return RedirectResponse(
                        f"/downlines?error={str(exc).replace(' ', '+')}", status_code=303
                    )
                credit(session, user, amount, "PAYMENT_IN", description, created_by=user.id, commit=False)
            session.add(
                AuditLog(
                    user_id=user.id,
                    action="PAYMENT",
                    entity_type="user",
                    entity_id=str(target.id),
                    details=f"direction={direction}; amount={amount}; description={description}",
                )
            )
            session.commit()
        return RedirectResponse("/downlines?msg=Payment+recorded", status_code=303)

    # ─── Telegram Help info page ───

    @app.get("/telegram-help")
    def telegram_help(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            return module_response(
                request, session, user, "telegram-help", "Telegram Help",
                "INTEGRATION", "Reference guide for Telegram betting integration (simulation).",
            )

    # ─── Payout guide ───

    @app.get("/payout-guide")
    def payout_guide(request: Request):
        with Session(engine) as session:
            user = signed_in_user(request, session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            return module_response(
                request, session, user, "payout-guide", "Payout Guide",
                "REFERENCE", "Verified 4D payout values for test-credit settlement.",
                payout_data={
                    "ordinary": {
                        f"{bet.value}_{prize.value}": str(ordinary_payout(bet, prize))
                        for bet in BetType for prize in PrizeLevel
                    },
                },
            )

    return app


app = create_app()
