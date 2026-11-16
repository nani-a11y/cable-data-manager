from fastapi.testclient import TestClient
from app.models import AdminUser
from app.rate_limiter import login_rate_limiter, RateLimitPolicy, LoginRateLimiter
from app.security import hash_password


def test_login_rate_limiting_enforcement_and_reset(client, test_db):
    # Setup test admin
    email = "rate-limit-admin@example.com"
    raw_password = "operatorSecurePass123!"
    admin = AdminUser(
        email=email,
        password_hash=hash_password(raw_password),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    login_rate_limiter.reset()

    # 1. First 4 failed attempts should return 401
    for i in range(4):
        resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    # 2. 5th failed attempt should still return 401 (triggers lockout for subsequent attempts)
    resp5 = client.post(
        "/api/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert resp5.status_code == 401

    # 3. 6th attempt should now be blocked with 429 Too Many Requests
    resp6 = client.post(
        "/api/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert resp6.status_code == 429
    assert "Too many login attempts" in resp6.json()["detail"]
    assert "Retry-After" in resp6.headers

    # 4. Even with the correct password, it is blocked while locked out
    resp_blocked_correct = client.post(
        "/api/auth/login",
        json={"email": email, "password": raw_password},
    )
    assert resp_blocked_correct.status_code == 429

    # 5. Recovery / Reset: simulate lockout expiration or administrative reset
    login_rate_limiter.reset()

    # 6. Now correct password succeeds immediately
    resp_success = client.post(
        "/api/auth/login",
        json={"email": email, "password": raw_password},
    )
    assert resp_success.status_code == 200
    assert "access_token" in resp_success.json()

    # 7. Success clears failures, so next attempt from this IP has fresh counter
    login_rate_limiter.reset()


def test_rate_limiting_client_ip_handling_with_proxies(client, test_db, monkeypatch):
    monkeypatch.setattr(
        "app.rate_limiter.settings.trusted_proxies",
        "testclient,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    )
    email = "proxy-test-admin@example.com"
    raw_password = "operatorSecurePass123!"
    admin = AdminUser(
        email=email,
        password_hash=hash_password(raw_password),
        is_active=True,
    )
    test_db.add(admin)
    test_db.commit()

    login_rate_limiter.reset()

    # Simulate client A from behind a trusted local proxy (e.g. 127.0.0.1 or 172.20.0.1)
    headers_client_a = {"X-Forwarded-For": "203.0.113.10"}
    for _ in range(5):
        resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": "wrongpassword"},
            headers=headers_client_a,
        )
        assert resp.status_code == 401

    # Client A is now locked out
    resp_a_locked = client.post(
        "/api/auth/login",
        json={"email": email, "password": "wrongpassword"},
        headers=headers_client_a,
    )
    assert resp_a_locked.status_code == 429

    # Client B from a different IP (203.0.113.20) behind the same proxy should NOT be locked out
    headers_client_b = {"X-Forwarded-For": "203.0.113.20"}
    resp_b = client.post(
        "/api/auth/login",
        json={"email": email, "password": raw_password},
        headers=headers_client_b,
    )
    assert resp_b.status_code == 200
    assert "access_token" in resp_b.json()

    login_rate_limiter.reset()


def test_rate_limiter_untrusted_proxy_rejection():
    # Test limiter directly with custom policy and untrusted peer IP
    limiter = LoginRateLimiter(RateLimitPolicy(max_failed_attempts=2, window_seconds=10, lockout_seconds=10))

    class MockRequest:
        def __init__(self, host, x_forwarded_for=None):
            self.client = type("Client", (), {"host": host})()
            self.headers = {}
            if x_forwarded_for:
                self.headers["x-forwarded-for"] = x_forwarded_for

    # Peer is a public untrusted IP trying to spoof X-Forwarded-For
    req = MockRequest(host="198.51.100.5", x_forwarded_for="1.1.1.1")
    # Must reject the spoofed header and return the direct untrusted peer IP
    assert limiter.extract_client_ip(req) == "198.51.100.5"

    # Peer is an untrusted client trying to spoof X-Real-IP
    req_real_ip_spoof = MockRequest(host="198.51.100.5")
    req_real_ip_spoof.headers["x-real-ip"] = "8.8.8.8"
    assert limiter.extract_client_ip(req_real_ip_spoof) == "198.51.100.5"

    # Peer is a trusted local IP (127.0.0.1) forwarding client IP via X-Forwarded-For
    req_trusted = MockRequest(host="127.0.0.1", x_forwarded_for="198.51.100.22")
    assert limiter.extract_client_ip(req_trusted) == "198.51.100.22"

    # Peer is a trusted local IP forwarding client IP via X-Real-IP
    req_trusted_real_ip = MockRequest(host="127.0.0.1")
    req_trusted_real_ip.headers["x-real-ip"] = "198.51.100.33"
    assert limiter.extract_client_ip(req_trusted_real_ip) == "198.51.100.33"

    # Peer is a trusted local IP forwarding invalid IP -> fallbacks safely to peer
    req_invalid = MockRequest(host="127.0.0.1", x_forwarded_for="invalid-ip-string")
    assert limiter.extract_client_ip(req_invalid) == "127.0.0.1"


def test_production_dockerfile_contains_no_wildcard_forwarded_allow_ips():
    import os
    dockerfile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Dockerfile.prod"))
    with open(dockerfile_path, "r") as f:
        content = f.read()
    assert '--forwarded-allow-ips "*"' not in content
    assert "--forwarded-allow-ips '*'" not in content
    assert "TRUSTED_PROXIES" in content

