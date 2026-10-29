# Next-Generation Digital Queue

[![CI](https://github.com/Eugeniouo/digital-ticket-service/actions/workflows/ci.yml/badge.svg)](https://github.com/Eugeniouo/digital-ticket-service/actions/workflows/ci.yml)

An MVP of a digital queue management system, built during the Russian Post hackathon (PostCode Challenge by Pochtatech).
Visitors, operators and branch managers all work in a browser on their own devices — no dedicated kiosk or ticket hardware required.
The queue lives on the server; its state is stored in PostgreSQL and survives restarts.

Three entry points feed into a single branch queue: pre-booked time slots, e-tickets obtained via a QR code in the branch hall, and walk-in customers registered by an operator.

> The user interface is in Russian, as the product targets Russian Post branches.

## Contents

- [Goal](#goal)
- [What's Delivered](#whats-delivered)
- [Architecture](#architecture)
- [Features](#features)
- [Queue Algorithm](#queue-algorithm)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Commands](#development-commands)
- [Notifications](#notifications)
- [Roadmap and Scaling](#roadmap-and-scaling)

## Goal

Physical queue management systems are installed in only a fraction of post offices.
Deploying and maintaining them requires hardware in every branch, so a network of tens of thousands of locations evolves unevenly.

This project moves the queue onto customers' phones and staff computers, with service rules defined centrally and tuned at the branch level.

Who uses it:

- **Visitor** — books a slot in advance or takes a ticket at the branch;
- **Operator** — runs a service window and calls the next customer;
- **Branch manager** — configures windows and rules, monitors the day;
- **`root`** — creates branches and accounts across the network.

## What's Delivered

All mandatory scenarios from the hackathon brief are ready for review: booking, QR tickets, calling by any free window, concurrent calls with ticket locking, closing a window, redirecting a customer, restart with the queue preserved, notification gateway outage, concurrent ticket number issuance, and daily analytics.

| Layer | Result |
|---|---|
| Visitor | responsive web UI for booking, QR check-in and ticket status |
| Operator | window workstation: open, call, serve, mark no-show |
| Manager | windows, priority rules, live queue, analytics, staff, QR poster |
| Server | REST API, OpenAPI, ticket status audit log, notification module |
| Data | PostgreSQL as the single source of truth; the queue is restored after a restart |
| Integrations | demo notification adapter behind the `NotificationGateway` port |
| Deployment | full stack via Docker Compose |

The UI only displays state and sends commands.
Call order, ticket numbers, slots and locks are all computed on the server.

## Architecture

```
Visitor / Operator / Manager
                 │
              Caddy
          ┌──────┴──────┐
     frontend          /api
                        │
                     FastAPI
                   ┌────┼────┐
            PostgreSQL  Valkey  Celery
```

Caddy serves a single origin: the frontend pages and `/api`.
The browser calls the API on the same origin, with the JWT passed in the `Authorization: Bearer` header.
Queue state and the notification outbox live in PostgreSQL.
Valkey is the Celery broker: a worker picks up pending outbox records and hands them to the gateway adapter.

### Tech Stack

| Component | Purpose |
|---|---|
| Python 3.12+, FastAPI, SQLAlchemy, Alembic | queue server and migrations |
| PostgreSQL | branches, tickets, slots, audit log, outbox |
| Valkey and Celery | notification delivery outside the call transaction |
| Caddy | reverse proxy for UI and API on a single origin |
| Vanilla HTML, CSS and JavaScript | visitor, operator and manager interfaces |
| JWT and Argon2 | staff authentication |
| Docker Compose | reproducible setup |

The server is a set of domain modules, each with a schema, repository, service and HTTP handler.
External systems plug in through ports in `backend/query_service/integrations/`.
The API contract is available at `/api/docs`. Secrets live in `.env`.

The entire stack is built from components that can run on-premises without cloud SaaS: PostgreSQL, Python, Valkey (Redis protocol), Caddy and a framework-free browser client.

### Roles

| Role | Who | Permissions |
|---|---|---|
| `operator` | window clerk | open and close their window, call, serve, return to queue, redirect, mark no-show, add walk-ins, report a problem |
| `admin` | branch manager | windows and services, priority rules, branch queue, daily analytics, branch staff accounts, QR poster, ticket history, problem reports |
| `root` | network administrator | branch catalog and any account |

Operators and managers are bound to a single `department_id`.
`root` is not tied to any branch.

### Identifiers

The API, QR codes and ticket sessions use UUIDs.

People see human-friendly values instead:

- branch code (`DEMO01`) and address;
- service name;
- ticket number (`П-001`, `С-014`);
- window label (`Окно 1`, i.e. "Window 1").

A ticket number is unique within a branch for one queue calendar day (`Europe/Moscow` by default).
The prefix is derived from the service type: parcels — `П`, letters — `М`, payments — `К`, pensions — `С`, other — `У`.
The counter is incremented atomically in PostgreSQL, so concurrent issuance never produces duplicate numbers.

## Features

### Visitor

- choose a branch and a service;
- book a free slot (date and time);
- get a ticket via QR in the hall: phone camera or the branch page;
- ticket status, estimated wait time, and window number once called;
- cancel a booking while the ticket is `queued`;
- session stored in `localStorage` and the URL: after a connection drop the visitor gets back to their ticket;
- status polling every 5 seconds while the ticket is active.

A booking creates a ticket with source `web` and consumes slot capacity.
A QR check-in creates a ticket with source `qr` and no slot.
No sign-in or app installation required.

### Operator

- open and close a window, choose the set of services for the shift;
- one window, one operator: an occupied window or a second seat triggers a conflict;
- add a customer from the walk-in line (`walk-in`);
- call the next customer, start and finish service;
- return a customer to the queue or redirect them to another service;
- mark a called customer as a no-show;
- ticket source shown on the card: booking, QR, walk-in;
- report a technical or operational problem.

The queue order on screen matches the server-side `call-next`.
The server returns the next eligible ticket, and the operator calls whoever the API returned.

### Branch Manager

- branch windows and the services available at each window;
- branch priority rules (channel bonuses and wait thresholds);
- real-time queue and unfinished tickets;
- daily analytics: customers served, average and maximum wait, window utilization, ticket sources, hourly breakdown;
- ticket status change history;
- branch staff accounts and password changes;
- branch QR poster;
- problem reports.

### Server Guarantees

- a customer is never assigned to two windows: the window is locked and the ticket is taken with `FOR UPDATE SKIP LOCKED`;
- the entire queue state lives in the database, so an API restart loses nothing;
- every status change is written to the audit log;
- invalid requests get a meaningful status code (`400`, `401`, `403`, `404`, `409`, `422`);
- `/api/health` responds as long as the process is alive;
- logs are structured by timestamp, level and logger name.

## Queue Algorithm

A single SQL ordering covers bookings, QR tickets and walk-ins.
Rules are stored per branch and can be changed by the manager without recalculating tickets already issued.

`priority_key` stores the starting point: the slot start for bookings, the arrival time for QR and walk-ins.
The channel bonus is not baked into the key.
At call time the server computes the effective priority:

```
effective = priority_key − bonus(source)
```

Lower values are called first.
A booking with a 5-minute bonus is ranked as if it had arrived five minutes before its slot.

### Who Can Be Called

- QR and walk-in tickets are eligible immediately after issuance.
- A booking becomes eligible at the start of its slot and remains so until `max_wait_web` expires.
- An expired booking is cancelled as a no-show (`canceled`, reason `noshow`) on the next `call-next` or ticket lookup.

### `ORDER BY` Rules

1. Overdue QR and walk-in tickets (waited longer than `max_wait_*`) go first. This caps the wait time for customers who came in off the street.
2. Effective priority, ascending.
3. `created_at`, ascending: FIFO within the same level.

A booking is ranked by its slot time, not by when it was made.
Long-waiting walk-in and QR tickets are lifted by anti-starvation once their wait crosses the branch threshold.

### Defaults

A new branch inherits defaults from the server settings.
The manager can then adjust them in minutes from the dashboard; the API stores seconds.

| Parameter | Default | Meaning |
|---|---|---|
| `bonus_web` | 300 s (5 min) | advantage for pre-booked visits |
| `bonus_qr` | 0 | QR tickets are ranked by arrival time |
| `bonus_walk_in` | 0 | walk-ins are ranked by arrival time |
| `max_wait_web` | 900 s (15 min) | booking expires this long after the slot start |
| `max_wait_qr` | 1200 s (20 min) | anti-starvation threshold for QR |
| `max_wait_walk_in` | 1200 s (20 min) | anti-starvation threshold for walk-ins |

### Edge Cases

**Two windows call at the same time.**
Each window locks itself and selects a ticket with `SKIP LOCKED`.
A ticket can never end up at two windows.

**Closing a window with an active customer.**
If a ticket is `called` or `serving`, the API responds with `409`.
The operator must first finish service, return the customer to the queue, redirect them or mark a no-show.
The ticket stays at the window until the operator explicitly releases it.

**Redirect.**
The ticket becomes a walk-in for the new service: the slot is cleared and `priority_key` is recalculated from the current moment.
The original channel and slot are kept in `origin_*` fields for analytics.

**Return to queue.**
The customer is `queued` again for the same service, the window is freed, and priority is recalculated from the current time.

**No-show.**
The ticket moves to `canceled` with reason `NOSHOW`, the booked slot is released, and a `ticket.noshow` event goes to the outbox.

## Getting Started

You need Docker and Docker Compose.
[Just](https://github.com/casey/just) is handy but optional: every step below also has a plain Compose equivalent.

### 1. Environment Variables

```bash
cp .env.example .env
```

Or: `just env`.

For a local demo, set the following in `.env`:

```env
QUERY_SERVICE_JWT_SECRET="dev-jwt-secret-change-me-32bytes-min"
QUERY_SERVICE_BOOTSTRAP_USERNAME="root"
QUERY_SERVICE_BOOTSTRAP_PASSWORD="change-me"
QUERY_SERVICE_SEED_API_URL="http://127.0.0.1:8000"
QUERY_SERVICE_FRONTEND_ORIGIN="http://localhost:18080"
QUERY_SERVICE_VISITOR_PATH="/src/visitor.html"
```

`SEED_API_URL` is the API address the seed script calls from the host.
`FRONTEND_ORIGIN` is the origin embedded in the visitor QR code.

### 2. Start the Stack

```bash
just run
```

Equivalent:

```bash
docker compose up --build
```

This starts the API, PostgreSQL, migrations, `root` bootstrap, Valkey, the Celery worker, Celery beat, the frontend and Caddy.

Wait until the API responds to the health check:

```bash
curl http://localhost:8000/api/health
```

| What | URL |
|---|---|
| UI | http://localhost:18080 |
| OpenAPI | http://localhost:8000/api/docs |
| Health check | http://localhost:8000/api/health |

### 3. Load Demo Data

In **another** terminal, while the stack is running:

```bash
just seed
```

Equivalent, if `uv` is installed on the host:

```bash
uv run -m query_service.seed_demo
```

Or from the API container:

```bash
docker compose exec api python -m query_service.seed_demo
```

This creates branches `DEMO01` and `DEMO02`, six services, windows, slots for today and tomorrow, and manager and operator accounts in each branch.

| Login | Role | Password | Branch |
|---|---|---|---|
| `admin` | manager | `password` | DEMO01 or DEMO02 |
| `operator` | operator | `password` | DEMO01 or DEMO02 |
| `root` | network | value of `QUERY_SERVICE_BOOTSTRAP_PASSWORD` | — |

The seed is idempotent: re-running it creates whatever is missing and leaves already issued tickets intact.

### 4. Quick Walkthrough

1. Open http://localhost:18080 → **Book a visit** (*Записаться в отделение*), choose `DEMO01`, a service and a slot. Note the ticket number.
2. Sign in as `operator` to the same branch at http://localhost:18080/src/login.html. Open a window and call the next customer.
3. Go back to the visitor's ticket (`/?view=ticket` or the *Вернуться к моему талону* / "Back to my ticket" link): the called status and window number should appear.
4. Signing in with the same operator from a second browser to take another window is rejected — the seat is taken. To test concurrent calls, create a second operator from the manager dashboard.
5. As manager `admin`: queue rules, daily analytics, ticket history, QR poster.

### Deploying to a VPS

Ports 80 and 443 are exposed; external database and API ports stay closed:

```bash
just prod
```

Equivalent:

```bash
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
```

In `.env`, set `SITE_ADDRESS` (the Caddy host, e.g. `185-12-34-56.nip.io`) and a public `QUERY_SERVICE_FRONTEND_ORIGIN`.

### Development Without the Full Compose Stack

```bash
just run-be      # API, DB, migrations, bootstrap; http://localhost:8000
just frontend    # pages at http://localhost:4173
just worker      # Celery worker
just beat        # Celery beat
```

The browser client calls `/api` on the same origin.
The full Compose stack with Caddy is the primary way to demo and test the project.

## Project Structure

```
backend/query_service/     queue server
  api/                    routes, health check, OpenAPI assembly
  modules/                domains: auth, tickets, windows, slots, …
  integrations/           ports for external systems (notifications)
  database/               SQLAlchemy models
  migrations/             Alembic
  seed_demo.py            demo catalog via the REST API
  bootstrap_staff.py      creates root from .env
frontend/                 web UI (ES modules, no framework)
  src/tickets/            visitor ticket session and API
  src/staff/              staff adapters
  src/shared/             fetch, JWT, identifiers
proxy/                    Caddy: UI + /api
docs/technical_task.md    hackathon brief (in Russian)
docker-compose.yml        local stack
docker-compose.vps.yml    overlay for ports 80/443
justfile                  development commands
```

Branch resources are nested under `/api/departments/{department_id}/…`: services, windows, slots, tickets, problems, analytics.

## Development Commands

| Command | Purpose |
|---|---|
| `just` | list commands |
| `just env` | create `.env` from the example |
| `just run` | full stack |
| `just prod` | stack with the VPS overlay |
| `just run-be` | API only |
| `just frontend` | UI dev server |
| `just seed` | demo data |
| `just fresh` | reset DB, run migrations, create root |
| `just migrate` | apply migrations |
| `just gen_migrations "…"` | generate a new migration |
| `just test` | backend and frontend tests |
| `just fmt` / `just lint` | format and lint Python |
| `npm --prefix frontend run format` | format the frontend with Prettier |
| `just logs api` | service logs |
| `just psql` | PostgreSQL console |
| `just down` | stop Compose and remove volumes |

Server environment variables are prefixed with `QUERY_SERVICE_`.

## Notifications

An event is written to the `notification_outbox` table in the same transaction as the ticket change.
Rolling back the transaction removes both the status change and the outbox record.
If the gateway is unavailable, the message stays `pending`: the customer has already been called, and delivery is retried.

```
call-next / noshow / approaching
        │
        ▼
  PostgreSQL outbox   ──Celery beat──►  Celery worker
        │                                    │
        │                                    ▼
        │                            NotificationGateway
        │                                    │
        └────── status sent / failed ────────┘
```

### Events

| Event | When | Payload |
|---|---|---|
| `ticket.called` | an operator called the ticket | ticket number, window |
| `queue.approaching` | no more than `notify_approaching_ahead` people (2 by default) are ahead of the customer | ticket number, estimated wait |
| `ticket.noshow` | an operator marked a no-show | ticket number, window |

Re-enqueueing the same event with the same idempotency key is ignored.
The call key is `{ticket_id}:ticket.called:{called_at}`.

### Demo Adapter

`QUERY_SERVICE_NOTIFY_ADAPTER=demo` (the default).
A successful delivery is logged as `notification.delivered`.
The MVP does not store the customer's phone number, since the demo adapter needs no recipient.
A production adapter would take the delivery address from the customer's Russian Post profile.

Simulating a gateway outage:

```env
QUERY_SERVICE_NOTIFY_FORCE_FAILURE=true
```

The queue keeps working as usual.
Outbox records accumulate as `pending`, then move to `failed` once the retry limit is reached.

### Retries and Timeouts

The worker picks up a batch of due records with row-level locking.
Each send is bounded by `QUERY_SERVICE_NOTIFY_TIMEOUT_SECONDS` (2 s by default).
The delay between attempts grows as `2^attempts` seconds, capped at 60.
After `QUERY_SERVICE_NOTIFY_MAX_ATTEMPTS` (5 by default) the record is marked `failed`.
An invalid payload goes straight to `failed`, since retrying it is pointless.

Beat triggers a drain every `QUERY_SERVICE_NOTIFY_POLL_INTERVAL_SECONDS` (2 s by default).
Delivery state lives in the outbox, so the next beat tick picks up the same `pending` rows.

### Replacing the Demo Adapter with a Production Gateway

1. Implement the `NotificationGateway` protocol (`async def send(message)`) next to `integrations/notifications/demo.py`.
2. Raise `NotificationDeliveryError` when delivery fails.
3. Register the implementation in `create_notification_adapter`.
4. Set `QUERY_SERVICE_NOTIFY_ADAPTER` to the new name.

Only the adapter behind the port changes. `call-next`, the ticket log and the queue rules stay the same.
The queue knows how to do exactly one thing: put an event into the outbox.

## Roadmap and Scaling

### Product After the MVP

- wait-time forecasting based on the number of open windows and service duration;
- recommending that the manager open an extra window as the queue grows;
- a tablet kiosk in the hall and a call display board;
- a multi-branch dashboard for regional managers;
- an accessibility mode for visually impaired users;
- staff deactivation and transfers between branches;
- a per-branch time zone instead of a single `Europe/Moscow`;
- a production notification adapter and a recipient ID in the customer profile.

### Network Scale: 40,000 Branches

The queue is isolated by `department_id`.
This key is the shard boundary: tickets, windows, slots, the audit log and the outbox of one branch never overlap with another.
The API no longer keeps sessions in process memory, so horizontal scaling means FastAPI replicas behind the proxy.

A back-of-the-envelope load estimate, not the result of an MVP load test:

- peak load shifts across time zones, so the simultaneous maximum is well below "all 40,000 at once";
- a single branch at peak has a handful of windows and dozens of tickets in the queue, not millions of rows;
- hot queries (`call-next`, ticket issuance) are point lookups that are already serialized by locks within a branch.

#### Stage 1. Pilot

A few dozen branches on a single PostgreSQL cluster.
Production notifications, readiness probes, metrics for calls and the outbox, a branch catalog, and kiosks in larger locations.
Priority rules still live on the branch, with defaults in the server configuration.

#### Stage 2. Regions

PostgreSQL shards by `department_id` range or by macro-region.
API routing by branch key.
Daily analytics are computed within the shard; only roll-ups (served, wait time, utilization) are sent to the center, not raw tickets.
Live queue updates (WebSocket or SSE) instead of polling.
Priority policies can be defined centrally and inherited by branches.
Booking from the Russian Post mobile app becomes just another `web` ticket issuance adapter — same queue.

#### Stage 3. The Long Tail

Branches with unreliable connectivity get a lightweight node: local issuance and calling, with the audit log synced once the connection is back.
The branch catalog is federated: the center owns codes and addresses, each branch owns its queue.
If the connection to the center is lost, a window keeps serving already issued tickets; new QR and online bookings join the queue once the link is restored.

At this scale, notifications still go through the outbox: the customer call completes within the branch transaction, independent workers drain the sharded outbox, and the idempotency key makes redelivery safe.
