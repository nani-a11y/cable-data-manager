import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models import AdminUser, BusinessSettings, Customer
from ..schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerPagination,
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
    return customer


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
