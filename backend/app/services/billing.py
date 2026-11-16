"""Billing and Invoice Generation Engine.

Responsibilities:
1. Generates one monthly invoice per active customer for a target billing_month (YYYY-MM).
2. Auto-assigns snapshot amount from customer.monthly_amount.
3. Automatically applies any unallocated advance credit using FIFO.
4. Catch-up engine: inspects business_settings.billing_day and timezone to generate overdue invoices on startup.
5. Idempotent: duplicate generations return existing invoices without error.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import zoneinfo
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..models import BusinessSettings, Customer, Invoice, Payment, PaymentAllocation


def generate_next_invoice_number(db: Session, billing_month: str) -> str:
    """Generate sequential invoice number like 'INV-202611-0001'."""
    clean_month = billing_month.replace("-", "")
    prefix = f"INV-{clean_month}-"
    # Find max invoice number for this month prefix
    existing = (
        db.query(Invoice.invoice_number)
        .filter(Invoice.invoice_number.like(f"{prefix}%"))
        .all()
    )
    max_num = 0
    for (inv_num,) in existing:
        if inv_num and len(inv_num) > len(prefix):
            try:
                num = int(inv_num[len(prefix):])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_num = max_num + 1
    return f"{prefix}{next_num:04d}"


def calculate_customer_advance_credit(customer_id: int, db: Session) -> Decimal:
    """Calculate available unallocated advance credit for a customer.

    Credit = Sum of valid non-reversed payments - Sum of non-reversed payment allocations.
    """
    total_paid = (
        db.query(func.coalesce(func.sum(Payment.amount), Decimal("0.00")))
        .filter(Payment.customer_id == customer_id, Payment.is_reversed == False)
        .scalar()
    )
    total_allocated = (
        db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(Payment.customer_id == customer_id, Payment.is_reversed == False)
        .scalar()
    )
    credit = total_paid - total_allocated
    return credit if credit > Decimal("0.00") else Decimal("0.00")


def apply_advance_credit_to_invoice(invoice: Invoice, db: Session) -> Decimal:
    """If customer has unallocated advance payment credit, allocate it to this invoice FIFO."""
    if invoice.paid_amount >= invoice.amount:
        return Decimal("0.00")

    needed = invoice.amount - invoice.paid_amount

    # Find unreversed payments for this customer with unallocated amounts (FIFO by paid_date, id)
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == invoice.customer_id, Payment.is_reversed == False)
        .order_by(Payment.paid_date.asc(), Payment.id.asc())
        .all()
    )

    total_applied = Decimal("0.00")

    for pay in payments:
        if needed <= Decimal("0.00"):
            break
        # Calculate unallocated amount on this specific payment
        allocated_on_pay = (
            db.query(func.coalesce(func.sum(PaymentAllocation.allocated_amount), Decimal("0.00")))
            .filter(PaymentAllocation.payment_id == pay.id)
            .scalar()
        )
        avail = pay.amount - allocated_on_pay
        if avail > Decimal("0.00"):
            alloc_amt = min(needed, avail)
            allocation = PaymentAllocation(
                payment_id=pay.id,
                invoice_id=invoice.id,
                allocated_amount=alloc_amt,
            )
            db.add(allocation)
            invoice.paid_amount += alloc_amt
            needed -= alloc_amt
            total_applied += alloc_amt

    # Update invoice status
    if invoice.paid_amount >= invoice.amount:
        invoice.status = "paid"
    elif invoice.paid_amount > Decimal("0.00"):
        invoice.status = "partial"
    else:
        invoice.status = "pending"

    return total_applied


def issue_invoice_for_customer(
    customer: Customer,
    billing_month: str,
    issued_date: date,
    db: Session,
) -> tuple[Invoice, bool]:
    """Issue a single monthly invoice for a customer.

    Returns (invoice, created_flag). Idempotent if invoice already exists.
    """
    # Check if invoice already exists for customer_id + billing_month
    existing = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer.id,
            Invoice.billing_month == billing_month,
        )
        .first()
    )
    if existing:
        return existing, False

    # Generate sequential invoice number with retry on collision
    max_retries = 10
    for _ in range(max_retries):
        inv_num = generate_next_invoice_number(db, billing_month)
        invoice = Invoice(
            invoice_number=inv_num,
            customer_id=customer.id,
            billing_month=billing_month,
            amount=customer.monthly_amount,  # Immutable rate snapshot
            paid_amount=Decimal("0.00"),
            status="pending",
            issued_date=issued_date,
        )
        try:
            db.add(invoice)
            db.flush()  # Assigns invoice.id without closing transaction
            # Automatically apply any available advance credit
            apply_advance_credit_to_invoice(invoice, db)
            db.commit()
            db.refresh(invoice)
            return invoice, True
        except IntegrityError:
            db.rollback()
            # Check if another process created it concurrently
            existing_after = (
                db.query(Invoice)
                .filter(
                    Invoice.customer_id == customer.id,
                    Invoice.billing_month == billing_month,
                )
                .first()
            )
            if existing_after:
                return existing_after, False
            # Otherwise retry invoice number generation

    raise RuntimeError(f"Could not generate invoice for customer {customer.id} due to concurrency.")


def run_monthly_billing_cycle(billing_month: str, db: Session) -> dict:
    """Run monthly invoice generation for all active customers.

    Safe under concurrency and idempotent.
    """
    # Active customers only
    active_customers = (
        db.query(Customer)
        .filter(Customer.is_active == True)
        .order_by(Customer.id.asc())
        .all()
    )

    # Determine invoice issued_date: use the first day of billing_month
    try:
        yr, mo = (int(p) for p in billing_month.split("-"))
        issued_date = date(yr, mo, 1)
    except Exception:
        issued_date = date.today()

    created_count = 0
    already_existing_count = 0
    total_amount = Decimal("0.00")

    for cust in active_customers:
        inv, created = issue_invoice_for_customer(cust, billing_month, issued_date, db)
        if created:
            created_count += 1
            total_amount += inv.amount
        else:
            already_existing_count += 1

    return {
        "billing_month": billing_month,
        "eligible_customers": len(active_customers),
        "invoices_created": created_count,
        "already_existing": already_existing_count,
        "total_billed_amount": f"{total_amount:.2f}",
    }


def run_startup_billing_catchup(db: Session) -> dict:
    """Catch-up engine to run on system startup.

    Determines if current month's billing day has arrived based on BusinessSettings.
    If today >= billing_day, runs billing cycle for the current month.
    """
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if not settings:
        return {"status": "skipped", "reason": "No business settings configured"}

    # Compute current date in business timezone
    try:
        tz = zoneinfo.ZoneInfo(settings.timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")

    now = datetime.now(tz)
    current_month_str = now.strftime("%Y-%m")
    billing_day = settings.billing_day

    # Check if billing day has arrived for this month
    if now.day >= billing_day:
        result = run_monthly_billing_cycle(current_month_str, db)
        result["status"] = "completed"
        return result

    return {
        "status": "pending_billing_day",
        "current_day": now.day,
        "billing_day": billing_day,
        "billing_month": current_month_str,
    }
