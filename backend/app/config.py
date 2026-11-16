from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://cable_admin:password@localhost:5432/cable_manager"
    jwt_secret: str = "insecure-default-jwt-secret-replace-in-env"
    jwt_expire_minutes: int = 60
    admin_email: str = "admin@example.com"
    admin_password: str = "insecure-default-password-replace-in-env"
    cors_origins: str = "http://localhost:5173"
    trusted_proxies: str = "127.0.0.1,172.28.0.10"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [p.strip() for p in self.trusted_proxies.split(",") if p.strip()]

    @model_validator(mode="after")
    def validate_production_configuration(self):
        env = (self.app_env or "").strip().lower()
        if env == "production":
            import ipaddress

            # 1. JWT secret validation
            known_insecure_jwt = {
                "insecure-default-jwt-secret-replace-in-env",
                "development-secret-key-change-in-production-min-32-chars",
                "change-me",
                "changeme",
                "secret",
                "jwt-secret",
                "password",
            }
            secret = (self.jwt_secret or "").strip()
            if not secret:
                raise ValueError("JWT_SECRET must not be empty in production.")
            secret_lower = secret.lower()
            if (
                secret_lower in known_insecure_jwt
                or "replace-in-env" in secret_lower
                or "change_this" in secret_lower
            ):
                raise ValueError("Insecure default or placeholder JWT_SECRET is rejected in production.")
            if len(secret) < 32:
                raise ValueError(
                    f"JWT_SECRET must be at least 32 characters in production (provided {len(secret)} characters)."
                )
            if len(set(secret)) < 8:
                raise ValueError("JWT_SECRET lacks sufficient entropy / character diversity for production.")

            # 2. Admin password validation (Minimum 12 chars, entropy, weak list)
            from .security import validate_admin_password

            try:
                validate_admin_password(self.admin_password)
            except ValueError as exc:
                raise ValueError(f"Production ADMIN_PASSWORD rejected: {exc}")

            # 3. Database URL check
            db_url_lower = (self.database_url or "").lower()
            if (
                ":password@" in db_url_lower
                or "cable_admin:password" in db_url_lower
                or "change_this" in db_url_lower
            ):
                raise ValueError("Insecure default database credentials detected in production DATABASE_URL.")

            # 4. Trusted proxy validation
            proxies = (self.trusted_proxies or "").strip()
            if not proxies:
                raise ValueError("TRUSTED_PROXIES must not be empty in production.")
            if "*" in proxies:
                raise ValueError("Wildcard '*' is forbidden in production TRUSTED_PROXIES.")

            for entry in self.trusted_proxy_list:
                if entry in ["localhost", "testclient"]:
                    continue
                try:
                    if "/" in entry:
                        ipaddress.ip_network(entry, strict=False)
                    else:
                        ipaddress.ip_address(entry)
                except ValueError:
                    raise ValueError(f"Invalid IP address or CIDR network in TRUSTED_PROXIES: '{entry}'.")

        return self


settings = Settings()
