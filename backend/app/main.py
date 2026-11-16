from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, SessionLocal, get_db
from .models import AdminUser
from .security import hash_password
from .routes.auth import router as auth_router, get_current_admin
from .routes.business_settings import router as business_settings_router
from .routes.customers import router as customers_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = settings.admin_email.lower()
        existing = db.query(AdminUser).filter(AdminUser.email == email).first()
        if not existing:
            db.add(AdminUser(email=email, password_hash=hash_password(settings.admin_password)))
            db.commit()
    finally:
        db.close()
    yield

app = FastAPI(title="Cable Manager API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router)
app.include_router(business_settings_router)
app.include_router(customers_router)

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(__import__("sqlalchemy").text("SELECT 1"))
    return {"status": "ok", "database": "connected"}

@app.get("/api/dashboard/summary")
def dashboard_summary(current_admin: AdminUser = Depends(get_current_admin)):
    # Phase 1 & 2: no customer/payment data exists yet; return explicit empty state.
    return {
        "total_customers": 0,
        "expected_collection": 0,
        "collected": 0,
        "outstanding": 0,
        "data_status": "awaiting_customer_import"
    }
