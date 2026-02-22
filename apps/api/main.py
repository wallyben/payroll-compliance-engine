from fastapi import FastAPI
from apps.api.db import Base, engine
from apps.api.routers import auth, uploads, runs, mappings

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Payroll Compliance OS (IE) v1")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
app.include_router(mappings.router, prefix="/mappings", tags=["mappings"])
app.include_router(runs.router, prefix="/runs", tags=["runs"])
