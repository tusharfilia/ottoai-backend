"""introduce_contact_lead_appointment_tables

Revision ID: 4f2f2c1b9c3d
Revises: 8c79001578c0
Create Date: 2025-11-10 12:00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4f2f2c1b9c3d"
down_revision = "8c79001578c0"
branch_labels = None
depends_on = None

lead_status_enum = sa.Enum(
    "new",
    "qualified_booked",
    "qualified_unbooked",
    "qualified_service_not_offered",
    "nurturing",
    "closed_won",
    "closed_lost",
    name="lead_status",
)

lead_source_enum = sa.Enum(
    "unknown",
    "inbound_call",
    "inbound_web",
    "referral",
    "partner",
    "other",
    name="lead_source",
)

appointment_status_enum = sa.Enum(
    "scheduled",
    "confirmed",
    "completed",
    "cancelled",
    "no_show",
    name="appointment_status",
)

appointment_outcome_enum = sa.Enum(
    "pending",
    "won",
    "lost",
    "no_show",
    "rescheduled",
    name="appointment_outcome",
)


def upgrade():
    bind = op.get_bind()
    lead_status_enum.create(bind, checkfirst=True)
    lead_source_enum.create(bind, checkfirst=True)
    appointment_status_enum.create(bind, checkfirst=True)
    appointment_outcome_enum.create(bind, checkfirst=True)

    op.create_table(
        "contact_cards",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_phone", sa.String(), nullable=False),
        sa.Column("secondary_phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("property_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "primary_phone", name="uq_contact_cards_company_phone"),
    )
    op.create_index(
        "ix_contact_cards_company_primary",
        "contact_cards",
        ["company_id", "primary_phone"],
    )
    op.create_index(
        "ix_contact_cards_email",
        "contact_cards",
        ["company_id", "email"],
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("contact_card_id", sa.String(), sa.ForeignKey("contact_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", lead_status_enum, nullable=False, server_default="new"),
        sa.Column("source", lead_source_enum, nullable=False, server_default="unknown"),
        sa.Column("campaign", sa.String(), nullable=True),
        sa.Column("pipeline_stage", sa.String(), nullable=True),
        sa.Column("priority", sa.String(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(), nullable=True),
        sa.Column("last_qualified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_leads_company_status_contact",
        "leads",
        ["company_id", "status", "contact_card_id"],
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("lead_id", sa.String(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_card_id", sa.String(), sa.ForeignKey("contact_cards.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_rep_id", sa.String(), sa.ForeignKey("sales_reps.user_id", ondelete="SET NULL"), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(), nullable=True),
        sa.Column("status", appointment_status_enum, nullable=False, server_default="scheduled"),
        sa.Column("outcome", appointment_outcome_enum, nullable=False, server_default="pending"),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("service_type", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_appointments_company_lead_window",
        "appointments",
        ["company_id", "lead_id", "scheduled_start", "assigned_rep_id"],
    )

    # Calls → Contact/Lead links
    op.add_column("calls", sa.Column("contact_card_id", sa.String(), nullable=True))
    op.add_column("calls", sa.Column("lead_id", sa.String(), nullable=True))
    op.create_index("ix_calls_contact_card_id", "calls", ["contact_card_id"])
    op.create_index("ix_calls_lead_id", "calls", ["lead_id"])
    op.create_foreign_key(
        "fk_calls_contact_card",
        "calls",
        "contact_cards",
        ["contact_card_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_calls_lead",
        "calls",
        "leads",
        ["lead_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_calls_lead", "calls", type_="foreignkey")
    op.drop_constraint("fk_calls_contact_card", "calls", type_="foreignkey")
    op.drop_index("ix_calls_lead_id", table_name="calls")
    op.drop_index("ix_calls_contact_card_id", table_name="calls")
    op.drop_column("calls", "lead_id")
    op.drop_column("calls", "contact_card_id")

    op.drop_index("ix_appointments_company_lead_window", table_name="appointments")
    op.drop_table("appointments")

    op.drop_index("ix_leads_company_status_contact", table_name="leads")
    op.drop_table("leads")

    op.drop_index("ix_contact_cards_email", table_name="contact_cards")
    op.drop_index("ix_contact_cards_company_primary", table_name="contact_cards")
    op.drop_table("contact_cards")

    bind = op.get_bind()
    appointment_outcome_enum.drop(bind, checkfirst=True)
    appointment_status_enum.drop(bind, checkfirst=True)
    lead_source_enum.drop(bind, checkfirst=True)
    lead_status_enum.drop(bind, checkfirst=True)

