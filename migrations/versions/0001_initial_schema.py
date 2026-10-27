"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-27 14:07:16.673654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from artemis.audit.models import install_triggers


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('audit_checkpoints',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.Column('batch_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('signature', sa.String(), nullable=False),
    sa.Column('public_key', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_events',
    sa.Column('seq', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('case_id', sa.String(), nullable=True),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('payload_json', sa.Text(), nullable=False),
    sa.Column('prev_hash', sa.String(length=64), nullable=False),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('seq')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_case_id'), ['case_id'], unique=False)

    for table in ('audit_events', 'audit_checkpoints'):  # the ledger is append-only: UPDATE/DELETE raise
        install_triggers(op.get_bind(), table)

    op.create_table('customers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('legal_name', sa.String(), nullable=False),
    sa.Column('gstin', sa.String(), nullable=False),
    sa.Column('pan', sa.String(), nullable=False),
    sa.Column('tan', sa.String(), nullable=False),
    sa.Column('contact_domain', sa.String(), nullable=False),
    sa.Column('tds_applicable', sa.Boolean(), nullable=False),
    sa.Column('tds_rate_bp', sa.Integer(), nullable=False),
    sa.Column('tds_category', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reviewers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('approval_limit_paise', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tax_credits',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('deductor_name', sa.String(), nullable=False),
    sa.Column('deductor_tan', sa.String(), nullable=False),
    sa.Column('our_pan', sa.String(), nullable=False),
    sa.Column('quarter', sa.Integer(), nullable=False),
    sa.Column('amount_credited', sa.Integer(), nullable=False),
    sa.Column('tds_section_ref', sa.String(), nullable=False),
    sa.Column('transaction_date', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('bank_receipts',
    sa.Column('utr', sa.String(), nullable=False),
    sa.Column('value_date', sa.String(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('payer_name_raw', sa.String(), nullable=False),
    sa.Column('narration', sa.String(), nullable=False),
    sa.Column('bank_charges', sa.Integer(), nullable=False),
    sa.Column('resolved_customer_id', sa.String(), nullable=True),
    sa.Column('resolution_score', sa.Integer(), nullable=True),
    sa.Column('case_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['resolved_customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('utr')
    )
    op.create_table('cases',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('utr', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=True),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('evidence_status', sa.String(), nullable=True),
    sa.Column('variance_paise', sa.Integer(), nullable=True),
    sa.Column('unexplained_paise', sa.Integer(), nullable=True),
    sa.Column('duplicate', sa.Boolean(), nullable=False),
    sa.Column('merged_into', sa.String(), nullable=True),
    sa.Column('assigned_reviewer', sa.String(), nullable=True),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('updated_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('customer_aliases',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('alias', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('confidence', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('invoices',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('invoice_date', sa.String(), nullable=False),
    sa.Column('due_date', sa.String(), nullable=False),
    sa.Column('taxable_value', sa.Integer(), nullable=False),
    sa.Column('gst_amount', sa.Integer(), nullable=False),
    sa.Column('gross_amount', sa.Integer(), nullable=False),
    sa.Column('po_ref', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('remittance_emails',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('received_at', sa.String(), nullable=False),
    sa.Column('from_addr', sa.String(), nullable=False),
    sa.Column('subject', sa.String(), nullable=False),
    sa.Column('body_text', sa.Text(), nullable=False),
    sa.Column('parsed', sa.JSON(), nullable=True),
    sa.Column('raw_path', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('adjustments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('amount_paise', sa.Integer(), nullable=False),
    sa.Column('evidence_ids', sa.JSON(), nullable=False),
    sa.Column('validated', sa.Boolean(), nullable=False),
    sa.Column('validated_by_rule', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('allocations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('invoice_id', sa.String(), nullable=False),
    sa.Column('amount_paise', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('credit_notes',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('customer_id', sa.String(), nullable=False),
    sa.Column('invoice_id', sa.String(), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('issued_on', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reviews',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('reviewer_id', sa.String(), nullable=False),
    sa.Column('decision', sa.String(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=False),
    sa.Column('policy_id', sa.String(), nullable=False),
    sa.Column('decided_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
    sa.ForeignKeyConstraint(['reviewer_id'], ['reviewers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('reviews')
    op.drop_table('credit_notes')
    op.drop_table('allocations')
    op.drop_table('adjustments')
    op.drop_table('remittance_emails')
    op.drop_table('invoices')
    op.drop_table('customer_aliases')
    op.drop_table('cases')
    op.drop_table('bank_receipts')
    op.drop_table('tax_credits')
    op.drop_table('reviewers')
    op.drop_table('customers')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_case_id'))

    op.drop_table('audit_events')
    op.drop_table('audit_checkpoints')
    if op.get_bind().dialect.name == 'postgresql':  # dropping a table drops its trigger, not the function behind it
        for table in ('audit_events', 'audit_checkpoints'):
            op.execute(f'DROP FUNCTION IF EXISTS {table}_append_only()')
