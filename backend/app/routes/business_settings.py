from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from ..database import get_db
from ..models import AdminUser, BusinessSettings, Customer
from ..schemas import (
    BusinessSettingsCreate,
    BusinessSettingsUpdate,
    BusinessSettingsResponse,
    AreaCreatePayload,
    AreaRenamePayload,
    AreaArchivePayload,
    BulkRateUpdatePayload,
    BulkRateUpdateResponse,
)
from .auth import get_current_admin

router = APIRouter(prefix="/api/business-settings", tags=["business-settings"])


@router.get("", response_model=BusinessSettingsResponse)
def get_business_settings(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business configuration not found",
        )
    return settings


@router.post("", response_model=BusinessSettingsResponse, status_code=status.HTTP_201_CREATED)
def create_business_settings(
    payload: BusinessSettingsCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    existing = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Business configuration already exists. Use PUT or PATCH to update.",
        )

    settings = BusinessSettings(
        id=1,
        business_name=payload.business_name,
        contact_number=payload.contact_number,
        email=str(payload.email) if payload.email else None,
        address=payload.address,
        service_areas=payload.service_areas,
        currency_code=payload.currency_code,
        timezone=payload.timezone,
        default_monthly_amount=payload.default_monthly_amount,
        billing_day=payload.billing_day,
        grace_period_days=payload.grace_period_days,
        late_payment_policy=payload.late_payment_policy,
    )
    try:
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return settings
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate or invalid configuration rejected by database constraint.",
        ) from exc


@router.put("", response_model=BusinessSettingsResponse)
def update_business_settings(
    payload: BusinessSettingsCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business configuration not found. Create configuration first.",
        )

    settings.business_name = payload.business_name
    settings.contact_number = payload.contact_number
    settings.email = str(payload.email) if payload.email else None
    settings.address = payload.address
    settings.service_areas = payload.service_areas
    settings.currency_code = payload.currency_code
    settings.timezone = payload.timezone
    settings.default_monthly_amount = payload.default_monthly_amount
    settings.billing_day = payload.billing_day
    settings.grace_period_days = payload.grace_period_days
    settings.late_payment_policy = payload.late_payment_policy

    try:
        db.commit()
        db.refresh(settings)
        return settings
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database constraint violation during settings update.",
        ) from exc


@router.patch("", response_model=BusinessSettingsResponse)
def patch_business_settings(
    payload: BusinessSettingsUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business configuration not found. Create configuration first.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"]:
        update_data["email"] = str(update_data["email"])

    for field, value in update_data.items():
        setattr(settings, field, value)

    try:
        db.commit()
        db.refresh(settings)
        return settings
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database constraint violation during settings patch.",
        ) from exc


def _normalize_areas_list(areas_data: list) -> list[dict]:
    """Ensure service areas list is represented as [{"name": str, "is_active": bool}]."""
    normalized: list[dict] = []
    seen = set()
    for item in areas_data:
        if isinstance(item, str):
            name = item.strip()
            if name.lower() not in seen:
                seen.add(name.lower())
                normalized.append({"name": name, "is_active": True})
        elif isinstance(item, dict) and "name" in item:
            name = str(item["name"]).strip()
            if name.lower() not in seen:
                seen.add(name.lower())
                normalized.append({"name": name, "is_active": bool(item.get("is_active", True))})
    return normalized


@router.get("/areas")
def get_service_areas(
    include_archived: bool = True,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List service areas with active/archived status and customer counts."""
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).first()
    if not settings:
        raise HTTPException(status_code=404, detail="Business settings not found")

    areas = _normalize_areas_list(settings.service_areas)
    if not include_archived:
        areas = [a for a in areas if a["is_active"]]

    # Enrich with customer counts
    enriched = []
    for a in areas:
        count = db.query(Customer).filter(func.lower(Customer.area) == a["name"].lower()).count()
        enriched.append({
            "name": a["name"],
            "is_active": a["is_active"],
            "customer_count": count,
        })
    return enriched


@router.post("/areas")
def add_service_area(
    payload: AreaCreatePayload,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Add a new active service area."""
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).with_for_update().first()
    if not settings:
        raise HTTPException(status_code=404, detail="Business settings not found")

    areas = _normalize_areas_list(settings.service_areas)
    name_clean = payload.name.strip()
    for a in areas:
        if a["name"].lower() == name_clean.lower():
            if not a["is_active"]:
                # Re-activate previously archived area
                a["is_active"] = True
                settings.service_areas = areas
                db.commit()
                return {"message": f"Area '{name_clean}' re-activated successfully", "area": a}
            raise HTTPException(status_code=409, detail=f"Service area '{name_clean}' already exists")

    new_area = {"name": name_clean, "is_active": True}
    areas.append(new_area)
    settings.service_areas = areas
    db.commit()
    return {"message": f"Area '{name_clean}' added successfully", "area": new_area}


@router.put("/areas/rename")
def rename_service_area(
    payload: AreaRenamePayload,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Rename a service area and atomically update all associated customer records."""
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).with_for_update().first()
    if not settings:
        raise HTTPException(status_code=404, detail="Business settings not found")

    old_name = payload.old_name.strip()
    new_name = payload.new_name.strip()

    if old_name.lower() == new_name.lower():
        return {"message": "Area names are identical", "updated_customers": 0}

    areas = _normalize_areas_list(settings.service_areas)
    found = False
    for a in areas:
        if a["name"].lower() == new_name.lower() and a["name"].lower() != old_name.lower():
            raise HTTPException(status_code=409, detail=f"Target service area '{new_name}' already exists")

    for a in areas:
        if a["name"].lower() == old_name.lower():
            a["name"] = new_name
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Service area '{old_name}' not found")

    # Update matching customer records atomically
    updated_count = (
        db.query(Customer)
        .filter(func.lower(Customer.area) == old_name.lower())
        .update({"area": new_name}, synchronize_session="fetch")
    )

    settings.service_areas = areas
    db.commit()
    return {
        "message": f"Area renamed from '{old_name}' to '{new_name}' successfully",
        "updated_customers": updated_count,
    }


@router.put("/areas/archive")
def archive_service_area(
    payload: AreaArchivePayload,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Archive or un-archive a service area.

    Archived areas cannot be chosen for new customers, but historical associations remain preserved.
    """
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).with_for_update().first()
    if not settings:
        raise HTTPException(status_code=404, detail="Business settings not found")

    target_name = payload.name.strip()
    areas = _normalize_areas_list(settings.service_areas)
    found = False
    for a in areas:
        if a["name"].lower() == target_name.lower():
            a["is_active"] = payload.is_active
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Service area '{target_name}' not found")

    # If attempting to deactivate, ensure at least one active area remains
    active_count = sum(1 for a in areas if a["is_active"])
    if active_count == 0:
        raise HTTPException(status_code=400, detail="Cannot archive all service areas. At least one active area must remain.")

    settings.service_areas = areas
    db.commit()
    status_str = "activated" if payload.is_active else "archived"
    return {"message": f"Area '{target_name}' {status_str} successfully"}


@router.delete("/areas/{name}")
def delete_service_area(
    name: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Delete a service area IF AND ONLY IF no customers are associated with it."""
    settings = db.query(BusinessSettings).filter(BusinessSettings.id == 1).with_for_update().first()
    if not settings:
        raise HTTPException(status_code=404, detail="Business settings not found")

    target_name = name.strip()
    # Check customer references
    cust_count = db.query(Customer).filter(func.lower(Customer.area) == target_name.lower()).count()
    if cust_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete area '{target_name}' because {cust_count} customer(s) are associated with it. Please archive it instead.",
        )

    areas = _normalize_areas_list(settings.service_areas)
    new_areas = [a for a in areas if a["name"].lower() != target_name.lower()]
    if len(new_areas) == len(areas):
        raise HTTPException(status_code=404, detail=f"Service area '{target_name}' not found")

    if len(new_areas) == 0:
        raise HTTPException(status_code=400, detail="Cannot delete the only service area.")

    settings.service_areas = new_areas
    db.commit()
    return {"message": f"Service area '{target_name}' deleted successfully"}


@router.post("/bulk-rate-update", response_model=BulkRateUpdateResponse)
def bulk_update_subscription_rates(
    payload: BulkRateUpdatePayload,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Bulk update the monthly subscription rate for ALL active customers.

    Requires explicit confirmation flag. Inactive customers and historical invoices are untouched.
    """
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation (confirm=True) is required to execute a bulk rate update.",
        )

    # Perform atomic update on all active customers
    updated_count = (
        db.query(Customer)
        .filter(Customer.is_active == True)
        .update({"monthly_amount": payload.new_monthly_amount}, synchronize_session="fetch")
    )
    db.commit()

    return BulkRateUpdateResponse(
        affected_customers_count=updated_count,
        new_monthly_amount=f"{payload.new_monthly_amount:.2f}",
        message=f"Successfully updated subscription rate to ₹{payload.new_monthly_amount:.2f} for {updated_count} active customer(s).",
    )
