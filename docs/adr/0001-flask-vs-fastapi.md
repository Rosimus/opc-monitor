# ADR-0001: Flask vs FastAPI for the REST API

- **Status:** Accepted
- **Date:** 2026-09
- **Context:** choosing a web framework for the OPC Monitor backend

## Context

The backend service needs a web framework that supports:

- REST API with auto-generated documentation
- JWT authentication
- Prometheus metrics
- OpenTelemetry instrumentation
- Rate limiting and security headers
- HTML template rendering for the UI

This is a portfolio project: development speed and stack recognizability for recruiters matter.

## Decision

**Flask was chosen.**

Key reasons:

- **Mature extension ecosystem** — `flask-jwt-extended`, `flask-limiter`, `flask-talisman`, `flask-cors`, `flask-swagger-ui`. FastAPI equivalents are either hand-rolled middleware or less mature packages.
- **Swagger generation** works through `flask-swagger-ui` + a static `swagger.json`. FastAPI gives this "for free" via Pydantic, but for our API size it is not critical.
- **Jinja2 templating out of the box.** In FastAPI, HTML rendering requires wiring up `Jinja2Templates` manually.
- **Familiar stack.** More prior experience with Flask — less time spent learning framework specifics.

## Consequences

**Pros:**

- Fast development — extensions cover routine tasks (JWT, rate limiting, security headers) out of the box.
- Aligns with the "classic" Python stack, familiar to most recruiters.
- Large volume of examples and articles.

**Cons:**

- No automatic request validation (FastAPI has Pydantic). Validation is done manually via `request.get_json(silent=True)` + explicit checks.
- No `async/await` — WSGI server (Gunicorn + gthread workers). Adequate for our load profile (tens of RPS), but FastAPI would be preferable at 10k+ RPS.
- Slower in benchmarks (WSGI vs ASGI).

**Migration:** if the project grows into a microservice architecture, individual endpoints can be rewritten in FastAPI without touching the rest of the application — both can coexist behind an API gateway.

## Alternatives considered

**FastAPI** — an excellent choice for new projects with high throughput and validation requirements. For this pet project it is overkill: we would need to introduce Pydantic schemas for every endpoint and pick up new libraries for JWT / rate limiting.

**Aiohttp** — too low-level, lots of boilerplate. Not worth it for a CRUD application.

**Django + DRF** — a "heavy" framework with ORM, admin, migrations. Overkill for our scope; Django ORM is also less flexible than raw SQL via SQLAlchemy in our case.