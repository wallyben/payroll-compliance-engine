from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.db import Base, engine
from apps.api.routers import auth, uploads, runs, mappings
from apps.api.logging_config import configure_logging, request_logging_middleware

Base.metadata.create_all(bind=engine)

configure_logging()
app = FastAPI(title="Payroll Compliance OS (IE) v1")
app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
app.include_router(mappings.router, prefix="/mappings", tags=["mappings"])
app.include_router(runs.router, prefix="/runs", tags=["runs"])
