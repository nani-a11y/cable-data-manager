from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import re

from ..database import get_db
from ..models import AdminUser, Customer, Invoice
from ..schemas import InvoiceResponse
from ..services.billing import (
    issue_invoice_for_customer,
    run_monthly_billing_cycle,
    run_startup_billing_catchup,
)
from .auth import get_current_admin

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.post("/generate/{billing_month}")
def trigger_monthly_billing(
    billing_month: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Trigger monthly billing cycle for a given month (YYYY-MM).

    Generates invoices for all active customers idempotently.
    """
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", billing_month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Billing month must be in YYYY-MM format (e.g., '2026-11')",
        )

    result = run_monthly_billing_cycle(billing_month, db)
    return result


@router.post("/catch-up")
def trigger_billing_catchup(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Manually trigger billing catchup logic for the current month."""
    return run_startup_billing_catchup(db)


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    customer_id: int | None = Query(None, description="Filter by customer ID"),
    billing_month: str | None = Query(None, description="Filter by month YYYY-MM"),
    status: str | None = Query(None, description="Filter by status (pending, partial, paid)"),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List invoices with optional filters."""
    query = db.query(Invoice)
    if customer_id is not None:
        query = query.filter(Invoice.customer_id == customer_id)
    if billing_month:
        query = query.filter(Invoice.billing_month == billing_month)
    if status:
        query = query.filter(Invoice.status == status)

    return query.order_by(Invoice.billing_month.desc(), Invoice.id.desc()).all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Retrieve details for a single invoice."""
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice with ID {invoice_id} not found")
    return inv
