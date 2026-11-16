"""Focused Tests for Realigned Features:
1. Customer List Dues and Advance Credit Annotation
2. Chronological Customer Passbook (Khata) with Running Balances
3. Monthly Collection Register with Area and Status Filters
"""
from datetime import date
from decimal import Decimal
import pytest

from app.models import AdminUser, BusinessSettings
from app.security import hash_password


@pytest.fixture
def auth_headers(client, test_db):
    email = "admin-realign@example.com"
    password = "AdminRealignPass123!"
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


def test_customer_list_dues_and_advance_credit(client, auth_headers, business_setup):
    """Test GET /api/customers includes current_outstanding_balance and advance_credit."""
    c1 = client.post(
        "/api/customers",
        json={"name": "Alice Dues", "phone": "9111111111", "box_number": "BOX-D-01", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()

    c2 = client.post(
        "/api/customers",
        json={"name": "Bob Advance", "phone": "9222222222", "box_number": "BOX-D-02", "area": "Sector 2", "monthly_amount": "400.00"},
        headers=auth_headers,
    ).json()

    # Generate billing for 2026-11
    client.post("/api/billing/generate/2026-11", headers=auth_headers)

    # Bob pays 600.00 (400 for invoice + 200 advance)
    client.post(
        "/api/payments",
        json={"customer_id": c2["id"], "amount": "600.00", "payment_method": "upi", "paid_date": "2026-11-02"},
        headers=auth_headers,
    )

    # Fetch list
    resp = client.get("/api/customers", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]

    alice = next(c for c in items if c["id"] == c1["id"])
    assert alice["current_outstanding_balance"] == "300.00"
    assert alice["advance_credit"] == "0.00"

    bob = next(c for c in items if c["id"] == c2["id"])
    assert bob["current_outstanding_balance"] == "0.00"
    assert bob["advance_credit"] == "200.00"


def test_customer_passbook_khata_running_balance(client, auth_headers, business_setup):
    """Test GET /api/customers/{id}/history returns chronological ledger with exact running balances."""
    c = client.post(
        "/api/customers",
        json={"name": "Khata User", "phone": "9333333333", "box_number": "BOX-KHATA-01", "area": "Sector 1", "monthly_amount": "350.00"},
        headers=auth_headers,
    ).json()

    # Month 1 Bill (2026-10): 350.00
    client.post("/api/billing/generate/2026-10", headers=auth_headers)

    # Pay 200.00 on 2026-10-05
    client.post(
        "/api/payments",
        json={"customer_id": c["id"], "amount": "200.00", "payment_method": "cash", "paid_date": "2026-10-05"},
        headers=auth_headers,
    )

    # Month 2 Bill (2026-11): 350.00
    client.post("/api/billing/generate/2026-11", headers=auth_headers)

    # Pay 500.00 on 2026-11-05 (Clears 150 from Oct, 350 from Nov)
    pay2 = client.post(
        "/api/payments",
        json={"customer_id": c["id"], "amount": "500.00", "payment_method": "upi", "paid_date": "2026-11-05"},
        headers=auth_headers,
    ).json()["payment"]

    # Reverse pay2
    client.post(
        f"/api/payments/{pay2['id']}/reverse",
        json={"reversal_reason": "Incorrect bank credit"},
        headers=auth_headers,
    )

    # Check Khata Ledger
    resp = client.get(f"/api/customers/{c['id']}/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "ledger" in data
    ledger = data["ledger"]

    # 1. Charge 2026-10: +350 -> Balance 350.00
    # 2. Payment: -200 -> Balance 150.00
    # 3. Charge 2026-11: +350 -> Balance 500.00
    # 4. Payment 2: -500 -> Balance 0.00
    # 5. Reversal: +500 -> Balance 500.00
    assert len(ledger) == 5
    assert ledger[0]["entry_type"] == "charge"
    assert ledger[0]["running_balance"] == "350.00"

    assert ledger[1]["entry_type"] == "payment"
    assert ledger[1]["running_balance"] == "150.00"

    assert ledger[2]["entry_type"] == "charge"
    assert ledger[2]["running_balance"] == "500.00"

    assert ledger[3]["entry_type"] == "payment"
    assert ledger[3]["running_balance"] == "0.00"

    assert ledger[4]["entry_type"] == "reversal"
    assert ledger[4]["running_balance"] == "500.00"

    # End balance must reconcile with customer.outstanding_balance
    assert data["outstanding_balance"] == "500.00"


def test_monthly_register_filtering_and_totals(client, auth_headers, business_setup):
    """Test GET /api/reports/monthly-register/{month} with area, status, and search filters."""
    # Create customers in different areas
    c1 = client.post(
        "/api/customers",
        json={"name": "Reg Area1 Paid", "phone": "9444444441", "box_number": "BOX-R-01", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()

    c2 = client.post(
        "/api/customers",
        json={"name": "Reg Area1 Unpaid", "phone": "9444444442", "box_number": "BOX-R-02", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()

    c3 = client.post(
        "/api/customers",
        json={"name": "Reg Area2 Partial", "phone": "9444444443", "box_number": "BOX-R-03", "area": "Sector 2", "monthly_amount": "500.00"},
        headers=auth_headers,
    ).json()

    # Generate billing for 2026-12
    client.post("/api/billing/generate/2026-12", headers=auth_headers)

    # c1 pays full 300
    client.post(
        "/api/payments",
        json={"customer_id": c1["id"], "amount": "300.00", "payment_method": "cash", "paid_date": "2026-12-01"},
        headers=auth_headers,
    )

    # c3 pays partial 200 of 500
    client.post(
        "/api/payments",
        json={"customer_id": c3["id"], "amount": "200.00", "payment_method": "upi", "paid_date": "2026-12-01"},
        headers=auth_headers,
    )

    # 1. Total unfiltered register for 2026-12
    r_all = client.get("/api/reports/monthly-register/2026-12", headers=auth_headers).json()
    assert r_all["total_expected"] == "1100.00"  # 300 + 300 + 500
    assert r_all["total_collected"] == "500.00"  # 300 + 200
    assert r_all["total_pending"] == "600.00"    # 300 (c2) + 300 (c3)

    # 2. Filter by Area = "Sector 1"
    r_sec1 = client.get("/api/reports/monthly-register/2026-12?area=Sector 1", headers=auth_headers).json()
    assert r_sec1["total_customers"] == 2
    assert r_sec1["total_expected"] == "600.00"
    assert r_sec1["total_collected"] == "300.00"
    assert r_sec1["total_pending"] == "300.00"

    # 3. Filter by Status = "paid"
    r_paid = client.get("/api/reports/monthly-register/2026-12?status_filter=paid", headers=auth_headers).json()
    assert r_paid["total_customers"] == 1
    assert r_paid["items"][0]["customer_id"] == c1["id"]

    # 4. Filter by Status = "partial"
    r_partial = client.get("/api/reports/monthly-register/2026-12?status_filter=partial", headers=auth_headers).json()
    assert r_partial["total_customers"] == 1
    assert r_partial["items"][0]["customer_id"] == c3["id"]

    # 5. Filter by Status = "unpaid"
    r_unpaid = client.get("/api/reports/monthly-register/2026-12?status_filter=unpaid", headers=auth_headers).json()
    assert r_unpaid["total_customers"] == 1
    assert r_unpaid["items"][0]["customer_id"] == c2["id"]
