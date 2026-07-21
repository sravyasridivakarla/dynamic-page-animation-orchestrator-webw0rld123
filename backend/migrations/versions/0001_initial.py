"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE workflowstate AS ENUM ('draft', 'approved', 'rejected', 'pending_deletion')"
    )

    op.create_table(
        "page_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", sa.String(255), nullable=False),
        sa.Column(
            "workflow_state",
            postgresql.ENUM(
                "draft", "approved", "rejected", "pending_deletion",
                name="workflowstate",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_page_configs_product_id", "page_configs", ["product_id"])

    op.create_table(
        "scroll_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("page_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "visual_representations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("page_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "sourcing_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("page_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "provenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("page_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("inputs", postgresql.JSON(), nullable=False),
        sa.Column("sources", postgresql.JSON(), nullable=False),
        sa.Column("reasoning_trace", sa.Text(), nullable=False),
        sa.Column("diff_presented", postgresql.JSON(), nullable=False),
        sa.Column("human_decision", sa.String(50), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provenance_records")
    op.drop_table("sourcing_timeline_events")
    op.drop_table("visual_representations")
    op.drop_table("scroll_sections")
    op.drop_table("page_configs")
    op.execute("DROP TYPE workflowstate")
