from decimal import Decimal
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import AdminUser, BusinessSettings
from app.security import hash_password


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
def valid_payload():
    return {
        "business_name": "City Cable Network",
        "contact_number": "+91 9876543210",
        "email": "contact@citycable.example",
        "address": "123 Main Bazaar Road, Sector 4",
        "service_areas": ["Sector 4", "Sector 5", "Market Area"],
        "currency_code": "INR",
        "timezone": "Asia/Kolkata",
        "default_monthly_amount": "350.00",
        "billing_day": 1,
        "grace_period_days": 5,
        "late_payment_policy": "reminder_only",
    }


def test_get_business_settings_unauthenticated(client):
    response = client.get("/api/business-settings")
    assert response.status_code == 401


def test_get_business_settings_not_found(client, auth_headers):
    response = client.get("/api/business-settings", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Business configuration not found"


def test_create_business_settings_success(client, auth_headers, valid_payload):
    response = client.post("/api/business-settings", headers=auth_headers, json=valid_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["business_name"] == "City Cable Network"
    assert data["contact_number"] == "+91 9876543210"
    assert data["email"] == "contact@citycable.example"
    assert data["service_areas"] == ["Sector 4", "Sector 5", "Market Area"]
    assert data["currency_code"] == "INR"
    assert data["timezone"] == "Asia/Kolkata"
    # Exact decimal representation as string
    assert data["default_monthly_amount"] == "350.00"
    assert data["billing_day"] == 1
    assert data["grace_period_days"] == 5
    assert data["late_payment_policy"] == "reminder_only"
    assert "created_at" in data
    assert "updated_at" in data


def test_create_duplicate_business_settings_fails(client, auth_headers, valid_payload):
    # First creation succeeds
    resp1 = client.post("/api/business-settings", headers=auth_headers, json=valid_payload)
    assert resp1.status_code == 201

    # Second creation must fail with 409 Conflict
    resp2 = client.post("/api/business-settings", headers=auth_headers, json=valid_payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_get_existing_business_settings(client, auth_headers, valid_payload):
    client.post("/api/business-settings", headers=auth_headers, json=valid_payload)
    response = client.get("/api/business-settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "City Cable Network"
    assert data["default_monthly_amount"] == "350.00"


def test_update_business_settings_put(client, auth_headers, valid_payload):
    client.post("/api/business-settings", headers=auth_headers, json=valid_payload)

    updated_payload = {
        **valid_payload,
        "business_name": "Metro Cable Services",
        "default_monthly_amount": "400.00",
        "billing_day": 15,
        "grace_period_days": 7,
        "service_areas": ["Downtown", "North Zone"],
    }
    response = client.put("/api/business-settings", headers=auth_headers, json=updated_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Metro Cable Services"
    assert data["default_monthly_amount"] == "400.00"
    assert data["billing_day"] == 15
    assert data["grace_period_days"] == 7
    assert data["service_areas"] == ["Downtown", "North Zone"]


def test_patch_business_settings(client, auth_headers, valid_payload):
    client.post("/api/business-settings", headers=auth_headers, json=valid_payload)

    patch_payload = {
        "contact_number": "+91 9999988888",
        "default_monthly_amount": "375.50",
    }
    response = client.patch("/api/business-settings", headers=auth_headers, json=patch_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "City Cable Network"  # Unchanged
    assert data["contact_number"] == "+91 9999988888"     # Changed
    assert data["default_monthly_amount"] == "375.50"      # Changed


def test_db_single_row_constraint_at_database_level(test_db):
    # Direct DB insertion with id=1 works
    bs1 = BusinessSettings(
        id=1,
        business_name="Biz 1",
        contact_number="9876543210",
        service_areas=["Area 1"],
        currency_code="INR",
        timezone="Asia/Kolkata",
        default_monthly_amount=Decimal("300.00"),
        billing_day=1,
        grace_period_days=5,
    )
    test_db.add(bs1)
    test_db.commit()

    # Attempting to insert another row with id=2 must violate single_business_setting_row CheckConstraint
    bs2 = BusinessSettings(
        id=2,
        business_name="Biz 2",
        contact_number="9876543210",
        service_areas=["Area 2"],
        currency_code="INR",
        timezone="Asia/Kolkata",
        default_monthly_amount=Decimal("300.00"),
        billing_day=1,
        grace_period_days=5,
    )
    test_db.add(bs2)
    with pytest.raises(IntegrityError):
        test_db.commit()
    test_db.rollback()


def test_validation_invalid_billing_day(client, auth_headers, valid_payload):
    # Billing day 0 is invalid
    payload = {**valid_payload, "billing_day": 0}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422

    # Billing day 29 is invalid (max 28 to guarantee every month has it)
    payload = {**valid_payload, "billing_day": 29}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_validation_negative_or_zero_amount(client, auth_headers, valid_payload):
    # Zero amount
    payload = {**valid_payload, "default_monthly_amount": "0"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422

    # Negative amount
    payload = {**valid_payload, "default_monthly_amount": "-100.00"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_validation_excessive_decimals_on_amount(client, auth_headers, valid_payload):
    payload = {**valid_payload, "default_monthly_amount": "299.999"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422
    assert "more than 2 decimal places" in resp.text


def test_validation_invalid_currency_code(client, auth_headers, valid_payload):
    payload = {**valid_payload, "currency_code": "INVALID"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_validation_invalid_timezone(client, auth_headers, valid_payload):
    payload = {**valid_payload, "timezone": "Mars/Olympus_Mons"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_validation_invalid_service_areas(client, auth_headers, valid_payload):
    # Empty list
    payload = {**valid_payload, "service_areas": []}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422

    # Empty string inside list
    payload = {**valid_payload, "service_areas": ["Area 1", "   "]}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422

    # Duplicate areas
    payload = {**valid_payload, "service_areas": ["Zone A", "zone a"]}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_validation_invalid_contact_number(client, auth_headers, valid_payload):
    # Less than 7 digits
    payload = {**valid_payload, "contact_number": "12345"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_validation_invalid_late_payment_policy(client, auth_headers, valid_payload):
    payload = {**valid_payload, "late_payment_policy": "charge_huge_penalty"}
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 422


def test_all_endpoints_reject_unauthenticated(client, valid_payload):
    # GET rejected
    assert client.get("/api/business-settings").status_code == 401
    # POST rejected
    assert client.post("/api/business-settings", json=valid_payload).status_code == 401
    # PUT rejected
    assert client.put("/api/business-settings", json=valid_payload).status_code == 401
    # PATCH rejected
    assert client.patch("/api/business-settings", json={"business_name": "Hacked"}).status_code == 401


def test_failed_update_preserves_existing_settings(client, auth_headers, valid_payload):
    # Seed initial configuration
    create_resp = client.post("/api/business-settings", headers=auth_headers, json=valid_payload)
    assert create_resp.status_code == 201
    original_data = create_resp.json()

    # Attempt invalid PUT (billing_day out of range)
    invalid_put = {**valid_payload, "billing_day": 99}
    put_resp = client.put("/api/business-settings", headers=auth_headers, json=invalid_put)
    assert put_resp.status_code == 422

    # Verify settings are unchanged after failed PUT
    get_after_put = client.get("/api/business-settings", headers=auth_headers).json()
    assert get_after_put["business_name"] == original_data["business_name"]
    assert get_after_put["billing_day"] == original_data["billing_day"]
    assert get_after_put["default_monthly_amount"] == original_data["default_monthly_amount"]

    # Attempt invalid PATCH (negative amount)
    invalid_patch = {"default_monthly_amount": "-50.00"}
    patch_resp = client.patch("/api/business-settings", headers=auth_headers, json=invalid_patch)
    assert patch_resp.status_code == 422

    # Verify settings are unchanged after failed PATCH
    get_after_patch = client.get("/api/business-settings", headers=auth_headers).json()
    assert get_after_patch["business_name"] == original_data["business_name"]
    assert get_after_patch["billing_day"] == original_data["billing_day"]
    assert get_after_patch["default_monthly_amount"] == original_data["default_monthly_amount"]


def test_concurrent_create_requests_prevent_duplicates(valid_payload):
    import concurrent.futures
    import tempfile
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient
    from app.database import Base, get_db
    from app.main import app

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        conc_engine = create_engine(f"sqlite:///{temp_db_path}", connect_args={"timeout": 20})
        Base.metadata.create_all(bind=conc_engine)
        ConcSessionLocal = sessionmaker(bind=conc_engine)

        # Seed admin
        db = ConcSessionLocal()
        admin = AdminUser(
            email="admin-conc@example.com",
            password_hash=hash_password("AdminSecret123!"),
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.close()

        def override_conc_db():
            s = ConcSessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = override_conc_db

        login_client = TestClient(app)
        login_resp = login_client.post(
            "/api/auth/login",
            json={"email": "admin-conc@example.com", "password": "AdminSecret123!"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        def make_post():
            c = TestClient(app)
            resp = c.post("/api/business-settings", headers=headers, json=valid_payload)
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(make_post)
            f2 = executor.submit(make_post)
            statuses = [f1.result(), f2.result()]

        # Exactly one request must succeed with 201, and the other must be rejected with 409 Conflict
        assert 201 in statuses, f"Expected a 201 Created, got {statuses}"
        assert 409 in statuses, f"Expected a 409 Conflict for duplicate creation, got {statuses}"

        # Verify exactly 1 configuration exists in database
        verify_client = TestClient(app)
        get_resp = verify_client.get("/api/business-settings", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == 1

        db = ConcSessionLocal()
        assert db.query(BusinessSettings).count() == 1
        db.close()
    finally:
        app.dependency_overrides.clear()
        conc_engine.dispose()
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def test_monetary_boundary_numeric_12_2(client, auth_headers, valid_payload):
    # Upper boundary for Numeric(12, 2) is 9,999,999,999.99 (10 integer digits + 2 scale digits = 12 total digits)
    payload_max = {**valid_payload, "default_monthly_amount": "9999999999.99"}
    resp_max = client.post("/api/business-settings", headers=auth_headers, json=payload_max)
    assert resp_max.status_code == 201
    assert resp_max.json()["default_monthly_amount"] == "9999999999.99"

    # Exceeding boundary: 10,000,000,000.00 (11 integer digits) must be rejected with 422
    payload_overflow = {**valid_payload, "default_monthly_amount": "10000000000.00"}
    resp_overflow = client.put("/api/business-settings", headers=auth_headers, json=payload_overflow)
    assert resp_overflow.status_code == 422
    assert "exceeds maximum allowed value" in resp_overflow.text


def test_service_area_normalization_deterministic(client, auth_headers, valid_payload):
    payload = {
        **valid_payload,
        "service_areas": ["   North Sector  ", "South Sector\t", "East Market   "],
    }
    resp = client.post("/api/business-settings", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    saved_areas = resp.json()["service_areas"]
    assert saved_areas == ["North Sector", "South Sector", "East Market"]

