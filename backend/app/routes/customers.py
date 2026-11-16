import math
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models import AdminUser, BusinessSettings, Customer, Invoice, Payment, PaymentAllocation
from ..schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerPagination,
    CustomerFinancialHistoryResponse,
)
from .auth import get_current_admin

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _generate_next_display_id(db: Session) -> str:
    """Generate display_id like 'C-0001', 'C-0002' safely under concurrency.

    Extracts the highest existing sequence number from display_id strings.
    """
    display_ids = db.query(Customer.display_id).all()
    max_num = 0
    for (d_id,) in display_ids:
        if d_id and d_id.startswith("C-"):
            try:
                num = int(d_id[2:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_num = max_num + 1
    while True:
        candidate = f"C-{next_num:04d}"
        exists = db.query(Customer.id).filter(Customer.display_id == candidate).first()
        if not exists:
            return candidate
        next_num += 1


def _validate_service_area(area: str, db: Session) -> str:
    """Validate that area belongs to configured business settings service areas."""
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business configuration is missing. Configure service areas in settings first.",
        )

    # Extract service areas list
    service_areas = settings.service_areas
    # service_areas can be a list of strings or list of dicts {"name": ..., "is_active": ...}
    valid_names = set()
    for item in service_areas:
        if isinstance(item, str):
            valid_names.add(item.strip().lower())
        elif isinstance(item, dict) and "name" in item:
            # If dict, only consider if active (defaults to True if not specified)
            if item.get("is_active", True):
                valid_names.add(item["name"].strip().lower())

    area_clean = area.strip()
    if area_clean.lower() not in valid_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service area '{area_clean}' is not an active configured service area.",
        )
    return area_clean


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Create a new customer with automatic display ID and validated service area."""
    # 1. Validate service area against BusinessSettings
    cleaned_area = _validate_service_area(payload.area, db)

    # 2. Determine monthly amount (if omitted, fetch business settings default)
    monthly_amount = payload.monthly_amount
    if monthly_amount is None:
        settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business configuration is missing. Configure business settings first.",
            )
        monthly_amount = settings.default_monthly_amount

    # 3. Check for case-insensitive duplicate box number early for a friendly message
    cleaned_box = payload.box_number.strip()
    existing_box = (
        db.query(Customer.id)
        .filter(func.lower(Customer.box_number) == cleaned_box.lower())
        .first()
    )
    if existing_box:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A customer with box number '{cleaned_box}' already exists.",
        )

    max_retries = 10
    for attempt in range(max_retries):
        display_id = _generate_next_display_id(db)
        customer = Customer(
            display_id=display_id,
            name=payload.name.strip(),
            phone=payload.phone.strip(),
            box_number=cleaned_box,
            area=cleaned_area,
            monthly_amount=monthly_amount,
            is_active=True,
        )

        try:
            db.add(customer)
            db.commit()
            db.refresh(customer)
            return customer
        except IntegrityError as exc:
            db.rollback()
            err_str = str(exc).lower()
            # If box_number duplicated, fail immediately with 409
            if "uq_customers_box_number_lower" in err_str or (
                "box_number" in err_str and "display_id" not in err_str
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A customer with box number '{cleaned_box}' already exists.",
                ) from exc
            # If display_id collided due to concurrency, retry with new display_id
            if "display_id" in err_str:
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Could not generate unique customer ID due to concurrent activity. Please retry.",
                    ) from exc
                continue
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database integrity constraint violated during customer creation.",
            ) from exc


@router.get("", response_model=CustomerPagination)
def list_customers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search term for name, phone, or box number"),
    include_inactive: bool = Query(False, description="Include deactivated customers"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List customers with pagination, optional case-insensitive search, and active/inactive filtering."""
    query = db.query(Customer)

    # Filter by active status
    if not include_inactive:
        query = query.filter(Customer.is_active == True)

    # Search filter (case-insensitive on name, phone, box_number, or display_id)
    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Customer.name).like(search_term),
                func.lower(Customer.phone).like(search_term),
                func.lower(Customer.box_number).like(search_term),
                func.lower(Customer.display_id).like(search_term),
            )
        )

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size

    # Order by display_id asc
    items = query.order_by(Customer.id.asc()).offset(offset).limit(page_size).all()

    # Annotate with outstanding balance and advance credit efficiently
    if items:
        cust_ids = [c.id for c in items]

        # 1. Outstanding invoice dues per customer: sum(amount - paid_amount)
        invoice_rows = (
            db.query(
                Invoice.customer_id,
                func.coalesce(func.sum(Invoice.amount - Invoice.paid_amount), Decimal("0.00")),
            )
            .filter(Invoice.customer_id.in_(cust_ids))
            .group_by(Invoice.customer_id)
            .all()
        )
        dues_map = {cid: val for cid, val in invoice_rows}

        # 2. Advance credit = (Total valid payments) - (Total allocations on non-reversed payments)
        paid_rows = (
            db.query(
                Payment.customer_id,
                func.coalesce(func.sum(Payment.amount), Decimal("0.00")),
            )
            .filter(Payment.customer_id.in_(cust_ids), Payment.is_reversed == False)
            .group_by(Payment.customer_id)
            .all()
        )
        paid_map = {cid: val for cid, val in paid_rows}

        alloc_rows = (
            db.query(
                Payment.customer_id,
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")),
            )
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .filter(Payment.customer_id.in_(cust_ids), Payment.is_reversed == False)
            .group_by(Payment.customer_id)
            .all()
        )
        alloc_map = {cid: val for cid, val in alloc_rows}

        for c in items:
            c.current_outstanding_balance = dues_map.get(c.id, Decimal("0.00"))
            credit = paid_map.get(c.id, Decimal("0.00")) - alloc_map.get(c.id, Decimal("0.00"))
            c.advance_credit = credit if credit > Decimal("0.00") else Decimal("0.00")

    return CustomerPagination(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Retrieve detailed information for a single customer by internal ID."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    # Annotate balance and credit
    inv_due = (
        db.query(func.coalesce(func.sum(Invoice.amount - Invoice.paid_amount), Decimal("0.00")))
        .filter(Invoice.customer_id == customer_id)
        .scalar()
    )
    total_valid_paid = (
        db.query(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
        .filter(Payment.customer_id == customer_id, Payment.is_reversed == False)
        .scalar()
    )
    total_alloc = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(Payment.customer_id == customer_id, Payment.is_reversed == False)
        .scalar()
    )
    customer.current_outstanding_balance = inv_due
    credit = total_valid_paid - total_alloc
    customer.advance_credit = credit if credit > Decimal("0.00") else Decimal("0.00")
    return customer


@router.get("/{customer_id}/history", response_model=CustomerFinancialHistoryResponse)
def get_customer_financial_history(
    customer_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Retrieve full chronological invoices and payment history for a customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )

    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id)
        .order_by(Invoice.billing_month.desc(), Invoice.id.desc())
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer_id)
        .order_by(Payment.paid_date.desc(), Payment.id.desc())
        .all()
    )

    from decimal import Decimal
    total_invoiced = sum((inv.amount for inv in invoices), Decimal("0.00"))
    total_invoice_paid = sum((inv.paid_amount for inv in invoices), Decimal("0.00"))
    outstanding = total_invoiced - total_invoice_paid

    total_valid_payments = sum((p.amount for p in payments if not p.is_reversed), Decimal("0.00"))
    # Advance credit = valid payments - total allocations
    total_allocated = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(Payment.customer_id == customer_id, Payment.is_reversed == False)
        .scalar()
    )
    advance_credit = total_valid_payments - total_allocated
    if advance_credit < Decimal("0.00"):
        advance_credit = Decimal("0.00")

    # Annotate customer object
    customer.current_outstanding_balance = outstanding
    customer.advance_credit = advance_credit

    # Build chronological passbook / ledger entries (sorted by date asc, id asc)
    # Events:
    # 1. Invoice created -> date = issued_date, type = "charge", description = f"Monthly Due ({inv.billing_month})"
    # 2. Payment received -> date = paid_date, type = "payment", description = f"Payment Received ({pay.payment_method.upper()} - {pay.receipt_number})"
    # 3. Payment reversed -> date = reversed_at.date(), type = "reversal", description = f"Payment Reversal ({pay.receipt_number} - {pay.reversal_reason})"
    raw_events = []
    for inv in invoices:
        raw_events.append({
            "date": inv.issued_date,
            "created_at": inv.created_at,
            "sort_key": (inv.issued_date, 0, inv.id),
            "entry_type": "charge",
            "description": f"Monthly Charge ({inv.billing_month})",
            "charge_amount": inv.amount,
            "payment_amount": Decimal("0.00"),
        })

    for pay in payments:
        raw_events.append({
            "date": pay.paid_date,
            "created_at": pay.created_at,
            "sort_key": (pay.paid_date, 1, pay.id),
            "entry_type": "payment",
            "description": f"Payment Received ({pay.payment_method.upper()}) [Ref: {pay.receipt_number}]",
            "charge_amount": Decimal("0.00"),
            "payment_amount": pay.amount,
        })
        if pay.is_reversed:
            rev_date = pay.reversed_at.date() if pay.reversed_at else pay.paid_date
            raw_events.append({
                "date": rev_date,
                "created_at": pay.reversed_at or pay.created_at,
                "sort_key": (rev_date, 2, pay.id),
                "entry_type": "reversal",
                "description": f"Reversal: {pay.receipt_number} ({pay.reversal_reason or 'No reason provided'})",
                "charge_amount": pay.amount,
                "payment_amount": Decimal("0.00"),
            })

    # Sort events chronologically (oldest to newest)
    raw_events.sort(key=lambda x: x["sort_key"])

    running_bal = Decimal("0.00")
    ledger_entries = []
    for ev in raw_events:
        running_bal += ev["charge_amount"]
        running_bal -= ev["payment_amount"]
        ledger_entries.append({
            "date": ev["date"],
            "entry_type": ev["entry_type"],
            "description": ev["description"],
            "charge_amount": ev["charge_amount"],
            "payment_amount": ev["payment_amount"],
            "running_balance": running_bal,
        })

    return CustomerFinancialHistoryResponse(
        customer=customer,
        total_invoiced=f"{total_invoiced:.2f}",
        total_paid=f"{total_valid_payments:.2f}",
        outstanding_balance=f"{outstanding:.2f}",
        advance_credit=f"{advance_credit:.2f}",
        invoices=invoices,
        payments=payments,
        ledger=ledger_entries,
    )


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Update customer details (name, phone, box_number, area, monthly_amount, is_active)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )

    update_dict = payload.model_dump(exclude_unset=True)

    # Validate area if being updated
    if "area" in update_dict and update_dict["area"] is not None:
        update_dict["area"] = _validate_service_area(update_dict["area"], db)

    # Check box number uniqueness if being updated
    if "box_number" in update_dict and update_dict["box_number"] is not None:
        cleaned_box = update_dict["box_number"].strip()
        existing = (
            db.query(Customer.id)
            .filter(
                func.lower(Customer.box_number) == cleaned_box.lower(),
                Customer.id != customer_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A customer with box number '{cleaned_box}' already exists.",
            )
        update_dict["box_number"] = cleaned_box

    # Clean strings
    if "name" in update_dict and update_dict["name"] is not None:
        update_dict["name"] = update_dict["name"].strip()
    if "phone" in update_dict and update_dict["phone"] is not None:
        update_dict["phone"] = update_dict["phone"].strip()

    for field, val in update_dict.items():
        setattr(customer, field, val)

    try:
        db.commit()
        db.refresh(customer)
        return customer
    except IntegrityError as exc:
        db.rollback()
        err_msg = str(exc).lower()
        if "box_number" in err_msg or "uq_customers_box_number_lower" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A customer with this box number already exists.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database integrity constraint violated during customer update.",
        ) from exc


@router.delete("/{customer_id}", response_model=CustomerResponse)
def deactivate_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Soft-delete / deactivate a customer. Sets is_active = False.

    Never deletes customer record or associated invoices/payments from the database.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )

    if not customer.is_active:
        # Already inactive, idempotent return
        return customer

    customer.is_active = False
    db.commit()
    db.refresh(customer)
    return customer
