import ipaddress
import time
from collections import defaultdict
from threading import Lock
from typing import NamedTuple

from fastapi import HTTPException, Request, status
from .config import settings


class RateLimitPolicy(NamedTuple):
    max_failed_attempts: int = 5
    window_seconds: int = 60
    lockout_seconds: int = 60


class LoginRateLimiter:
    def __init__(self, policy: RateLimitPolicy | None = None):
        self.policy = policy or RateLimitPolicy()
        self._lock = Lock()
        self._failed_attempts: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}

    def extract_client_ip(self, request: Request) -> str:
        peer_ip = request.client.host if request.client and request.client.host else "127.0.0.1"

        # Only trust forwarded headers if direct peer is configured as a trusted proxy
        if not self._is_trusted_proxy(peer_ip):
            return peer_ip

        # Inspect X-Forwarded-For (take the first valid client IP)
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            parts = [p.strip() for p in x_forwarded_for.split(",") if p.strip()]
            if parts and self._is_valid_ip(parts[0]):
                return parts[0]

        # Inspect X-Real-IP
        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            candidate = x_real_ip.strip()
            if self._is_valid_ip(candidate):
                return candidate

        return peer_ip

    def _is_valid_ip(self, ip_str: str) -> bool:
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False

    def _is_trusted_proxy(self, ip_str: str) -> bool:
        if ip_str in settings.trusted_proxy_list:
            return True
        if not self._is_valid_ip(ip_str):
            return False
        addr = ipaddress.ip_address(ip_str)
        for trusted in settings.trusted_proxy_list:
            if not self._is_valid_ip(trusted) and "/" not in trusted:
                continue
            try:
                if "/" in trusted:
                    if addr in ipaddress.ip_network(trusted, strict=False):
                        return True
                else:
                    if addr == ipaddress.ip_address(trusted):
                        return True
            except ValueError:
                continue
        return False

    def check_rate_limit(self, client_ip: str):
        now = time.time()
        with self._lock:
            # Check active lockout
            locked_until = self._lockouts.get(client_ip, 0)
            if now < locked_until:
                retry_after = max(1, int(locked_until - now) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many login attempts. Please try again after {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

            # Purge expired attempts outside window
            cutoff = now - self.policy.window_seconds
            attempts = [t for t in self._failed_attempts[client_ip] if t > cutoff]
            self._failed_attempts[client_ip] = attempts

            if len(attempts) >= self.policy.max_failed_attempts:
                self._lockouts[client_ip] = now + self.policy.lockout_seconds
                retry_after = self.policy.lockout_seconds
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many login attempts. Please try again after {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failure(self, client_ip: str):
        now = time.time()
        with self._lock:
            self._failed_attempts[client_ip].append(now)
            cutoff = now - self.policy.window_seconds
            attempts = [t for t in self._failed_attempts[client_ip] if t > cutoff]
            self._failed_attempts[client_ip] = attempts
            if len(attempts) >= self.policy.max_failed_attempts:
                self._lockouts[client_ip] = now + self.policy.lockout_seconds

    def record_success(self, client_ip: str):
        with self._lock:
            self._failed_attempts.pop(client_ip, None)
            self._lockouts.pop(client_ip, None)

    def reset(self):
        with self._lock:
            self._failed_attempts.clear()
            self._lockouts.clear()


login_rate_limiter = LoginRateLimiter()
