"""Payment Engine with FIFO Allocation, Advance Credit, and Audit Reversals.

Responsibilities:
1. Records manually received payments (cash, upi, other).
2. Generates sequential receipts like 'RCP-202611-0001'.
3. Performs FIFO allocation across outstanding invoices (oldest billing_month/id first).
4. Automatically calculates unallocated balance as advance credit.
5. Performs payment reversal inside an atomic database transaction:
   - Marks payment is_reversed = True, records reversal reason and timestamp.
   - Preserves PaymentAllocation records for immutable financial audit trails.
   - Reverts invoice paid_amount and updates status accordingly.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from ..models import Customer, Invoice, Payment, PaymentAllocation


def generate_next_receipt_number(db: Session) -> str:
    """Generate sequential receipt number like 'RCP-202611-0001'."""
    now_str = date.today().strftime("%Y%m")
    prefix = f"RCP-{now_str}-"
    existing = (
        db.query(Payment.receipt_number)
        .filter(Payment.receipt_number.like(f"{prefix}%"))
        .all()
    )
    max_num = 0
    for (rcp_num,) in existing:
        if rcp_num and len(rcp_num) > len(prefix):
            try:
                num = int(rcp_num[len(prefix):])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_num = max_num + 1
    return f"{prefix}{next_num:04d}"


def record_payment_fifo(
    customer_id: int,
    amount: Decimal,
    payment_method: str,
    paid_date: date,
    notes: str | None,
    db: Session,
) -> tuple[Payment, list[PaymentAllocation], Decimal]:
    """Record payment and allocate FIFO to unpaid invoices.

    Returns (Payment, list[PaymentAllocation], unallocated_advance_credit).
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )

    # Retry loop for receipt generation to prevent concurrent receipt_number collisions
    max_retries = 10
    payment = None
    for _ in range(max_retries):
        receipt_number = generate_next_receipt_number(db)
        payment = Payment(
            receipt_number=receipt_number,
            customer_id=customer_id,
            amount=amount,
            payment_method=payment_method,
            paid_date=paid_date,
            notes=notes,
            is_reversed=False,
        )
        try:
            db.add(payment)
            db.flush()  # Generates payment.id
            break
        except IntegrityError:
            db.rollback()
            payment = None

    if payment is None:
        raise RuntimeError("Could not allocate unique receipt number due to concurrent activity.")

    # Find unpaid/partial invoices for this customer ordered by billing_month asc, id asc
    unpaid_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.status.in_(["pending", "partial"]),
        )
        .order_by(Invoice.billing_month.asc(), Invoice.id.asc())
        .all()
    )

    remaining_payment = amount
    allocations: list[PaymentAllocation] = []

    for inv in unpaid_invoices:
        if remaining_payment <= Decimal("0.00"):
            break
        outstanding = inv.amount - inv.paid_amount
        if outstanding <= Decimal("0.00"):
            continue

        alloc_amount = min(remaining_payment, outstanding)
        allocation = PaymentAllocation(
            payment_id=payment.id,
            invoice_id=inv.id,
            allocated_amount=alloc_amount,
        )
        db.add(allocation)
        allocations.append(allocation)

        inv.paid_amount += alloc_amount
        remaining_payment -= alloc_amount

        # Update invoice status
        if inv.paid_amount >= inv.amount:
            inv.status = "paid"
        elif inv.paid_amount > Decimal("0.00"):
            inv.status = "partial"
        else:
            inv.status = "pending"

    advance_credit = remaining_payment
    db.commit()
    db.refresh(payment)
    return payment, allocations, advance_credit


def reverse_payment_transaction(
    payment_id: int,
    reversal_reason: str,
    db: Session,
) -> Payment:
    """Reverse a payment in an atomic transaction.

    1. Verifies payment is not already reversed.
    2. Marks payment reversed with reason and UTC timestamp.
    3. Reverts each associated allocation from the invoice paid_amount.
    4. Preserves PaymentAllocation records for immutable historical audit.
    5. Updates invoice statuses back to partial or pending.
    """
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID {payment_id} not found",
        )

    if payment.is_reversed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment has already been reversed.",
        )

    # Mark reversed
    payment.is_reversed = True
    payment.reversal_reason = reversal_reason.strip()
    payment.reversed_at = datetime.now(timezone.utc)

    # Find allocations for this payment
    allocations = (
        db.query(PaymentAllocation)
        .filter(PaymentAllocation.payment_id == payment_id)
        .all()
    )

    for alloc in allocations:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == alloc.invoice_id)
            .with_for_update()
            .first()
        )
        if invoice:
            invoice.paid_amount -= alloc.allocated_amount
            if invoice.paid_amount < Decimal("0.00"):
                invoice.paid_amount = Decimal("0.00")

            if invoice.paid_amount == Decimal("0.00"):
                invoice.status = "pending"
            elif invoice.paid_amount < invoice.amount:
                invoice.status = "partial"
            else:
                invoice.status = "paid"

        # Note: In accordance with financial audit requirements, allocation records are preserved
        # rather than physically deleted. Downstream queries join on Payment.is_reversed == False.

    db.commit()
    db.refresh(payment)
    return payment
