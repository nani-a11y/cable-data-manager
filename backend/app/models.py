from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class BusinessSettings(Base):
    __tablename__ = "business_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_business_setting_row"),
        CheckConstraint("billing_day >= 1 AND billing_day <= 28", name="valid_billing_day"),
        CheckConstraint("grace_period_days >= 0 AND grace_period_days <= 30", name="valid_grace_period_days"),
        CheckConstraint("default_monthly_amount > 0", name="positive_default_monthly_amount"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="Asia/Kolkata")
    default_monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("300.00"))
    billing_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    late_payment_policy: Mapped[str | None] = mapped_column(String(50), nullable=True, default="none")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
