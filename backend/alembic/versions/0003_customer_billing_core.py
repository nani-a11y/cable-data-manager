"""Add customer and billing core tables

Revision ID: 0003_customer_billing_core
Revises: 0002_business_settings
Create Date: 2026-11-16 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_customer_billing_core'
down_revision: Union[str, None] = '0002_business_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('display_id', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('box_number', sa.String(length=100), nullable=False),
        sa.Column('area', sa.String(length=100), nullable=False),
        sa.Column('monthly_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name='customers_pkey'),
        sa.CheckConstraint('monthly_amount > 0', name='positive_customer_monthly_amount'),
    )
    op.create_index('ix_customers_id', 'customers', ['id'], unique=False)
    op.create_index('ix_customers_display_id', 'customers', ['display_id'], unique=True)
    op.create_index('ix_customers_name', 'customers', ['name'], unique=False)
    op.create_index('ix_customers_phone', 'customers', ['phone'], unique=False)
    op.create_index('ix_customers_box_number', 'customers', ['box_number'], unique=False)
    op.create_index('ix_customers_area', 'customers', ['area'], unique=False)
    op.create_index('ix_customers_is_active', 'customers', ['is_active'], unique=False)
    op.create_index(
        'uq_customers_box_number_lower',
        'customers',
        [sa.text('lower(box_number)')],
        unique=True,
    )

    # 2. invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('billing_month', sa.String(length=7), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('issued_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_invoices_customer_id', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='invoices_pkey'),
        sa.UniqueConstraint('customer_id', 'billing_month', name='uq_invoice_customer_billing_month'),
        sa.CheckConstraint('amount > 0', name='positive_invoice_amount'),
        sa.CheckConstraint('paid_amount >= 0', name='non_negative_paid_amount'),
        sa.CheckConstraint('paid_amount <= amount', name='paid_amount_within_invoice_amount'),
        sa.CheckConstraint("status IN ('pending', 'partial', 'paid')", name='valid_invoice_status'),
        sa.CheckConstraint('length(billing_month) = 7', name='valid_billing_month_length'),
    )
    op.create_index('ix_invoices_id', 'invoices', ['id'], unique=False)
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], unique=True)
    op.create_index('ix_invoices_customer_id', 'invoices', ['customer_id'], unique=False)
    op.create_index('ix_invoices_billing_month', 'invoices', ['billing_month'], unique=False)
    op.create_index('ix_invoices_status', 'invoices', ['status'], unique=False)

    # 3. payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('receipt_number', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('payment_method', sa.String(length=20), server_default='cash', nullable=False),
        sa.Column('paid_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('is_reversed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('reversal_reason', sa.String(length=255), nullable=True),
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name='fk_payments_customer_id', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='payments_pkey'),
        sa.CheckConstraint('amount > 0', name='positive_payment_amount'),
        sa.CheckConstraint("payment_method IN ('cash', 'upi', 'other')", name='valid_payment_method'),
    )
    op.create_index('ix_payments_id', 'payments', ['id'], unique=False)
    op.create_index('ix_payments_receipt_number', 'payments', ['receipt_number'], unique=True)
    op.create_index('ix_payments_customer_id', 'payments', ['customer_id'], unique=False)
    op.create_index('ix_payments_paid_date', 'payments', ['paid_date'], unique=False)
    op.create_index('ix_payments_is_reversed', 'payments', ['is_reversed'], unique=False)

    # 4. payment_allocations table
    op.create_table(
        'payment_allocations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name='fk_allocations_payment_id', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name='fk_allocations_invoice_id', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='payment_allocations_pkey'),
        sa.CheckConstraint('allocated_amount > 0', name='positive_allocated_amount'),
    )
    op.create_index('ix_payment_allocations_id', 'payment_allocations', ['id'], unique=False)
    op.create_index('ix_payment_allocations_payment_id', 'payment_allocations', ['payment_id'], unique=False)
    op.create_index('ix_payment_allocations_invoice_id', 'payment_allocations', ['invoice_id'], unique=False)


def downgrade() -> None:
    op.drop_table('payment_allocations')
    op.drop_table('payments')
    op.drop_table('invoices')
    op.drop_table('customers')
