"""add_property_intelligence_fields

Revision ID: 5a3b4c5d6e7f
Revises: 4f2f2c1b9c3d
Create Date: 2025-11-11 00:00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "5a3b4c5d6e7f"
down_revision = "4f2f2c1b9c3d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "contact_cards",
        sa.Column("property_snapshot_raw", sa.Text(), nullable=True),
    )
    op.add_column(
        "contact_cards",
        sa.Column("property_snapshot_updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("contact_cards", "property_snapshot_updated_at")
    op.drop_column("contact_cards", "property_snapshot_raw")

