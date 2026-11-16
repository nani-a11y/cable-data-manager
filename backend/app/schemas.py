from datetime import date, datetime
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
    service_areas: list[str | dict]
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
    def validate_service_areas(cls, v: list[str | dict]) -> list[str | dict]:
        if not v:
            raise ValueError("At least one service area is required")
        cleaned: list[str | dict] = []
        seen = set()
        for item in v:
            if isinstance(item, str):
                trimmed = item.strip()
                if not trimmed:
                    raise ValueError("Service area name cannot be empty")
                lower = trimmed.lower()
                if lower in seen:
                    raise ValueError(f"Duplicate service area: '{trimmed}'")
                seen.add(lower)
                cleaned.append(trimmed)
            elif isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                if not name:
                    raise ValueError("Service area name cannot be empty")
                lower = name.lower()
                if lower in seen:
                    raise ValueError(f"Duplicate service area: '{name}'")
                seen.add(lower)
                is_active = bool(item.get("is_active", True))
                cleaned.append({"name": name, "is_active": is_active})
            else:
                raise ValueError("Invalid service area format")
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
    def validate_service_areas(cls, v: list[str | dict] | None) -> list[str | dict] | None:
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


# --- Area & Bulk Subscription Management Schemas ---

class AreaCreatePayload(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Area name cannot be empty")
        if len(trimmed) > 100:
            raise ValueError("Area name must not exceed 100 characters")
        return trimmed


class AreaRenamePayload(BaseModel):
    old_name: str
    new_name: str

    @field_validator("old_name", "new_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Area name cannot be empty")
        if len(trimmed) > 100:
            raise ValueError("Area name must not exceed 100 characters")
        return trimmed


class AreaArchivePayload(BaseModel):
    name: str
    is_active: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Area name cannot be empty")
        return trimmed


class BulkRateUpdatePayload(BaseModel):
    new_monthly_amount: Decimal
    confirm: bool

    @field_validator("new_monthly_amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("New monthly subscription amount must be greater than 0")
        if v > Decimal("9999999999.99"):
            raise ValueError("Amount exceeds maximum allowed limit")
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v.quantize(Decimal("0.01"))


class BulkRateUpdateResponse(BaseModel):
    affected_customers_count: int
    new_monthly_amount: str
    message: str


# --- Customer Schemas ---

class CustomerBase(BaseModel):
    name: str
    phone: str
    box_number: str
    area: str
    monthly_amount: Decimal | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Customer name cannot be empty")
        if len(trimmed) > 255:
            raise ValueError("Customer name must not exceed 255 characters")
        return trimmed

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Phone number cannot be empty")
        digits = re.sub(r"\D", "", trimmed)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone number must contain between 7 and 15 digits")
        if len(trimmed) > 50:
            raise ValueError("Phone number must not exceed 50 characters")
        return trimmed

    @field_validator("box_number")
    @classmethod
    def validate_box_number(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Box number cannot be empty")
        if len(trimmed) > 100:
            raise ValueError("Box number must not exceed 100 characters")
        return trimmed

    @field_validator("area")
    @classmethod
    def validate_area(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Area cannot be empty")
        if len(trimmed) > 100:
            raise ValueError("Area must not exceed 100 characters")
        return trimmed

    @field_validator("monthly_amount")
    @classmethod
    def validate_monthly_amount(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return None
        if v <= Decimal("0"):
            raise ValueError("Monthly amount must be greater than 0")
        if v > Decimal("9999999999.99"):
            raise ValueError("Monthly amount exceeds maximum allowed value")
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("Monthly amount cannot have more than 2 decimal places")
        return v.quantize(Decimal("0.01"))


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    box_number: str | None = None
    area: str | None = None
    monthly_amount: Decimal | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            return CustomerBase.validate_name(v)
        return None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None:
            return CustomerBase.validate_phone(v)
        return None

    @field_validator("box_number")
    @classmethod
    def validate_box_number(cls, v: str | None) -> str | None:
        if v is not None:
            return CustomerBase.validate_box_number(v)
        return None

    @field_validator("area")
    @classmethod
    def validate_area(cls, v: str | None) -> str | None:
        if v is not None:
            return CustomerBase.validate_area(v)
        return None

    @field_validator("monthly_amount")
    @classmethod
    def validate_monthly_amount(cls, v: Decimal | None) -> Decimal | None:
        if v is not None:
            return CustomerBase.validate_monthly_amount(v)
        return None


class CustomerResponse(BaseModel):
    id: int
    display_id: str
    name: str
    phone: str
    box_number: str
    area: str
    monthly_amount: Decimal
    is_active: bool
    current_outstanding_balance: Decimal = Decimal("0.00")
    advance_credit: Decimal = Decimal("0.00")
    created_at: datetime
    updated_at: datetime

    @field_serializer("monthly_amount")
    def serialize_monthly_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("current_outstanding_balance")
    def serialize_current_outstanding_balance(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("advance_credit")
    def serialize_advance_credit(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)


class CustomerPagination(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class MonthlyReviewMetrics(BaseModel):
    billing_month: str
    is_invoice_backed: bool
    estimated_amount: str
    amount_collected: str
    pending_amount: str
    collection_percentage: float
    older_arrears: str
    advance_credit: str
    total_active_customers: int
    total_inactive_customers: int


# --- Invoice Schemas ---

class InvoiceBase(BaseModel):
    customer_id: int
    billing_month: str
    amount: Decimal
    issued_date: date

    @field_validator("billing_month")
    @classmethod
    def validate_billing_month(cls, v: str) -> str:
        trimmed = v.strip()
        if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", trimmed):
            raise ValueError("Billing month must be in YYYY-MM format (e.g., '2026-11')")
        return trimmed

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Invoice amount must be greater than 0")
        if v > Decimal("9999999999.99"):
            raise ValueError("Invoice amount exceeds maximum allowed value")
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("Invoice amount cannot have more than 2 decimal places")
        return v.quantize(Decimal("0.01"))


class InvoiceCreate(InvoiceBase):
    invoice_number: str | None = None


class InvoiceResponse(InvoiceBase):
    id: int
    invoice_number: str
    paid_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("amount")
    def serialize_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("paid_amount")
    def serialize_paid_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)


# --- Payment Schemas ---

class PaymentBase(BaseModel):
    customer_id: int
    amount: Decimal
    payment_method: str = "cash"
    paid_date: date
    notes: str | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Payment amount must be greater than 0")
        if v > Decimal("9999999999.99"):
            raise ValueError("Payment amount exceeds maximum allowed value")
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("Payment amount cannot have more than 2 decimal places")
        return v.quantize(Decimal("0.01"))

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: str) -> str:
        method = v.strip().lower()
        if method not in {"cash", "upi", "other"}:
            raise ValueError("Payment method must be one of: 'cash', 'upi', 'other'")
        return method

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        if len(trimmed) > 255:
            raise ValueError("Payment notes must not exceed 255 characters")
        return trimmed


class PaymentCreate(PaymentBase):
    receipt_number: str | None = None


class PaymentResponse(PaymentBase):
    id: int
    receipt_number: str
    is_reversed: bool
    reversal_reason: str | None = None
    reversed_at: datetime | None = None
    created_at: datetime

    @field_serializer("amount")
    def serialize_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)


class PaymentReversePayload(BaseModel):
    reversal_reason: str

    @field_validator("reversal_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Reversal reason cannot be empty")
        if len(trimmed) > 255:
            raise ValueError("Reversal reason must not exceed 255 characters")
        return trimmed


class PaymentReceiptResponse(BaseModel):
    payment: PaymentResponse
    allocated_invoices_count: int
    total_allocated: str
    advance_credit_remaining: str
    message: str


# --- Payment Allocation Schemas ---

class PaymentAllocationBase(BaseModel):
    payment_id: int
    invoice_id: int
    allocated_amount: Decimal

    @field_validator("allocated_amount")
    @classmethod
    def validate_allocated_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Allocated amount must be greater than 0")
        if v > Decimal("9999999999.99"):
            raise ValueError("Allocated amount exceeds maximum allowed value")
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("Allocated amount cannot have more than 2 decimal places")
        return v.quantize(Decimal("0.01"))


class PaymentAllocationCreate(PaymentAllocationBase):
    pass


class PaymentAllocationResponse(PaymentAllocationBase):
    id: int
    created_at: datetime

    @field_serializer("allocated_amount")
    def serialize_allocated_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)


class LedgerEntryResponse(BaseModel):
    date: date
    entry_type: str  # "charge", "payment", "reversal"
    description: str
    charge_amount: Decimal = Decimal("0.00")
    payment_amount: Decimal = Decimal("0.00")
    running_balance: Decimal = Decimal("0.00")

    @field_serializer("charge_amount")
    def serialize_charge_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("payment_amount")
    def serialize_payment_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("running_balance")
    def serialize_running_balance(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)


class CustomerFinancialHistoryResponse(BaseModel):
    customer: CustomerResponse
    total_invoiced: str
    total_paid: str
    outstanding_balance: str
    advance_credit: str
    invoices: list[InvoiceResponse]
    payments: list[PaymentResponse]
    ledger: list[LedgerEntryResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Monthly Register Schemas ---

class MonthlyRegisterItem(BaseModel):
    customer_id: int
    display_id: str
    customer_name: str
    phone: str
    box_number: str
    area: str
    monthly_amount: Decimal
    amount_due: Decimal
    amount_collected: Decimal
    pending_amount: Decimal
    status: str  # "paid", "partial", "unpaid"
    is_active: bool

    @field_serializer("monthly_amount")
    def serialize_monthly_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("amount_due")
    def serialize_amount_due(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("amount_collected")
    def serialize_amount_collected(self, val: Decimal) -> str:
        return f"{val:.2f}"

    @field_serializer("pending_amount")
    def serialize_pending_amount(self, val: Decimal) -> str:
        return f"{val:.2f}"

    model_config = ConfigDict(from_attributes=True)


class MonthlyRegisterResponse(BaseModel):
    billing_month: str
    total_customers: int
    total_expected: str
    total_collected: str
    total_pending: str
    items: list[MonthlyRegisterItem]
