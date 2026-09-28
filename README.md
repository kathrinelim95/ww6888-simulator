# Virtual-Credit Simulation Platform

An independently written sandbox management application using **non-purchasable, non-redeemable test credits**. It contains no deposits, withdrawals, payment rails, cash prizes, or external wager transmission.

## Local setup

```bash
uv sync --dev
```

Set local-only passwords and seed the database:

```bash
export SIM_ADMIN_PASSWORD='choose-a-local-password'
export SIM_PLAYER_PASSWORD='choose-a-different-local-password'
uv run python -m app.cli
```

Start the service:

```bash
export SIM_SESSION_SECRET='replace-with-a-long-random-local-secret'
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/login>.

Seeded usernames:

- `sim-admin`
- `sim-agent`
- `sim-player`

## Verification

```bash
uv run pytest -q
curl http://127.0.0.1:8000/health
```

Expected health metadata:

```json
{"status":"ok","mode":"simulation","real_money_enabled":false}
```

## Safety and deployment notes

- All balance changes are signed ledger entries.
- Settlement outcomes are `won`, `lost`, or `void` and are idempotent.
- The interface permanently displays `SIMULATION ONLY — NO CASH VALUE`.
- Do not expose the development server publicly.
- Set a strong `SIM_SESSION_SECRET`; terminate TLS at a trusted reverse proxy if deployed internally.
- The reference-site parity audit is incomplete. See `PARITY_MATRIX.md` for verified, chosen, and blocked behavior.
