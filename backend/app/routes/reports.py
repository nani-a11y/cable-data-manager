from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from decimal import Decimal
import re

from ..database import get_db
from ..models import AdminUser, BusinessSettings, Customer, Invoice, Payment, PaymentAllocation
from ..schemas import MonthlyReviewMetrics, MonthlyRegisterResponse, MonthlyRegisterItem
from .auth import get_current_admin

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/monthly-review/{billing_month}", response_model=MonthlyReviewMetrics)
def get_monthly_review(
    billing_month: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Calculate and return Monthly Review metrics for a selected month (YYYY-MM).

    1. Estimated Amount:
       - If invoices exist: sum(invoice.amount) for that month.
       - If no invoices exist yet: sum(customer.monthly_amount) for all active customers.
    2. Amount Collected:
       - Sum of effective allocations to invoices of this billing month.
       - Excludes reversed payments.
    3. Pending Amount:
       - (Total month invoices amount) - (effective paid amount for month invoices).
    4. Older Arrears:
       - Sum of unpaid balances on invoices belonging to billing_month < selected month.
    5. Advance Credit:
       - Sum of total unallocated credit across all active customers.
    """
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", billing_month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Billing month must be in YYYY-MM format (e.g., '2026-11')",
        )

    # 1. Check if invoices exist for selected billing_month
    invoices = db.query(Invoice).filter(Invoice.billing_month == billing_month).all()
    is_invoice_backed = len(invoices) > 0

    if is_invoice_backed:
        estimated_amount = sum((inv.amount for inv in invoices), Decimal("0.00"))
        # Amount collected specifically for this month's invoices via payment allocations
        month_invoice_ids = [inv.id for inv in invoices]
        amount_collected = (
            db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .filter(
                PaymentAllocation.invoice_id.in_(month_invoice_ids),
                Payment.is_reversed == False,
            )
            .scalar()
        )
        pending_amount = estimated_amount - amount_collected
        if pending_amount < Decimal("0.00"):
            pending_amount = Decimal("0.00")
    else:
        # Sum current rates of active customers
        active_customers = db.query(Customer).filter(Customer.is_active == True).all()
        estimated_amount = sum((c.monthly_amount for c in active_customers), Decimal("0.00"))
        amount_collected = Decimal("0.00")
        pending_amount = estimated_amount

    # Collection percentage
    if estimated_amount > Decimal("0.00"):
        collection_pct = float(round((amount_collected / estimated_amount) * 100, 2))
    else:
        collection_pct = 0.0

    # Older Arrears: invoices with billing_month < selected month
    older_invoices = db.query(Invoice).filter(Invoice.billing_month < billing_month).all()
    older_arrears = sum((inv.amount - inv.paid_amount for inv in older_invoices), Decimal("0.00"))

    # Total Advance Credit across system: sum of valid unallocated payments
    total_valid_payments = (
        db.query(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
        .filter(Payment.is_reversed == False)
        .scalar()
    )
    total_allocations = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(Payment.is_reversed == False)
        .scalar()
    )
    total_advance_credit = total_valid_payments - total_allocations
    if total_advance_credit < Decimal("0.00"):
        total_advance_credit = Decimal("0.00")

    active_count = db.query(Customer).filter(Customer.is_active == True).count()
    inactive_count = db.query(Customer).filter(Customer.is_active == False).count()

    return MonthlyReviewMetrics(
        billing_month=billing_month,
        is_invoice_backed=is_invoice_backed,
        estimated_amount=f"{estimated_amount:.2f}",
        amount_collected=f"{amount_collected:.2f}",
        pending_amount=f"{pending_amount:.2f}",
        collection_percentage=collection_pct,
        older_arrears=f"{older_arrears:.2f}",
        advance_credit=f"{total_advance_credit:.2f}",
        total_active_customers=active_count,
        total_inactive_customers=inactive_count,
    )


@router.get("/monthly-register/{billing_month}", response_model=MonthlyRegisterResponse)
def get_monthly_register(
    billing_month: str,
    area: str | None = Query(None, description="Filter by service area"),
    status_filter: str | None = Query(None, description="Filter by status: paid, partial, unpaid"),
    search: str | None = Query(None, description="Search customer name, phone, or box number"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Retrieve subscriber-by-subscriber collection register for a selected month (YYYY-MM).

    Includes filters for:
    - Service Area
    - Payment Status (paid, partial, unpaid)
    - Customer search

    Financial definition:
    - If invoices exist for this month: amount_due = invoice.amount, amount_collected = allocated payments on that invoice.
    - If invoices do not exist: amount_due = customer.monthly_amount, amount_collected = 0.00.
    """
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", billing_month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Billing month must be in YYYY-MM format (e.g., '2026-11')",
        )

    # 1. Fetch all customers (active or those who have invoices in this month)
    cust_query = db.query(Customer)
    if area:
        cust_query = cust_query.filter(Customer.area == area.strip())
    if search:
        st = f"%{search.strip().lower()}%"
        cust_query = cust_query.filter(
            (func.lower(Customer.name).like(st))
            | (func.lower(Customer.phone).like(st))
            | (func.lower(Customer.box_number).like(st))
            | (func.lower(Customer.display_id).like(st))
        )
    customers = cust_query.order_by(Customer.id.asc()).all()

    # 2. Fetch invoices for this month
    invoices = db.query(Invoice).filter(Invoice.billing_month == billing_month).all()
    inv_map = {inv.customer_id: inv for inv in invoices}

    # 3. Fetch allocations for invoices of this month
    month_inv_ids = [inv.id for inv in invoices]
    alloc_map: dict[int, Decimal] = {}
    if month_inv_ids:
        alloc_rows = (
            db.query(
                PaymentAllocation.invoice_id,
                func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")),
            )
            .join(Payment, PaymentAllocation.payment_id == Payment.id)
            .filter(PaymentAllocation.invoice_id.in_(month_inv_ids), Payment.is_reversed == False)
            .group_by(PaymentAllocation.invoice_id)
            .all()
        )
        alloc_map = {inv_id: val for inv_id, val in alloc_rows}

    items: list[MonthlyRegisterItem] = []
    total_expected = Decimal("0.00")
    total_collected = Decimal("0.00")
    total_pending = Decimal("0.00")

    for c in customers:
        inv = inv_map.get(c.id)
        if inv:
            due = inv.amount
            collected = alloc_map.get(inv.id, Decimal("0.00"))
            pending = due - collected
            if pending < Decimal("0.00"):
                pending = Decimal("0.00")

            if collected >= due and due > Decimal("0.00"):
                st_code = "paid"
            elif collected > Decimal("0.00"):
                st_code = "partial"
            else:
                st_code = "unpaid"
        else:
            # Not billed yet for this month
            if not c.is_active:
                continue  # skip inactive customers if no invoice exists
            due = c.monthly_amount
            collected = Decimal("0.00")
            pending = due
            st_code = "unpaid"

        if status_filter:
            sf = status_filter.strip().lower()
            if sf in {"paid", "partial", "unpaid"} and st_code != sf:
                continue

        total_expected += due
        total_collected += collected
        total_pending += pending

        items.append(
            MonthlyRegisterItem(
                customer_id=c.id,
                display_id=c.display_id,
                customer_name=c.name,
                phone=c.phone,
                box_number=c.box_number,
                area=c.area,
                monthly_amount=c.monthly_amount,
                amount_due=due,
                amount_collected=collected,
                pending_amount=pending,
                status=st_code,
                is_active=c.is_active,
            )
        )

    return MonthlyRegisterResponse(
        billing_month=billing_month,
        total_customers=len(items),
        total_expected=f"{total_expected:.2f}",
        total_collected=f"{total_collected:.2f}",
        total_pending=f"{total_pending:.2f}",
        items=items,
    )
