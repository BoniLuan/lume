# ADR 0001: Modular monolith with MariaDB

Status: accepted, 2026-09-16.

Lume starts as one FastAPI application split into financial domain modules, one
React client, and one MariaDB 11.4 LTS database. A separate Nginx gateway owns
static delivery and API proxying.

The expected load and team size do not justify distributed services. Module
boundaries preserve a path to later extraction if measured operational needs arise.
MariaDB is intentional portfolio scope and provides exact decimal storage,
constraints, transactional updates, and familiar recovery tools. Each environment
owns a database, credential set, volume, and networks.
