# Clean-Room Reimplementation Parity Matrix

## Project boundary

- **Reference:** `https://ww6888.vip/Website/index`
- **Authorization:** owner/owner-authorized inspection confirmed by user on 2026-09-28.
- **Inspection mode:** authenticated read-only; no reference mutations.
- **Target:** internal sandbox using non-redeemable test credits.
- **Excluded:** proprietary source, branding/assets, customer/private data, credentials/tokens, deposits, withdrawals, payment rails, redemption, real-money wagering.

## Workflow matrix

| ID | Role | Reference area | Evidence | Independent route/service | Test evidence | Status | Notes |
|---|---|---|---|---|---|---|---|
| WF-001 | All | Main | Menu and authenticated dashboard observed | `/dashboard` | Web integration test | tested | Reference widgets/calculations unknown |
| WF-002 | All | My Profile | Menu label observed | `/profile`, ledger view | Module integration test | tested | Reference fields unknown |
| WF-003 | All | Result | Menu label observed | `/results` | Module integration test | tested | Reference result-entry workflow unknown |
| WF-004 | All | Announcement | Menu label observed | `/announcements` | Module integration test | tested | Admin publishing workflow not implemented |
| WF-005 | All | Betting | Screen observed for Simple Bet, Mass Bet, Mass Bet (2), Wildcard Bet, Saved Bet, and Fixed Bet; controls inventoried without submission | `/betting`, `place_ticket` | Placement integration test | tested | Simulator rules are chosen behavior; reference validation, payout, confirmation, and errors remain unknown |
| WF-006 | All | Reports | Nine report screens observed; filters, sections, columns, empty states, pagination, View/Forecast/Export controls inventoried without executing queries/exports | `/reports` | Module and settlement tests | tested | Reference formulas, populated rows, row actions, export format, and role scope remain unknown |
| WF-007 | Admin | Account | Account submenu observed; Sub Account screen observed with filters, New/Edit, columns, and pagination; no mutation invoked | `/accounts`, create, allocate | Role, mutation, atomicity tests | tested | Downlines, Statement, Payment, and Online List finished screens pending; simulator hierarchy is independent |
| WF-008 | Admin | View Log | Menu label observed | `/logs` | Role and audit tests | tested | Reference event taxonomy unknown |
| WF-009 | All/Admin | Draw Date | Menu label observed | `/draw-dates`, `/markets/create` | Market creation test | tested | Reference date rules unknown |
| WF-010 | Admin | Settlement | Not individually observed | `settle_ticket`, `/settlements/{id}` | Idempotence and atomicity tests | tested | Independent chosen behavior |
| WF-011 | All | Authentication | Public login modal observed: username required, password field, English/简体中文 selection, POST to `/Website/index`; unauthenticated DOM also contains a numeric PIN keypad flow, but its runtime behavior is unverified | `/login`, `/logout` | Login and inactive-account tests | tested | Original implementation; no reference credentials or authentication material inspected |
| WF-012 | Admin | Exports | Unknown | Not implemented | None | blocked | Requires reference evidence/user requirement |
| WF-013 | Unknown authenticated role | Simple Bet | Screen observed; no input or submission | `/betting` | Covered only by general placement tests | audited | Exact fields and validation need a privacy-safe recapture |
| WF-014 | Unknown authenticated role | Mass Bet | Screen observed with repeated number, Big/Small, and total controls | Not implemented | None | audited | Batch semantics and limits unknown |
| WF-015 | Unknown authenticated role | Mass Bet (2) | Screen observed with Normal/Roll/iBet/kBet and grouped draw-day controls | Not implemented | None | audited | Mode-expansion rules unknown |
| WF-016 | Unknown authenticated role | Wildcard Bet | Screen observed with wildcard number expansion example | Not implemented | None | audited | Expansion rules beyond the visible example unknown |
| WF-017 | Unknown authenticated role | Saved Bet / Saved Detail | Entry screen and read-only status-filtered detail screen observed | Not implemented | None | audited | Save/edit lifecycle and permissions unknown |
| WF-018 | Unknown authenticated role | Fixed Bet / Fixed Detail | Entry and status-filtered detail screens observed; closure notice recorded | Not implemented | None | audited | Fixed-number lifecycle and system-submission behavior unknown |
| WF-019 | Unknown authenticated role | Full Report | Date/data/account filters, Export, and grouped Total/Upline/Member metrics observed | `/reports` | Generic report test | audited | Calculations and export output unverified |
| WF-020 | Unknown authenticated role | PlaceOut Report | Placeout Total/My Placeout/Agent/Member sections and metrics observed | Not implemented | None | audited | Place-out formulas and hierarchy scope unverified |
| WF-021 | Unknown authenticated role | Summary Report | Date filters and transaction/rebate/strike/net columns observed | `/reports` | Generic report test | audited | Formulas and date-boundary semantics unverified |
| WF-022 | Unknown authenticated role | Bets Detail | Date/account/filter controls plus View and Forecast observed | Not implemented | None | audited | Forecast not invoked; behavior unknown |
| WF-023 | Unknown authenticated role | Telegram Detail | Search filters, status/performer/remarks/action columns, and pagination observed | Not implemented | None | audited | Integration and row actions unknown and excluded by default |
| WF-024 | Unknown authenticated role | Strike Detail | Date/account filters observed | Not implemented | None | audited | Output schema and formula unknown |
| WF-025 | Unknown authenticated role | Deleted Detail | Draw-date/account filters observed | `/logs` | Audit tests | audited | Retention, restoration, and deletion authority unknown |
| WF-026 | Unknown authenticated role | Sub Account | Screen observed with hierarchy filters, New/Edit controls, columns, and pagination | `/accounts` | Admin account tests | audited | Mutating controls not invoked; role scope unknown |
| WF-027 | Unknown authenticated role | Downlines / Statement / Payment / Online List | Navigation observed | Not implemented | None | unknown | Finished-screen captures pending |

## Role matrix

| Capability | Admin | Agent | Player | Enforcement/test |
|---|---:|---:|---:|---|
| Own profile/ledger | Yes | Yes | Yes | Authenticated module test |
| Place simulation ticket | Yes | Yes | Yes | Placement route test |
| Own reports | Yes | Yes | Yes | Report query scopes players |
| Global accounts | Yes | No | No | 403 denial test |
| Global audit log | Yes | No | No | 403 denial test |
| Create account | Yes | No | No | Route role check; mutation test |
| Allocate credit | Yes | No | No | Route role check; atomicity test |
| Configure market | Yes | No | No | Route role check; creation test |
| Settle ticket | Yes | No | No | Route role check; settlement test |

## Calculation register

| Calculation | Formula | Precision | Test | Status |
|---|---|---|---|---|
| Balance | Sum of signed ledger entries | 2 decimals | Ledger test | tested |
| Potential payout | `stake × captured_odds` | 2 decimals | Ticket test | tested |
| Win settlement | potential payout | 2 decimals | Winning settlement test | tested |
| Loss settlement | zero | 2 decimals | Pending dedicated case | implemented |
| Void settlement | original stake | 2 decimals | Pending dedicated case | implemented |

## Unknowns and blocks

| Item | Reason | Required evidence | Status |
|---|---|---|---|
| Per-role reference visibility | Only top-level menu observed | Read-only role walkthroughs | blocked |
| Betting inputs/validation | Entry screens audited without submitting | Privacy-safe field recapture and owner-provided rules | blocked |
| Report formulas/export | Filters and columns observed, but queries/Forecast/Export were not invoked | Existing populated examples or owner specification | blocked |
| Exact calculations/rounding | No reference examples captured | Non-mutating examples or owner specification | blocked |
| Account hierarchy permissions | Sub Account schema observed; other account screens and role variants pending | Read-only role walkthrough | blocked |
| Result publishing | Reference workflow not audited | Read-only screen/state inspection | blocked |
| Draw-date rules | Reference workflow not audited | Read-only screen inspection | blocked |

## Completion gate

- [x] Authorization and exclusions recorded
- [x] Every known top-level module has a row
- [x] Original implementation and design language
- [x] Core mutation authorization and audit coverage
- [x] Full automated suite currently passes
- [ ] Clean seed executed twice against the final schema
- [ ] Live application/browser walkthrough completed
- [ ] Reference unknowns resolved or explicitly accepted as independent behavior
