from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from ..models import AdminUser, BusinessSettings
from ..schemas import (
    BusinessSettingsCreate,
    BusinessSettingsUpdate,
    BusinessSettingsResponse,
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
