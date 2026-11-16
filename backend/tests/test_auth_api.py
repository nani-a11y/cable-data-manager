from app.models import AdminUser
from app.security import hash_password


def test_dashboard_summary_unauthorized(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_login_invalid_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_and_access_protected_endpoints(client, test_db):
    # Seed an isolated admin user in the disposable test database
    email = "test-operator@example.com"
    raw_password = "operatorSecurePass123!"
    admin = AdminUser(
        email=email,
        password_hash=hash_password(raw_password),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    # 1. Successful login
    login_resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": raw_password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Access /api/auth/me
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == email
    assert me_data["is_active"] is True

    # 3. Access /api/dashboard/summary
    dash_resp = client.get("/api/dashboard/summary", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    assert dash_data["total_customers"] == 0
    assert dash_data["data_status"] == "awaiting_customer_import"
