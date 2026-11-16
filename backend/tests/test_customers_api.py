"""Tests for Customer Management Backend APIs (Phase 3 Step 3.2A).

Covers all 18 mandatory requirements:
1. Authenticated customer creation.
2. Unauthenticated request rejection.
3. Customer list and pagination.
4. Customer detail retrieval.
5. Customer update.
6. Search by name.
7. Search by phone.
8. Search by box number.
9. Case-insensitive duplicate box rejection.
10. Default monthly amount assignment.
11. Individual monthly amount override.
12. Invalid service area rejection.
13. Customer deactivation.
14. Deactivated customer excluded from default listing.
15. Explicit inactive-customer listing.
16. Financial history preservation on deactivation.
17. Concurrent customer creation and display ID uniqueness.
18. Decimal precision and monetary boundary validation.
"""
from decimal import Decimal
import tempfile
import threading
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import AdminUser, BusinessSettings, Customer, Invoice, Payment
from app.security import hash_password
from app.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def auth_headers(client, test_db):
    """Seed an admin user and return valid Bearer authorization headers."""
    email = "admin-test@example.com"
    password = "AdminSecretPassword123!"
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
def setup_business_settings(test_db):
    """Ensure business settings with service areas and default amount exist."""
    settings = BusinessSettings(
        id=1,
        business_name="City Cable Network",
        contact_number="+91 9876543210",
        service_areas=["Sector 1", "Sector 2", "Sector 3", "Old Town"],
        currency_code="INR",
        timezone="Asia/Kolkata",
        default_monthly_amount=Decimal("350.00"),
        billing_day=1,
        grace_period_days=5,
        late_payment_policy="none",
    )
    test_db.add(settings)
    test_db.commit()
    return settings


# 1. Authenticated customer creation
def test_01_authenticated_customer_creation(client, auth_headers, setup_business_settings):
    payload = {
        "name": "Rajesh Sharma",
        "phone": "9876543210",
        "box_number": "STB-1001",
        "area": "Sector 1",
        "monthly_amount": "400.00",
    }
    resp = client.post("/api/customers", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["display_id"] == "C-0001"
    assert data["name"] == "Rajesh Sharma"
    assert data["phone"] == "9876543210"
    assert data["box_number"] == "STB-1001"
    assert data["area"] == "Sector 1"
    assert data["monthly_amount"] == "400.00"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data


# 2. Unauthenticated request rejection
def test_02_unauthenticated_request_rejection(client):
    endpoints = [
        ("GET", "/api/customers"),
        ("POST", "/api/customers"),
        ("GET", "/api/customers/1"),
        ("PATCH", "/api/customers/1"),
        ("DELETE", "/api/customers/1"),
    ]
    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 401


# 3. Customer list and pagination
def test_03_customer_list_and_pagination(client, auth_headers, setup_business_settings):
    for i in range(1, 26):
        client.post(
            "/api/customers",
            json={
                "name": f"Customer {i}",
                "phone": f"9876543{i:03d}",
                "box_number": f"BOX-{i:03d}",
                "area": "Sector 1",
            },
            headers=auth_headers,
        )

    # Page 1
    resp1 = client.get("/api/customers?page=1&page_size=10", headers=auth_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] == 25
    assert data1["page"] == 1
    assert data1["page_size"] == 10
    assert data1["total_pages"] == 3
    assert len(data1["items"]) == 10
    assert data1["items"][0]["display_id"] == "C-0001"

    # Page 3
    resp3 = client.get("/api/customers?page=3&page_size=10", headers=auth_headers)
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert len(data3["items"]) == 5
    assert data3["items"][-1]["display_id"] == "C-0025"


# 4. Customer detail retrieval
def test_04_customer_detail_retrieval(client, auth_headers, setup_business_settings):
    created = client.post(
        "/api/customers",
        json={
            "name": "Priya Verma",
            "phone": "9123456789",
            "box_number": "BOX-PV-01",
            "area": "Sector 2",
        },
        headers=auth_headers,
    ).json()

    resp = client.get(f"/api/customers/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == created["id"]
    assert data["display_id"] == created["display_id"]
    assert data["name"] == "Priya Verma"

    # Not found check
    resp_nf = client.get("/api/customers/99999", headers=auth_headers)
    assert resp_nf.status_code == 404


# 5. Customer update
def test_05_customer_update(client, auth_headers, setup_business_settings):
    created = client.post(
        "/api/customers",
        json={
            "name": "Anil Kumar",
            "phone": "9811122233",
            "box_number": "BOX-AK-01",
            "area": "Sector 1",
            "monthly_amount": "300.00",
        },
        headers=auth_headers,
    ).json()

    patch_payload = {
        "name": "Anil K. Sharma",
        "area": "Sector 3",
        "monthly_amount": "450.00",
    }
    resp = client.patch(f"/api/customers/{created['id']}", json=patch_payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Anil K. Sharma"
    assert data["area"] == "Sector 3"
    assert data["monthly_amount"] == "450.00"
    assert data["phone"] == "9811122233"  # Unchanged
    assert data["box_number"] == "BOX-AK-01"  # Unchanged


# 6. Search by name
def test_06_search_by_name(client, auth_headers, setup_business_settings):
    client.post(
        "/api/customers",
        json={"name": "Vikram Singh", "phone": "9876500001", "box_number": "VS-01", "area": "Sector 1"},
        headers=auth_headers,
    )
    client.post(
        "/api/customers",
        json={"name": "Sunita Rao", "phone": "9876500002", "box_number": "SR-01", "area": "Sector 1"},
        headers=auth_headers,
    )

    resp = client.get("/api/customers?search=vikram", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Vikram Singh"


# 7. Search by phone
def test_07_search_by_phone(client, auth_headers, setup_business_settings):
    client.post(
        "/api/customers",
        json={"name": "Kiran Patel", "phone": "9988776655", "box_number": "KP-01", "area": "Sector 2"},
        headers=auth_headers,
    )

    resp = client.get("/api/customers?search=887766", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["phone"] == "9988776655"


# 8. Search by box number
def test_08_search_by_box_number(client, auth_headers, setup_business_settings):
    client.post(
        "/api/customers",
        json={"name": "Deepak Joshi", "phone": "9771122334", "box_number": "STB-ALPHA-99", "area": "Sector 3"},
        headers=auth_headers,
    )

    resp = client.get("/api/customers?search=alpha-99", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["box_number"] == "STB-ALPHA-99"


# 9. Case-insensitive duplicate box rejection
def test_09_case_insensitive_duplicate_box_rejection(client, auth_headers, setup_business_settings):
    resp1 = client.post(
        "/api/customers",
        json={"name": "First User", "phone": "9000000001", "box_number": "BOX-UNIQUE-1", "area": "Sector 1"},
        headers=auth_headers,
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        "/api/customers",
        json={"name": "Second User", "phone": "9000000002", "box_number": "box-unique-1", "area": "Sector 2"},
        headers=auth_headers,
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


# 10. Default monthly amount assignment
def test_10_default_monthly_amount_assignment(client, auth_headers, setup_business_settings):
    # setup_business_settings has default_monthly_amount = Decimal("350.00")
    resp = client.post(
        "/api/customers",
        json={"name": "Default Amount User", "phone": "9111222333", "box_number": "BOX-DEF-1", "area": "Sector 1"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["monthly_amount"] == "350.00"


# 11. Individual monthly amount override
def test_11_individual_monthly_amount_override(client, auth_headers, setup_business_settings):
    resp = client.post(
        "/api/customers",
        json={
            "name": "Custom Amount User",
            "phone": "9111222444",
            "box_number": "BOX-CUST-1",
            "area": "Sector 1",
            "monthly_amount": "550.00",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["monthly_amount"] == "550.00"


# 12. Invalid service area rejection
def test_12_invalid_service_area_rejection(client, auth_headers, setup_business_settings):
    resp = client.post(
        "/api/customers",
        json={"name": "Invalid Area User", "phone": "9111222555", "box_number": "BOX-INV-1", "area": "Non Existent Area"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "not an active configured service area" in resp.json()["detail"]


# 13. Customer deactivation
def test_13_customer_deactivation(client, auth_headers, setup_business_settings):
    created = client.post(
        "/api/customers",
        json={"name": "Deactivate Me", "phone": "9111222666", "box_number": "BOX-DEACT-1", "area": "Sector 1"},
        headers=auth_headers,
    ).json()

    del_resp = client.delete(f"/api/customers/{created['id']}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["is_active"] is False

    # Verify via get
    get_resp = client.get(f"/api/customers/{created['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["is_active"] is False


# 14. Deactivated customer excluded from default listing
def test_14_deactivated_customer_excluded_from_default_listing(client, auth_headers, setup_business_settings):
    c1 = client.post(
        "/api/customers",
        json={"name": "Active Customer", "phone": "9111222771", "box_number": "BOX-ACT-1", "area": "Sector 1"},
        headers=auth_headers,
    ).json()

    c2 = client.post(
        "/api/customers",
        json={"name": "Inactive Customer", "phone": "9111222772", "box_number": "BOX-INACT-1", "area": "Sector 1"},
        headers=auth_headers,
    ).json()

    client.delete(f"/api/customers/{c2['id']}", headers=auth_headers)

    resp = client.get("/api/customers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    display_ids = [item["display_id"] for item in data["items"]]
    assert c1["display_id"] in display_ids
    assert c2["display_id"] not in display_ids


# 15. Explicit inactive-customer listing
def test_15_explicit_inactive_customer_listing(client, auth_headers, setup_business_settings):
    c = client.post(
        "/api/customers",
        json={"name": "To Deactivate", "phone": "9111222888", "box_number": "BOX-INACT-LIST", "area": "Sector 1"},
        headers=auth_headers,
    ).json()
    client.delete(f"/api/customers/{c['id']}", headers=auth_headers)

    resp = client.get("/api/customers?include_inactive=true", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    display_ids = [item["display_id"] for item in data["items"]]
    assert c["display_id"] in display_ids


# 16. Financial history preservation on deactivation
def test_16_financial_history_preservation_on_deactivation(client, auth_headers, setup_business_settings, test_db):
    from datetime import date
    c = client.post(
        "/api/customers",
        json={"name": "History Preserved", "phone": "9111222999", "box_number": "BOX-HIST-1", "area": "Sector 1"},
        headers=auth_headers,
    ).json()

    # Seed an invoice and payment directly into test_db
    inv = Invoice(
        invoice_number="INV-TEST-001",
        customer_id=c["id"],
        billing_month="2026-11",
        amount=Decimal("350.00"),
        paid_amount=Decimal("350.00"),
        status="paid",
        issued_date=date(2026, 11, 1),
    )
    pay = Payment(
        receipt_number="RCP-TEST-001",
        customer_id=c["id"],
        amount=Decimal("350.00"),
        payment_method="cash",
        paid_date=date(2026, 11, 2),
    )
    test_db.add(inv)
    test_db.add(pay)
    test_db.commit()

    # Deactivate customer
    del_resp = client.delete(f"/api/customers/{c['id']}", headers=auth_headers)
    assert del_resp.status_code == 200

    # Verify invoice and payment still exist in test_db
    db_inv = test_db.query(Invoice).filter(Invoice.customer_id == c["id"]).first()
    db_pay = test_db.query(Payment).filter(Payment.customer_id == c["id"]).first()
    assert db_inv is not None
    assert db_inv.amount == Decimal("350.00")
    assert db_pay is not None
    assert db_pay.amount == Decimal("350.00")


# 17. Concurrent customer creation and display ID uniqueness
def test_17_concurrent_customer_creation_display_id_uniqueness():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_url = f"sqlite:///{tmp.name}"
        engine = create_engine(db_url, connect_args={"timeout": 15})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        with Session() as s:
            admin = AdminUser(email="admin-concur@example.com", password_hash=hash_password("pw"), is_active=True)
            bs = BusinessSettings(
                id=1,
                business_name="Test",
                contact_number="1234567890",
                service_areas=["Area 1"],
                default_monthly_amount=Decimal("300.00"),
            )
            s.add(admin)
            s.add(bs)
            s.commit()

        def override_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db

        c = TestClient(app)
        resp = c.post("/api/auth/login", json={"email": "admin-concur@example.com", "password": "pw"})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        errors = []
        created_display_ids = []

        def worker(num):
            try:
                client_thread = TestClient(app)
                res = client_thread.post(
                    "/api/customers",
                    json={
                        "name": f"Concurrent User {num}",
                        "phone": f"90000000{num:02d}",
                        "box_number": f"CONCUR-BOX-{num}",
                        "area": "Area 1",
                    },
                    headers=headers,
                )
                if res.status_code == 201:
                    created_display_ids.append(res.json()["display_id"])
                else:
                    errors.append(f"HTTP {res.status_code}: {res.text}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        app.dependency_overrides.pop(get_db, None)

        assert len(errors) == 0, f"Errors in concurrent creation: {errors}"
        assert len(created_display_ids) == 10
        # All display IDs must be unique
        assert len(set(created_display_ids)) == 10


# 18. Decimal precision and monetary boundary validation
def test_18_decimal_precision_and_monetary_boundary_validation(client, auth_headers, setup_business_settings):
    # Negative amount
    r1 = client.post(
        "/api/customers",
        json={"name": "Test", "phone": "9876543210", "box_number": "B-1", "area": "Sector 1", "monthly_amount": "-50.00"},
        headers=auth_headers,
    )
    assert r1.status_code == 422

    # Zero amount
    r2 = client.post(
        "/api/customers",
        json={"name": "Test", "phone": "9876543210", "box_number": "B-2", "area": "Sector 1", "monthly_amount": "0.00"},
        headers=auth_headers,
    )
    assert r2.status_code == 422

    # Too many decimal places
    r3 = client.post(
        "/api/customers",
        json={"name": "Test", "phone": "9876543210", "box_number": "B-3", "area": "Sector 1", "monthly_amount": "300.999"},
        headers=auth_headers,
    )
    assert r3.status_code == 422

    # Exceeds maximum 9999999999.99
    r4 = client.post(
        "/api/customers",
        json={"name": "Test", "phone": "9876543210", "box_number": "B-4", "area": "Sector 1", "monthly_amount": "10000000000.00"},
        headers=auth_headers,
    )
    assert r4.status_code == 422
