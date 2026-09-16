from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from lume.accounts.api import router as accounts_router
from lume.auth.api import router as auth_router
from lume.budgets.api import router as budgets_router
from lume.categories.api import router as categories_router
from lume.core import models as domain_models  # noqa: F401
from lume.core.config import get_settings
from lume.core.database import SessionFactory
from lume.recurring.api import router as recurring_router
from lume.reporting.api import router as reporting_router
from lume.transactions.api import router as transactions_router
from lume.users.api import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield


settings = get_settings()
app = FastAPI(
    title="Lume API",
    version="0.1.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID"],
    )

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(accounts_router)
app.include_router(categories_router)
app.include_router(transactions_router)
app.include_router(budgets_router)
app.include_router(recurring_router)
app.include_router(reporting_router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "lume-api"}


@app.get("/readyz", include_in_schema=False)
def readyz(response: Response) -> dict[str, str]:
    try:
        with SessionFactory() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ready"}
