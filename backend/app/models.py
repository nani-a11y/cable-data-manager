from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
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


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("uq_customers_box_number_lower", func.lower(text("box_number")), unique=True),
        CheckConstraint("monthly_amount > 0", name="positive_customer_monthly_amount"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    box_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    area: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    invoices = relationship("Invoice", back_populates="customer", passive_deletes="all")
    payments = relationship("Payment", back_populates="customer", passive_deletes="all")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("customer_id", "billing_month", name="uq_invoice_customer_billing_month"),
        CheckConstraint("amount > 0", name="positive_invoice_amount"),
        CheckConstraint("paid_amount >= 0", name="non_negative_paid_amount"),
        CheckConstraint("paid_amount <= amount", name="paid_amount_within_invoice_amount"),
        CheckConstraint("status IN ('pending', 'partial', 'paid')", name="valid_invoice_status"),
        CheckConstraint("length(billing_month) = 7", name="valid_billing_month_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    billing_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    customer = relationship("Customer", back_populates="invoices")
    allocations = relationship("PaymentAllocation", back_populates="invoice", passive_deletes="all")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_payment_amount"),
        CheckConstraint("payment_method IN ('cash', 'upi', 'other')", name="valid_payment_method"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), default="cash", nullable=False)
    paid_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    customer = relationship("Customer", back_populates="payments")
    allocations = relationship("PaymentAllocation", back_populates="payment", passive_deletes="all")


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="positive_allocated_amount"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    payment = relationship("Payment", back_populates="allocations")
    invoice = relationship("Invoice", back_populates="allocations")
