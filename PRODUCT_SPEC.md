# Virtual-Credit Simulation Platform — Implementation Specification

## 1. Project boundary

This is an independently implemented sandbox inspired only by behavior observable on an owner-authorized reference management site.

- Reference: `https://ww6888.vip/Website/index`
- Authorization: the user confirmed ownership or owner permission on 2026-09-28.
- Reference inspection: authenticated but strictly read-only.
- Target: internal virtual-credit simulation.
- Original implementation: no copied backend code, branding, protected assets, customer data, credentials, cookies, or tokens.

### Hard safety boundary

- Test credits have no cash value and cannot be purchased, sold, transferred outside the sandbox, or redeemed.
- No deposits, withdrawals, bank/card/wallet/cryptocurrency integrations, cash-out, payout provider, or real-world wager transmission.
- Authenticated screens visibly display `SIMULATION ONLY — NO CASH VALUE`.
- `/health` declares `mode: simulation` and `real_money_enabled: false`.

## 2. Reference evidence

Observed authenticated navigation labels:

- Main
- My Profile
- Result
- Announcement
- Betting
- Reports
- Account
- View Log
- Draw Date

Observed unauthenticated entry behavior on 2026-09-28:

- Public landing page presents `Home`, `Abount`, `Services`, `Contact`, and `Sign In` navigation.
- `Sign In` opens an in-page modal rather than navigating to a separate URL.
- Modal contains a required username field, password field, English/简体中文 choices, and a sign-in button.
- The form posts to `/Website/index`.
- The unauthenticated DOM contains a numeric PIN keypad/dialog (`9` through `0` plus `ok`) and PIN-related inputs. This is markup evidence only; trigger conditions, validation, attempt limits, persistence, and role behavior were not exercised or inferred.
- No credentials, cookies, tokens, PINs, hidden field values, or authentication material were inspected or retained.

The authenticated desktop session was later reacquired and the following additional behavior was observed read-only. No form was submitted, no account or balance was changed, and no export was downloaded.

### Authenticated shell

- The shell displays `Credit`, `Credit Available`, and `Credit Balance`, a server date/time, market status (`OPEN` in the observed session), and available draw dates.
- A notice states that 4D betting closes at 6:19 PM and refers mobile users to a mobile subdomain.
- The observed account marker was `SMPBT`; its formal role name and permission set remain unknown.

### Betting navigation

- Observed submenu labels: `Simple Bet`, `Mass Bet`, `Mass Bet (2)`, `Wildcard Bet`, `Saved Bet`, and `Fixed Bet`.
- `Mass Bet` presents repeated number rows with Big/Small stake fields and total controls.
- `Mass Bet (2)` adds batch mode/day controls, including labels such as Normal, Roll, iBet, kBet, and grouped draw-day choices.
- `Wildcard Bet` presents number-pattern expansion; an on-screen example showed a wildcard expanding into multiple four-digit numbers.
- `Saved Bet` presents reusable pages plus Clear, Calculate, Submit, and Save controls.
- `Fixed Bet` presents reusable fixed-number rows and states that fixed numbers close at 14:00 and are submitted to the system at 14:15.
- Input validation, minimum/maximum stake, duplicate handling, confirmation, payout, and error behavior were not exercised.

### Reports navigation

Observed report screens:

- `Full Report`: date range, data type, account search, View and Export; grouped Total, Upline, and Member sections with Big, Small, percentage, Amount, Payable, Strike, ticket percentage, expense/tax, profit/loss, and Nett fields.
- `PlaceOut Report`: date range, View and Export; Placeout Total, My Placeout, Agent, and Member sections with Big, Small, percentage, Amount, ticket percentage, Payable, Strike, Nett, and Details.
- `Summary Report`: date range and View; Transaction Date, Description, Amount, Rebate, Less Rebate, Strike, Strike Comm, Nett, PL Stake, and Nett Bal.
- `Bets Detail`: date range, account, filter, View, and Forecast; Downline Summary and Page Details output areas.
- `Telegram Detail`: date range, search mode/value, account, All, and View; Received Time, Account ID, Status, Perform By, Telegram ID, Remarks, and Actions. The empty table used a page-size default of 20 and first/previous/next/last pagination.
- `Strike Detail`: date range, account, and View.
- `Saved Detail`: account, status (default observed as Active), and View.
- `Fixed Detail`: status (default observed as Active), account, and View.
- `Deleted Detail`: draw date, account, and View.

Visible report forms and empty states do not prove formulas, permissions, query semantics, exports, row actions, or state transitions. `View`, `Forecast`, and `Export` were not invoked during this pass.

### Account navigation

- Observed submenu labels: `Sub Account`, `Downlines`, `Statement`, `Payment`, and `Online List`.
- `Sub Account` provides parent/account and account-ID filters, View/Clear, New/Edit, and a paginated table with Main Account, Account ID, Name, and Status. New/Edit were not invoked.
- The remaining account screens still require finished-screen capture.

Detailed role boundaries, populated report examples, exact calculations, rounding, result publication, account mutations, and settlement behavior remain unknown unless separately verified in `PARITY_MATRIX.md`.

## 3. Chosen independent behavior

### Roles

| Capability | Admin | Agent | Player |
|---|---:|---:|---:|
| View own profile and ledger | Yes | Yes | Yes |
| View own reports | Yes | Yes | Yes |
| Place simulation ticket | Yes | Yes | Yes |
| Create accounts | Yes | Future scoped downline | No |
| Allocate test credit | Yes | Future scoped downline | No |
| Configure markets | Yes | No | No |
| Settle tickets | Yes | No | No |
| View global audit log | Yes | No | No |

### Entities

- `User`: username, Argon2 password hash, role, parent, active state, timestamp.
- `LedgerEntry`: beneficiary, signed fixed-precision amount, type, description, stable reference, initiating actor, timestamp.
- `Market`: name, UTC close time, status.
- `Selection`: market, code, label, decimal odds.
- `Ticket`: user, selection, stake, captured odds, potential payout, status, settlement amount and timestamps.
- `Announcement`: title, body, active state, timestamp.
- `AuditLog`: actor, action, entity type/id, details, timestamp.

## 4. Ledger invariants

1. Balance is the exact sum of signed ledger entries.
2. Positive entries are allocations, refunds, or settlement credits; negative entries are stakes.
3. A debit cannot reduce balance below zero.
4. Monetary-like values use `Decimal` and database fixed precision with two-decimal quantization.
5. Existing entries are append-only by application policy; corrections require compensating entries.
6. Administrative allocations store the initiating actor.
7. Allocation and its audit event commit atomically.

## 5. Ticket placement

A ticket may be created only when:

- the user is authenticated and active;
- stake is positive after two-decimal quantization;
- the market status is `open`;
- current UTC time is before market close;
- test-credit balance covers the stake.

One transaction creates the ticket and corresponding negative `STAKE` ledger entry. Odds and potential payout are captured at placement.

## 6. Settlement

Allowed transition:

`pending → won | lost | void`

| Outcome | Credit |
|---|---:|
| Won | `stake × captured_odds` |
| Lost | `0.00` |
| Void | original stake |

A non-pending ticket cannot be settled again. Settlement record, optional ledger credit, and audit event commit atomically.

## 7. Routes and interfaces

- `/login`, `/logout`
- `/dashboard`
- `/profile`
- `/betting`, `/betting/place`
- `/results`
- `/announcements`
- `/reports`
- `/accounts`, `/accounts/create`, `/accounts/{id}/credit`
- `/logs`
- `/draw-dates`, `/markets/create`
- `/settlements/{ticket_id}`
- `/health`

The UI uses an original dark navigation and neutral operational workspace rather than the reference site's trade dress.

## 8. Security and operational assumptions

- Passwords are Argon2 hashed through `pwdlib`.
- Disabled accounts cannot authenticate.
- Privileged mutation routes perform server-side role checks.
- Session cookies use `SameSite=Lax`; production/internal deployment must set a strong `SIM_SESSION_SECRET` and HTTPS-only cookies behind TLS.
- The current build is for local/internal evaluation, not public internet exposure.
- SQLite is the local database; a production migration plan and stronger concurrent balance locking are required before multi-user deployment.

## 9. Verification gate

Completion requires:

- full automated suite passing;
- seed operation succeeding twice without duplicates;
- live server health check;
- real browser walkthrough of login, placement, settlement, reports, authorization denial, and audit records;
- every promised reference workflow audited or explicitly accepted as an independent design decision.
