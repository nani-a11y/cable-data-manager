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


def test_production_secret_validation_rejects_insecure_defaults():
    import pytest
    from pydantic import ValidationError

    # Reject known insecure default JWT
    with pytest.raises(ValidationError, match="Insecure default or placeholder JWT_SECRET"):
        Settings(
            app_env="production",
            jwt_secret="insecure-default-jwt-secret-replace-in-env",
            admin_password="StrongProdOperator999!",
            database_url="postgresql+psycopg://user:prodpass@localhost:5432/proddb",
        )

    # Reject short JWT secret (< 32 chars)
    with pytest.raises(ValidationError, match="at least 32 characters in production"):
        Settings(
            app_env="production",
            jwt_secret="short-secret-under-32-chars",
            admin_password="StrongProdOperator999!",
            database_url="postgresql+psycopg://user:prodpass@localhost:5432/proddb",
        )

    # Reject low entropy JWT
    with pytest.raises(ValidationError, match="lacks sufficient entropy"):
        Settings(
            app_env="production",
            jwt_secret="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            admin_password="StrongProdOperator999!",
            database_url="postgresql+psycopg://user:prodpass@localhost:5432/proddb",
        )

    # Reject insecure or short admin password (< 12 chars)
    with pytest.raises(ValidationError, match="Production ADMIN_PASSWORD rejected"):
        Settings(
            app_env="production",
            jwt_secret="c9f8e7d6c5b4a3928172635483920192837465ab",
            admin_password="short123!",
            database_url="postgresql+psycopg://user:prodpass@localhost:5432/proddb",
        )

    # Reject wildcard in trusted proxies in production
    with pytest.raises(ValidationError, match="Wildcard '\\*' is forbidden in production TRUSTED_PROXIES"):
        Settings(
            app_env="production",
            jwt_secret="c9f8e7d6c5b4a3928172635483920192837465ab",
            admin_password="StrongProdOperator999!",
            database_url="postgresql+psycopg://user:prodpass@localhost:5432/proddb",
            trusted_proxies="*",
        )

    # Reject invalid IP or CIDR in trusted proxies in production
    with pytest.raises(ValidationError, match="Invalid IP address or CIDR network in TRUSTED_PROXIES"):
        Settings(
            app_env="production",
            jwt_secret="c9f8e7d6c5b4a3928172635483920192837465ab",
            admin_password="StrongProdOperator999!",
            database_url="postgresql+psycopg://user:prodpass@localhost:5432/proddb",
            trusted_proxies="127.0.0.1,invalid-proxy-subnet/99",
        )

    # Reject insecure database credentials
    with pytest.raises(ValidationError, match="Insecure default database credentials"):
        Settings(
            app_env="production",
            jwt_secret="c9f8e7d6c5b4a3928172635483920192837465ab",
            admin_password="StrongProdOperator999!",
            database_url="postgresql+psycopg://cable_admin:password@localhost:5432/cable_manager",
        )

    # Accept valid production configuration with default trusted proxy
    prod_settings_default = Settings(
        app_env="production",
        jwt_secret="c9f8e7d6c5b4a3928172635483920192837465ab",
        admin_password="StrongProdOperator999!",
        database_url="postgresql+psycopg://prod_user:StrongDBPass987!@db:5432/cable_prod",
    )
    assert prod_settings_default.app_env == "production"
    assert "172.28.0.10" in prod_settings_default.trusted_proxy_list

    # Accept valid production configuration with explicit trusted proxies
    prod_settings = Settings(
        app_env="production",
        jwt_secret="c9f8e7d6c5b4a3928172635483920192837465ab",
        admin_password="StrongProdOperator999!",
        database_url="postgresql+psycopg://prod_user:StrongDBPass987!@db:5432/cable_prod",
        trusted_proxies="127.0.0.1,172.28.0.10",
    )
    assert prod_settings.app_env == "production"
