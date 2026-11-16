from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from decimal import Decimal

from ..database import get_db
from ..models import AdminUser, Payment
from ..schemas import (
    PaymentCreate,
    PaymentResponse,
    PaymentReversePayload,
    PaymentReceiptResponse,
)
from ..services.payments import (
    record_payment_fifo,
    reverse_payment_transaction,
)
from .auth import get_current_admin

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("", response_model=PaymentReceiptResponse, status_code=status.HTTP_201_CREATED)
def record_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Record a customer payment and allocate FIFO across outstanding invoices.

    Any excess payment becomes unallocated advance credit.
    """
    payment, allocations, advance_credit = record_payment_fifo(
        customer_id=payload.customer_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        paid_date=payload.paid_date,
        notes=payload.notes,
        db=db,
    )

    total_allocated = sum((a.allocated_amount for a in allocations), Decimal("0.00"))

    return PaymentReceiptResponse(
        payment=payment,
        allocated_invoices_count=len(allocations),
        total_allocated=f"{total_allocated:.2f}",
        advance_credit_remaining=f"{advance_credit:.2f}",
        message=f"Payment of ₹{payload.amount:.2f} recorded successfully ({len(allocations)} invoices settled/partially paid, ₹{advance_credit:.2f} remaining as advance credit).",
    )


@router.get("", response_model=list[PaymentResponse])
def list_payments(
    customer_id: int | None = Query(None, description="Filter by customer ID"),
    include_reversed: bool = Query(True, description="Include reversed payments"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List recorded payments."""
    query = db.query(Payment)
    if customer_id is not None:
        query = query.filter(Payment.customer_id == customer_id)
    if not include_reversed:
        query = query.filter(Payment.is_reversed == False)

    return query.order_by(Payment.paid_date.desc(), Payment.id.desc()).all()


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Retrieve details for a single payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment with ID {payment_id} not found")
    return payment


@router.post("/{payment_id}/reverse", response_model=PaymentResponse)
def reverse_payment(
    payment_id: int,
    payload: PaymentReversePayload,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Reverse a payment with an audit trail, resetting settled invoices to unpaid status."""
    return reverse_payment_transaction(
        payment_id=payment_id,
        reversal_reason=payload.reversal_reason,
        db=db,
    )
