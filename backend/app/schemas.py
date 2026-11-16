from datetime import datetime
from decimal import Decimal
import re
import zoneinfo
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, field_serializer

# Currencies commonly used or recognized
SUPPORTED_CURRENCIES = {
    "INR", "USD", "EUR", "GBP", "AED", "AUD", "CAD", "SGD", "JPY", "CHF", "CNY",
    "NZD", "ZAR", "BRL", "MXN", "HKD", "MYR", "THB", "PHP", "IDR", "SAR", "QAR",
    "KWD", "OMR", "BHD", "LKR", "PKR", "BDT", "NPR"
}

ALLOWED_LATE_POLICIES = {"none", "reminder_only", "suspend_after_grace"}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class BusinessSettingsBase(BaseModel):
    business_name: str
    contact_number: str
    email: EmailStr | None = None
    address: str | None = None
    service_areas: list[str]
    currency_code: str = "INR"
    timezone: str = "Asia/Kolkata"
    default_monthly_amount: Decimal = Decimal("300.00")
    billing_day: int = 1
    grace_period_days: int = 5
    late_payment_policy: str | None = "none"

    @field_validator("business_name")
    @classmethod
    def validate_business_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Business name cannot be empty")
        if len(trimmed) > 255:
            raise ValueError("Business name must not exceed 255 characters")
        return trimmed

    @field_validator("contact_number")
    @classmethod
    def validate_contact_number(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Contact number cannot be empty")
        digits = re.sub(r"\D", "", trimmed)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Contact number must contain between 7 and 15 digits")
        if len(trimmed) > 50:
            raise ValueError("Contact number must not exceed 50 characters")
        return trimmed

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        if len(trimmed) > 500:
            raise ValueError("Address must not exceed 500 characters")
        return trimmed

    @field_validator("service_areas")
    @classmethod
    def validate_service_areas(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one service area is required")
        cleaned: list[str] = []
        seen = set()
        for item in v:
            trimmed = item.strip()
            if not trimmed:
                raise ValueError("Service area name cannot be empty")
            lower = trimmed.lower()
            if lower in seen:
                raise ValueError(f"Duplicate service area: '{trimmed}'")
            seen.add(lower)
            cleaned.append(trimmed)
        return cleaned

    @field_validator("currency_code")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        code = v.strip().upper()
        if code not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency code: '{code}'. Must be a valid 3-letter currency code (e.g., INR, USD, EUR).")
        return code

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        tz = v.strip()
        try:
            zoneinfo.ZoneInfo(tz)
        except Exception:
            raise ValueError(f"Invalid timezone identifier: '{tz}'")
        return tz

    @field_validator("default_monthly_amount")
    @classmethod
    def validate_default_monthly_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Default monthly subscription amount must be greater than 0")
        if v > Decimal("9999999999.99"):
            raise ValueError("Default monthly subscription amount exceeds maximum allowed value")
        # Ensure at most 2 decimal places
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("Default monthly subscription amount cannot have more than 2 decimal places")
        return v.quantize(Decimal("0.01"))

    @field_validator("billing_day")
    @classmethod
    def validate_billing_day(cls, v: int) -> int:
        if v < 1 or v > 28:
            raise ValueError("Billing day must be between 1 and 28 (to ensure monthly validity)")
        return v

    @field_validator("grace_period_days")
    @classmethod
    def validate_grace_period_days(cls, v: int) -> int:
        if v < 0 or v > 30:
            raise ValueError("Grace period days must be between 0 and 30")
        return v

    @field_validator("late_payment_policy")
    @classmethod
    def validate_late_payment_policy(cls, v: str | None) -> str | None:
        if v is None:
            return "none"
        val = v.strip().lower()
        if val not in ALLOWED_LATE_POLICIES:
            raise ValueError(f"Invalid late payment policy: '{v}'. Must be one of: {', '.join(sorted(ALLOWED_LATE_POLICIES))}")
        return val


class BusinessSettingsCreate(BusinessSettingsBase):
    pass


class BusinessSettingsUpdate(BaseModel):
    business_name: str | None = None
    contact_number: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    service_areas: list[str] | None = None
    currency_code: str | None = None
    timezone: str | None = None
    default_monthly_amount: Decimal | None = None
    billing_day: int | None = None
    grace_period_days: int | None = None
    late_payment_policy: str | None = None

    @field_validator("business_name")
    @classmethod
    def validate_business_name(cls, v: str | None) -> str | None:
        if v is not None:
            return BusinessSettingsBase.validate_business_name(v)
        return None

    @field_validator("contact_number")
    @classmethod
    def validate_contact_number(cls, v: str | None) -> str | None:
        if v is not None:
            return BusinessSettingsBase.validate_contact_number(v)
        return None

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str | None) -> str | None:
        if v is not None:
            return BusinessSettingsBase.validate_address(v)
        return None

    @field_validator("service_areas")
    @classmethod
    def validate_service_areas(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return BusinessSettingsBase.validate_service_areas(v)
        return None

    @field_validator("currency_code")
    @classmethod
    def validate_currency_code(cls, v: str | None) -> str | None:
        if v is not None:
            return BusinessSettingsBase.validate_currency_code(v)
        return None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None:
            return BusinessSettingsBase.validate_timezone(v)
        return None

    @field_validator("default_monthly_amount")
    @classmethod
    def validate_default_monthly_amount(cls, v: Decimal | None) -> Decimal | None:
        if v is not None:
            return BusinessSettingsBase.validate_default_monthly_amount(v)
        return None

    @field_validator("billing_day")
    @classmethod
    def validate_billing_day(cls, v: int | None) -> int | None:
        if v is not None:
            return BusinessSettingsBase.validate_billing_day(v)
        return None

    @field_validator("grace_period_days")
    @classmethod
    def validate_grace_period_days(cls, v: int | None) -> int | None:
        if v is not None:
            return BusinessSettingsBase.validate_grace_period_days(v)
        return None

    @field_validator("late_payment_policy")
    @classmethod
    def validate_late_payment_policy(cls, v: str | None) -> str | None:
        if v is not None:
            return BusinessSettingsBase.validate_late_payment_policy(v)
        return None


class BusinessSettingsResponse(BusinessSettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("default_monthly_amount")
    def serialize_default_monthly_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)
