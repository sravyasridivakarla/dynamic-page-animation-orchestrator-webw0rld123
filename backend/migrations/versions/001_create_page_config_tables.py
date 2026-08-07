"""Create page config tables.

Revision ID: 001
Revises:
Create Date: 2026-08-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    layouttype_enum = postgresql.ENUM(
        "STANDARD", "HERO", "MINIMAL", name="layouttype", create_type=True
    )
    layouttype_enum.create(op.get_bind(), checkfirst=True)

    visibilitystatus_enum = postgresql.ENUM(
        "DRAFT", "PUBLISHED", "ARCHIVED", name="visibilitystatus", create_type=True
    )
    visibilitystatus_enum.create(op.get_bind(), checkfirst=True)

    visualrepresentationtype_enum = postgresql.ENUM(
        "IMAGE", "VIDEO", "CAROUSEL", name="visualrepresentationtype", create_type=True
    )
    visualrepresentationtype_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "page_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", sa.String(255), nullable=False),
        sa.Column("page_title", sa.String(500), nullable=False),
        sa.Column("meta_description", sa.Text, nullable=False),
        sa.Column(
            "layout_type",
            postgresql.ENUM("STANDARD", "HERO", "MINIMAL", name="layouttype", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "visibility_status",
            postgresql.ENUM(
                "DRAFT", "PUBLISHED", "ARCHIVED", name="visibilitystatus", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
    )

    op.create_table(
        "scroll_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("page_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("heading", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("background_image_url", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "visual_representations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("page_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "IMAGE", "VIDEO", "CAROUSEL",
                name="visualrepresentationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("alt_text", sa.String(500), nullable=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "sourcing_timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("page_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("sourcing_timeline_events")
    op.drop_table("visual_representations")
    op.drop_table("scroll_sections")
    op.drop_table("page_configs")

    op.execute("DROP TYPE IF EXISTS visualrepresentationtype")
    op.execute("DROP TYPE IF EXISTS visibilitystatus")
    op.execute("DROP TYPE IF EXISTS layouttype")
