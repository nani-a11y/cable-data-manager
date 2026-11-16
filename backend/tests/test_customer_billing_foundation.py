"""Phase 3 Step 3.1: Customer & Billing Database Foundation Tests

Executed strictly against disposable PostgreSQL.
Validates:
1. Migration upgrade to head.
2. Alembic schema check with zero drift.
3. Migration downgrade to 0002_business_settings.
4. Re-upgrade to head.
5. Customer box number case-insensitive uniqueness.
6. Customer display ID uniqueness.
7. Customer and invoice monetary precision and boundaries.
8. Invoice duplicate customer/month rejection.
9. Invoice paid_amount constraints (non-negative and <= amount).
10. Payment and allocation positive amount constraints.
11. Foreign-key deletion protection for financial records (RESTRICT).
12. Customer deactivation preserves associated financial records.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import os
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config

from app.models import AdminUser, BusinessSettings, Customer, Invoice, Payment, PaymentAllocation

DISPOSABLE_PG_URL = os.environ.get(
    "DISPOSABLE_PG_URL",
    "postgresql+psycopg://test_user:disposablepass@127.0.0.1:5434/disposable_billing_test",
)


@pytest.fixture(scope="module")
def pg_engine():
    """Ensure disposable PostgreSQL connection is active."""
    engine = sa.create_engine(DISPOSABLE_PG_URL)
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Disposable PostgreSQL not reachable at {DISPOSABLE_PG_URL}: {exc}")
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def alembic_cfg():
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    alembic_ini = os.path.join(backend_dir, "alembic.ini")
    cfg = Config(alembic_ini)
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    cfg.set_main_option("sqlalchemy.url", DISPOSABLE_PG_URL)

    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = DISPOSABLE_PG_URL
    yield cfg
    if old_url is not None:
        os.environ["DATABASE_URL"] = old_url
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture(scope="function")
def pg_session(pg_engine):
    """Provides a transactional session on disposable PostgreSQL with clean tables."""
    Session = sessionmaker(bind=pg_engine)
    session = Session()

    # Clean existing data before each test
    with pg_engine.begin() as conn:
        conn.execute(sa.text("TRUNCATE TABLE payment_allocations, payments, invoices, customers CASCADE"))

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# -------------------------------------------------------------------------
# 1-4: Alembic Migration Lifecycle on Disposable PostgreSQL
# -------------------------------------------------------------------------

def test_01_migration_upgrade_to_head(alembic_cfg, pg_engine):
    """1. Migration upgrade to head on clean disposable PostgreSQL."""
    command.upgrade(alembic_cfg, "head")

    inspector = sa.inspect(pg_engine)
    tables = inspector.get_table_names()

    assert "admin_users" in tables
    assert "business_settings" in tables
    assert "customers" in tables
    assert "invoices" in tables
    assert "payments" in tables
    assert "payment_allocations" in tables
    assert "alembic_version" in tables

    # Verify customers columns
    cust_cols = {col["name"] for col in inspector.get_columns("customers")}
    assert {"id", "display_id", "name", "phone", "box_number", "area", "monthly_amount", "is_active", "created_at", "updated_at"}.issubset(cust_cols)

    # Verify invoices columns
    inv_cols = {col["name"] for col in inspector.get_columns("invoices")}
    assert {"id", "invoice_number", "customer_id", "billing_month", "amount", "paid_amount", "status", "issued_date", "created_at", "updated_at"}.issubset(inv_cols)

    # Verify payments columns
    pay_cols = {col["name"] for col in inspector.get_columns("payments")}
    assert {"id", "receipt_number", "customer_id", "amount", "payment_method", "paid_date", "notes", "is_reversed", "reversal_reason", "reversed_at", "created_at"}.issubset(pay_cols)

    # Verify payment_allocations columns
    alloc_cols = {col["name"] for col in inspector.get_columns("payment_allocations")}
    assert {"id", "payment_id", "invoice_id", "allocated_amount", "created_at"}.issubset(alloc_cols)


def test_02_alembic_schema_zero_drift(alembic_cfg):
    """2. Alembic schema check with zero drift."""
    # command.check raises CommandError if drift is detected
    command.check(alembic_cfg)


def test_03_migration_downgrade_to_0002(alembic_cfg, pg_engine):
    """3. Migration downgrade to 0002_business_settings drops only Phase 3 tables."""
    command.downgrade(alembic_cfg, "0002_business_settings")

    inspector = sa.inspect(pg_engine)
    tables = inspector.get_table_names()

    # Phase 3 tables dropped
    assert "customers" not in tables
    assert "invoices" not in tables
    assert "payments" not in tables
    assert "payment_allocations" not in tables

    # Phase 1 & 2 tables preserved
    assert "business_settings" in tables
    assert "admin_users" in tables
    assert "alembic_version" in tables


def test_04_reupgrade_to_head(alembic_cfg, pg_engine):
    """4. Re-upgrade to head successfully restores all 4 tables."""
    command.upgrade(alembic_cfg, "head")

    inspector = sa.inspect(pg_engine)
    tables = inspector.get_table_names()
    assert "customers" in tables
    assert "invoices" in tables
    assert "payments" in tables
    assert "payment_allocations" in tables


# -------------------------------------------------------------------------
# 5-12: Core Model & Constraint Validation Tests
# -------------------------------------------------------------------------

def test_05_customer_box_number_case_insensitive_uniqueness(pg_session):
    """5. Customer box number must be strictly unique (case-insensitive and trimmed)."""
    c1 = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="STB-98421",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
        is_active=True,
    )
    pg_session.add(c1)
    pg_session.commit()

    # Attempt inserting duplicate box number in lowercase: "stb-98421"
    c2 = Customer(
        display_id="C-0002",
        name="Suresh Sharma",
        phone="9876543211",
        box_number="stb-98421",
        area="Sector 5",
        monthly_amount=Decimal("350.00"),
        is_active=True,
    )
    pg_session.add(c2)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_06_customer_display_id_uniqueness(pg_session):
    """6. Customer display ID must be strictly unique."""
    c1 = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="BOX-A1",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
        is_active=True,
    )
    pg_session.add(c1)
    pg_session.commit()

    # Duplicate display_id
    c2 = Customer(
        display_id="C-0001",
        name="Anil Verma",
        phone="9876543212",
        box_number="BOX-A2",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
        is_active=True,
    )
    pg_session.add(c2)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_07_monetary_precision_and_boundaries(pg_session):
    """7. Customer and invoice monetary precision and boundaries (Numeric(12,2))."""
    # Max boundary Numeric(12, 2) is 9999999999.99
    c_max = Customer(
        display_id="C-MAX",
        name="High Tier Corp",
        phone="9876543210",
        box_number="BOX-MAX",
        area="Central",
        monthly_amount=Decimal("9999999999.99"),
        is_active=True,
    )
    pg_session.add(c_max)
    pg_session.commit()
    pg_session.refresh(c_max)
    assert c_max.monthly_amount == Decimal("9999999999.99")

    # Positive check constraint on customer monthly_amount (zero not allowed)
    c_zero = Customer(
        display_id="C-ZERO",
        name="Zero Amount",
        phone="9876543210",
        box_number="BOX-ZERO",
        area="Central",
        monthly_amount=Decimal("0.00"),
        is_active=True,
    )
    pg_session.add(c_zero)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Positive check constraint on invoice amount (zero not allowed)
    inv_zero = Invoice(
        invoice_number="INV-ZERO",
        customer_id=c_max.id,
        billing_month="2026-11",
        amount=Decimal("0.00"),
        paid_amount=Decimal("0.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv_zero)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_08_invoice_duplicate_customer_month_rejection(pg_session):
    """8. Unique constraint prevents duplicate invoices for same customer and month."""
    cust = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="BOX-1",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
    )
    pg_session.add(cust)
    pg_session.commit()

    inv1 = Invoice(
        invoice_number="INV-202611-0001",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("0.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv1)
    pg_session.commit()

    # Second invoice for same customer and same billing_month must fail
    inv2 = Invoice(
        invoice_number="INV-202611-0002",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("0.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv2)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_09_invoice_paid_amount_constraints(pg_session):
    """9. Invoice paid_amount constraints: non-negative and <= amount."""
    cust = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="BOX-1",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
    )
    pg_session.add(cust)
    pg_session.commit()

    # Negative paid_amount violates non_negative_paid_amount
    inv_neg = Invoice(
        invoice_number="INV-NEG",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("-10.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv_neg)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # paid_amount exceeding invoice amount violates paid_amount_within_invoice_amount
    inv_over = Invoice(
        invoice_number="INV-OVER",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("350.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv_over)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Invalid status violates valid_invoice_status
    inv_bad_status = Invoice(
        invoice_number="INV-BAD-STATUS",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("0.00"),
        status="unknown_status",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv_bad_status)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_10_payment_and_allocation_positive_amount_constraints(pg_session):
    """10. Payment and allocation amount must be strictly positive."""
    cust = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="BOX-1",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
    )
    pg_session.add(cust)
    pg_session.commit()

    # Payment amount <= 0 violates positive_payment_amount
    p_zero = Payment(
        receipt_number="REC-ZERO",
        customer_id=cust.id,
        amount=Decimal("0.00"),
        payment_method="cash",
        paid_date=date(2026, 11, 5),
    )
    pg_session.add(p_zero)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Invalid payment method violates valid_payment_method
    p_invalid_method = Payment(
        receipt_number="REC-METHOD",
        customer_id=cust.id,
        amount=Decimal("100.00"),
        payment_method="bitcoin",
        paid_date=date(2026, 11, 5),
    )
    pg_session.add(p_invalid_method)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Valid payment & invoice for allocation testing
    p_valid = Payment(
        receipt_number="REC-VALID",
        customer_id=cust.id,
        amount=Decimal("300.00"),
        payment_method="upi",
        paid_date=date(2026, 11, 5),
    )
    inv_valid = Invoice(
        invoice_number="INV-VALID",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("0.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add_all([p_valid, inv_valid])
    pg_session.commit()

    # Allocation amount <= 0 violates positive_allocated_amount
    alloc_zero = PaymentAllocation(
        payment_id=p_valid.id,
        invoice_id=inv_valid.id,
        allocated_amount=Decimal("0.00"),
    )
    pg_session.add(alloc_zero)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_11_foreign_key_deletion_protection(pg_session):
    """11. Deletion of customer with financial records is blocked by RESTRICT constraint."""
    cust = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="BOX-1",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
    )
    pg_session.add(cust)
    pg_session.commit()

    inv = Invoice(
        invoice_number="INV-001",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("300.00"),
        status="paid",
        issued_date=date(2026, 11, 1),
    )
    pay = Payment(
        receipt_number="REC-001",
        customer_id=cust.id,
        amount=Decimal("300.00"),
        payment_method="cash",
        paid_date=date(2026, 11, 5),
    )
    pg_session.add_all([inv, pay])
    pg_session.commit()

    alloc = PaymentAllocation(
        payment_id=pay.id,
        invoice_id=inv.id,
        allocated_amount=Decimal("300.00"),
    )
    pg_session.add(alloc)
    pg_session.commit()

    # Attempting to delete the customer must fail because financial records exist
    pg_session.delete(cust)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Attempting to delete an allocated invoice must fail
    pg_session.delete(inv)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_12_customer_deactivation_preserves_associated_financial_records(pg_session):
    """12. Customer deactivation is the supported lifecycle operation; all records remain intact."""
    cust = Customer(
        display_id="C-0001",
        name="Ramesh Kumar",
        phone="9876543210",
        box_number="BOX-1",
        area="Sector 4",
        monthly_amount=Decimal("300.00"),
        is_active=True,
    )
    pg_session.add(cust)
    pg_session.commit()

    inv = Invoice(
        invoice_number="INV-001",
        customer_id=cust.id,
        billing_month="2026-11",
        amount=Decimal("300.00"),
        paid_amount=Decimal("0.00"),
        status="pending",
        issued_date=date(2026, 11, 1),
    )
    pg_session.add(inv)
    pg_session.commit()

    # Deactivate customer
    cust.is_active = False
    pg_session.commit()
    pg_session.refresh(cust)

    assert cust.is_active is False

    # Financial records remain completely intact and linked
    persisted_inv = pg_session.query(Invoice).filter(Invoice.customer_id == cust.id).first()
    assert persisted_inv is not None
    assert persisted_inv.invoice_number == "INV-001"
    assert persisted_inv.amount == Decimal("300.00")
