"""Add business_settings table for configurable business setup

Revision ID: 0002_business_settings
Revises: 0001_initial_admin_users
Create Date: 2026-11-16 08:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_business_settings'
down_revision: Union[str, None] = '0001_initial_admin_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'business_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('business_name', sa.String(length=255), nullable=False),
        sa.Column('contact_number', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('service_areas', sa.JSON(), nullable=False),
        sa.Column('currency_code', sa.String(length=3), nullable=False, server_default='INR'),
        sa.Column('timezone', sa.String(length=100), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('default_monthly_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='300.00'),
        sa.Column('billing_day', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('grace_period_days', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('late_payment_policy', sa.String(length=50), nullable=True, server_default='none'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name='business_settings_pkey'),
        sa.CheckConstraint('id = 1', name='single_business_setting_row'),
        sa.CheckConstraint('billing_day >= 1 AND billing_day <= 28', name='valid_billing_day'),
        sa.CheckConstraint('grace_period_days >= 0 AND grace_period_days <= 30', name='valid_grace_period_days'),
        sa.CheckConstraint('default_monthly_amount > 0', name='positive_default_monthly_amount'),
    )


def downgrade() -> None:
    op.drop_table('business_settings')
