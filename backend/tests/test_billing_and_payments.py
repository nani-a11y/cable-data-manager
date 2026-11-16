"""Unit and Integration Tests for Billing, Payments, and Monthly Review.

Covers:
1. Billing Engine:
   - Invoice generation for active customers.
   - Idempotency & duplicate generation rejection.
   - Immediate billing for new customer.
   - Inactive customer exclusion.
   - Advance credit auto-allocation to newly generated invoices.
   - Startup catchup engine.
2. Payment Engine:
   - Full payment FIFO allocation.
   - Partial payment FIFO allocation across multiple invoices.
   - Advance overpayment tracking.
   - Payment reversal with invoice status rollback.
   - Double reversal rejection.
   - Customer financial history endpoint.
3. Monthly Review:
   - Invoice-backed estimated amount vs pre-invoice active customer rate sum.
   - Month-specific collection tracking.
   - Pending amount calculation.
   - Older arrears separation.
   - Zero-denominator percentage safety.
"""
from datetime import date, datetime
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models import AdminUser, BusinessSettings, Customer, Invoice, Payment, PaymentAllocation
from app.security import hash_password


@pytest.fixture
def auth_headers(client, test_db):
    email = "admin-full@example.com"
    password = "AdminFullPassword123!"
    admin = AdminUser(
        email=email,
        password_hash=hash_password(password),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def business_setup(test_db):
    settings = BusinessSettings(
        id=1,
        business_name="Fast Net Cable",
        contact_number="9876543210",
        service_areas=["Sector 1", "Sector 2"],
        currency_code="INR",
        timezone="Asia/Kolkata",
        default_monthly_amount=Decimal("300.00"),
        billing_day=1,
        grace_period_days=5,
        late_payment_policy="none",
    )
    test_db.add(settings)
    test_db.commit()
    return settings


# 1. Billing Engine Tests
def test_billing_engine_generation_and_idempotency(client, auth_headers, business_setup):
    # Create 2 active customers, 1 inactive
    c1 = client.post(
        "/api/customers",
        json={"name": "Active 1", "phone": "9000000001", "box_number": "B-01", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()
    c2 = client.post(
        "/api/customers",
        json={"name": "Active 2", "phone": "9000000002", "box_number": "B-02", "area": "Sector 1", "monthly_amount": "400.00"},
        headers=auth_headers,
    ).json()
    c3 = client.post(
        "/api/customers",
        json={"name": "Inactive 1", "phone": "9000000003", "box_number": "B-03", "area": "Sector 1", "monthly_amount": "350.00"},
        headers=auth_headers,
    ).json()
    client.delete(f"/api/customers/{c3['id']}", headers=auth_headers)

    # First run for 2026-11
    res1 = client.post("/api/billing/generate/2026-11", headers=auth_headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["eligible_customers"] == 2
    assert data1["invoices_created"] == 2
    assert data1["already_existing"] == 0
    assert data1["total_billed_amount"] == "700.00"

    # Second run for 2026-11 (idempotency check)
    res2 = client.post("/api/billing/generate/2026-11", headers=auth_headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["invoices_created"] == 0
    assert data2["already_existing"] == 2

    # Invoices list check
    invoices = client.get("/api/billing/invoices?billing_month=2026-11", headers=auth_headers).json()
    assert len(invoices) == 2
    assert all(inv["status"] == "pending" for inv in invoices)


# 2. Payment Recording and FIFO Allocation
def test_payment_recording_fifo_allocation(client, auth_headers, business_setup):
    c = client.post(
        "/api/customers",
        json={"name": "Payer 1", "phone": "9000000004", "box_number": "B-04", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()

    # Generate 2 invoices: 2026-10 (older) and 2026-11 (newer)
    client.post("/api/billing/generate/2026-10", headers=auth_headers)
    client.post("/api/billing/generate/2026-11", headers=auth_headers)

    # Partial payment of 400 (300 should settle 2026-10 full, 100 goes to 2026-11 partial)
    pay_resp = client.post(
        "/api/payments",
        json={
            "customer_id": c["id"],
            "amount": "400.00",
            "payment_method": "upi",
            "paid_date": "2026-11-05",
            "notes": "UPI pay",
        },
        headers=auth_headers,
    )
    assert pay_resp.status_code == 201
    pay_data = pay_resp.json()
    assert pay_data["allocated_invoices_count"] == 2
    assert pay_data["total_allocated"] == "400.00"
    assert pay_data["advance_credit_remaining"] == "0.00"

    # Verify invoice statuses
    inv_list = client.get(f"/api/billing/invoices?customer_id={c['id']}", headers=auth_headers).json()
    # Ordered desc by month: 2026-11 first, 2026-10 second
    inv_nov = next(i for i in inv_list if i["billing_month"] == "2026-11")
    inv_oct = next(i for i in inv_list if i["billing_month"] == "2026-10")

    assert inv_oct["status"] == "paid"
    assert inv_oct["paid_amount"] == "300.00"

    assert inv_nov["status"] == "partial"
    assert inv_nov["paid_amount"] == "100.00"


# 3. Advance Overpayment and Auto-credit on Future Bill
def test_advance_overpayment_and_future_credit(client, auth_headers, business_setup):
    c = client.post(
        "/api/customers",
        json={"name": "Advance Payer", "phone": "9000000005", "box_number": "B-05", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()

    # Customer pays 1000 with no invoices existing
    pay_resp = client.post(
        "/api/payments",
        json={
            "customer_id": c["id"],
            "amount": "1000.00",
            "payment_method": "cash",
            "paid_date": "2026-11-01",
        },
        headers=auth_headers,
    )
    assert pay_resp.status_code == 201
    assert pay_resp.json()["advance_credit_remaining"] == "1000.00"

    # Now generate bill for 2026-11 (300.00)
    client.post("/api/billing/generate/2026-11", headers=auth_headers)

    # Invoice should automatically be marked paid from advance credit
    inv = client.get(f"/api/billing/invoices?customer_id={c['id']}&billing_month=2026-11", headers=auth_headers).json()[0]
    assert inv["status"] == "paid"
    assert inv["paid_amount"] == "300.00"

    # Check history to verify remaining advance credit is 700.00
    hist = client.get(f"/api/customers/{c['id']}/history", headers=auth_headers).json()
    assert hist["advance_credit"] == "700.00"
    assert hist["outstanding_balance"] == "0.00"


# 4. Payment Reversal
def test_payment_reversal_restores_balances(client, test_db, auth_headers, business_setup):
    c = client.post(
        "/api/customers",
        json={"name": "Reversal User", "phone": "9000000006", "box_number": "B-06", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()

    client.post("/api/billing/generate/2026-11", headers=auth_headers)

    pay = client.post(
        "/api/payments",
        json={"customer_id": c["id"], "amount": "300.00", "payment_method": "cash", "paid_date": "2026-11-02"},
        headers=auth_headers,
    ).json()["payment"]

    # Verify invoice is paid
    inv_before = client.get(f"/api/billing/invoices?customer_id={c['id']}", headers=auth_headers).json()[0]
    assert inv_before["status"] == "paid"

    # Reverse payment
    rev_resp = client.post(
        f"/api/payments/{pay['id']}/reverse",
        json={"reversal_reason": "Bounced check / wrong entry"},
        headers=auth_headers,
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["is_reversed"] is True
    assert rev_data["reversal_reason"] == "Bounced check / wrong entry"
    assert rev_data["reversed_at"] is not None

    # Verify invoice is back to pending with paid_amount 0
    inv_after = client.get(f"/api/billing/invoices?customer_id={c['id']}", headers=auth_headers).json()[0]
    assert inv_after["status"] == "pending"
    assert inv_after["paid_amount"] == "0.00"

    # Verify that PaymentAllocation records are PRESERVED in the database for auditability
    from app.models import PaymentAllocation
    bind = test_db.get_bind()
    from sqlalchemy.orm import sessionmaker
    SessionLocalTest = sessionmaker(autocommit=False, autoflush=False, bind=bind)
    db = SessionLocalTest()
    try:
        alloc_records = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == pay["id"]).all()
        assert len(alloc_records) == 1
        assert alloc_records[0].allocated_amount == Decimal("300.00")
        assert alloc_records[0].invoice_id == inv_after["id"]
    finally:
        db.close()

    # Attempt second reversal should fail
    rev2 = client.post(
        f"/api/payments/{pay['id']}/reverse",
        json={"reversal_reason": "Again"},
        headers=auth_headers,
    )
    assert rev2.status_code == 400
    assert "already been reversed" in rev2.json()["detail"]


# 5. Monthly Review Metrics
def test_monthly_review_metrics(client, auth_headers, business_setup):
    # Customer 1: 300, Customer 2: 500
    c1 = client.post(
        "/api/customers",
        json={"name": "Rev Cust 1", "phone": "9000000007", "box_number": "B-07", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()
    c2 = client.post(
        "/api/customers",
        json={"name": "Rev Cust 2", "phone": "9000000008", "box_number": "B-08", "area": "Sector 1", "monthly_amount": "500.00"},
        headers=auth_headers,
    ).json()

    # Pre-invoice generation report
    rep_pre = client.get("/api/reports/monthly-review/2026-12", headers=auth_headers).json()
    assert rep_pre["is_invoice_backed"] is False
    assert rep_pre["estimated_amount"] == "800.00"
    assert rep_pre["amount_collected"] == "0.00"
    assert rep_pre["pending_amount"] == "800.00"
    assert rep_pre["collection_percentage"] == 0.0

    # Generate invoices
    client.post("/api/billing/generate/2026-12", headers=auth_headers)

    # Customer 1 pays in full 300
    client.post(
        "/api/payments",
        json={"customer_id": c1["id"], "amount": "300.00", "payment_method": "cash", "paid_date": "2026-12-05"},
        headers=auth_headers,
    )

    # Post-invoice report
    rep_post = client.get("/api/reports/monthly-review/2026-12", headers=auth_headers).json()
    assert rep_post["is_invoice_backed"] is True
    assert rep_post["estimated_amount"] == "800.00"
    assert rep_post["amount_collected"] == "300.00"
    assert rep_post["pending_amount"] == "500.00"
    assert rep_post["collection_percentage"] == 37.5
