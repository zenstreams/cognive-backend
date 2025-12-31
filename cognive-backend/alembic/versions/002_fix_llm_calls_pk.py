"""Fix llm_calls primary key for TimescaleDB constraints.

Revision ID: 002_fix_llm_calls_pk
Revises: 001_initial_schema
Create Date: 2025-12-28
"""

from __future__ import annotations

from alembic import op

revision = "002_fix_llm_calls_pk"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOTE:
    # The composite PK (id, timestamp) is established in 001_initial_schema to allow
    # TimescaleDB hypertable conversion to succeed on fresh databases.
    #
    # This migration keeps only the additive "fast lookup by id" index.
    op.create_index("ix_llm_calls_id", "llm_calls", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_llm_calls_id", table_name="llm_calls")

