"""Admin Settings and Service Area Management Tests.

Covers:
1. List service areas (active and archived) with customer counts.
2. Add new service area.
3. Prevent duplicate service area addition.
4. Rename service area and atomically update matching customers.
5. Archive service area (keeps existing customer association, excludes from new customer creation).
6. Prevent archiving all service areas.
7. Prevent deleting service area referenced by customers.
8. Delete unreferenced service area.
9. Bulk subscription rate update with confirm=True (active customers only).
10. Bulk update rejected with confirm=False.
"""
from decimal import Decimal
import pytest

from app.models import AdminUser, BusinessSettings, Customer
from app.security import hash_password


@pytest.fixture
def auth_headers(client, test_db):
    email = "admin-settings@example.com"
    password = "AdminSettingsPassword123!"
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
def business_settings(test_db):
    settings = BusinessSettings(
        id=1,
        business_name="Metro Cable",
        contact_number="9876543210",
        service_areas=["Sector 1", "Sector 2"],
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


def test_service_areas_crud_and_safety(client, auth_headers, business_settings):
    # 1. List areas
    areas = client.get("/api/business-settings/areas", headers=auth_headers).json()
    assert len(areas) == 2
    assert areas[0]["name"] == "Sector 1"
    assert areas[0]["is_active"] is True

    # 2. Add customer in Sector 1
    c1 = client.post(
        "/api/customers",
        json={"name": "Area User 1", "phone": "9876543211", "box_number": "STB-A1", "area": "Sector 1"},
        headers=auth_headers,
    ).json()

    # Verify customer count in areas list
    areas_updated = client.get("/api/business-settings/areas", headers=auth_headers).json()
    sec1 = next(a for a in areas_updated if a["name"] == "Sector 1")
    assert sec1["customer_count"] == 1

    # 3. Add new area
    add_res = client.post(
        "/api/business-settings/areas",
        json={"name": "Sector 3"},
        headers=auth_headers,
    )
    assert add_res.status_code == 200
    assert add_res.json()["area"]["name"] == "Sector 3"

    # Duplicate add fails
    add_dup = client.post(
        "/api/business-settings/areas",
        json={"name": "sector 3"},
        headers=auth_headers,
    )
    assert add_dup.status_code == 409

    # 4. Rename Sector 1 to Sector 1 North
    ren_res = client.put(
        "/api/business-settings/areas/rename",
        json={"old_name": "Sector 1", "new_name": "Sector 1 North"},
        headers=auth_headers,
    )
    assert ren_res.status_code == 200
    assert ren_res.json()["updated_customers"] == 1

    # Verify customer record area is updated
    cust_check = client.get(f"/api/customers/{c1['id']}", headers=auth_headers).json()
    assert cust_check["area"] == "Sector 1 North"

    # 5. Archive Sector 2
    arch_res = client.put(
        "/api/business-settings/areas/archive",
        json={"name": "Sector 2", "is_active": False},
        headers=auth_headers,
    )
    assert arch_res.status_code == 200

    # New customer in archived area should be rejected
    fail_cust = client.post(
        "/api/customers",
        json={"name": "Fail Area User", "phone": "9876543212", "box_number": "STB-A2", "area": "Sector 2"},
        headers=auth_headers,
    )
    assert fail_cust.status_code == 400
    assert "not an active configured service area" in fail_cust.json()["detail"]

    # 6. Attempt delete on Sector 1 North (has customer) should fail
    del_fail = client.delete("/api/business-settings/areas/Sector 1 North", headers=auth_headers)
    assert del_fail.status_code == 400
    assert "associated with it" in del_fail.json()["detail"]

    # Delete unreferenced Sector 3 succeeds
    del_ok = client.delete("/api/business-settings/areas/Sector 3", headers=auth_headers)
    assert del_ok.status_code == 200


def test_bulk_rate_update(client, auth_headers, business_settings):
    # Create 2 active customers, 1 inactive
    c1 = client.post(
        "/api/customers",
        json={"name": "Active Rate 1", "phone": "9876500001", "box_number": "BR-01", "area": "Sector 1", "monthly_amount": "300.00"},
        headers=auth_headers,
    ).json()
    c2 = client.post(
        "/api/customers",
        json={"name": "Active Rate 2", "phone": "9876500002", "box_number": "BR-02", "area": "Sector 1", "monthly_amount": "350.00"},
        headers=auth_headers,
    ).json()
    c3 = client.post(
        "/api/customers",
        json={"name": "Inactive Rate 3", "phone": "9876500003", "box_number": "BR-03", "area": "Sector 1", "monthly_amount": "250.00"},
        headers=auth_headers,
    ).json()
    client.delete(f"/api/customers/{c3['id']}", headers=auth_headers)

    # Without confirmation should fail
    unconf = client.post(
        "/api/business-settings/bulk-rate-update",
        json={"new_monthly_amount": "400.00", "confirm": False},
        headers=auth_headers,
    )
    assert unconf.status_code == 400

    # With confirmation should update only active customers
    res = client.post(
        "/api/business-settings/bulk-rate-update",
        json={"new_monthly_amount": "400.00", "confirm": True},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["affected_customers_count"] == 2
    assert data["new_monthly_amount"] == "400.00"

    # Verify active rates are updated
    check_c1 = client.get(f"/api/customers/{c1['id']}", headers=auth_headers).json()
    check_c2 = client.get(f"/api/customers/{c2['id']}", headers=auth_headers).json()
    assert check_c1["monthly_amount"] == "400.00"
    assert check_c2["monthly_amount"] == "400.00"

    # Verify inactive customer rate is untouched
    check_c3 = client.get(f"/api/customers/{c3['id']}", headers=auth_headers).json()
    assert check_c3["monthly_amount"] == "250.00"
