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
from .routes.billing import router as billing_router
from .routes.payments import router as payments_router
from .routes.reports import router as reports_router
from .services.billing import run_startup_billing_catchup

@asynccontextmanager
async def lifespan(app: FastAPI):
    # In development and testing, automatically ensure schema exists.
    # In production, schema must be managed explicitly via Alembic migrations.
    if settings.app_env != "production":
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        email = settings.admin_email.lower()
        existing = db.query(AdminUser).filter(AdminUser.email == email).first()
        if not existing:
            db.add(AdminUser(email=email, password_hash=hash_password(settings.admin_password)))
            db.commit()
    except Exception:
        db.rollback()
        if settings.app_env == "production":
            import logging
            logging.getLogger("uvicorn.error").warning(
                "Production startup: unable to query admin_users table. "
                "Ensure database migrations have been executed via 'alembic upgrade head'."
            )
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
app.include_router(billing_router)
app.include_router(payments_router)
app.include_router(reports_router)

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(__import__("sqlalchemy").text("SELECT 1"))
    return {"status": "ok", "database": "connected"}

@app.get("/api/dashboard/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    from datetime import date
    current_month = date.today().strftime("%Y-%m")
    from .routes.reports import get_monthly_review
    review = get_monthly_review(billing_month=current_month, db=db, current_admin=current_admin)
    data_status = "live" if review.total_active_customers > 0 else "awaiting_customer_import"
    return {
        "total_customers": review.total_active_customers,
        "expected_collection": float(review.estimated_amount),
        "collected": float(review.amount_collected),
        "outstanding": float(review.pending_amount),
        "data_status": data_status,
    }
