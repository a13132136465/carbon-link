import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select
from app.api import router
from app.config import settings
from app.database import SessionLocal
from app.models import Role, User
from app.security import hash_password

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        with SessionLocal() as db:
            exists = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower()))
            if not exists:
                db.add(User(email=settings.bootstrap_admin_email.lower(), password_hash=hash_password(settings.bootstrap_admin_password), display_name="System Administrator", role=Role.ADMIN))
                db.commit()
    yield

app = FastAPI(title="CarbonLink", version="1.0.0", description="碳积分登记、核证、交易与注销平台", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])
app.include_router(router)

@app.get("/health/live", tags=["health"])
def live(): return {"status": "ok"}

@app.get("/health/ready", tags=["health"])
def ready():
    with SessionLocal() as db: db.execute(text("SELECT 1"))
    return {"status": "ready"}

