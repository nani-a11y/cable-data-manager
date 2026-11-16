from app.config import Settings


def test_settings_default_values():
    settings = Settings(
        jwt_secret="dummy_jwt_secret_value_for_unit_tests",
        admin_email="admin@example.com",
        admin_password="dummy_admin_password",
    )
    assert settings.app_env in ["development", "testing"]
    assert settings.jwt_expire_minutes == 60


def test_allowed_origins_parsing():
    settings = Settings(
        cors_origins="http://localhost:5173, http://127.0.0.1:5173 , , https://app.example.com",
        jwt_secret="dummy_jwt_secret_value_for_unit_tests",
        admin_email="admin@example.com",
        admin_password="dummy_admin_password",
    )
    assert settings.allowed_origins == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://app.example.com",
    ]
