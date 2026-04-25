"""Initial schema — all 14 tables

Revision ID: 001
Revises:
Create Date: 2026-04-25

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
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("mobile", sa.String(15), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("role IN ('ca', 'smb')", name="users_role_check"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mobile"),
    )

    # 2. ca_profiles
    op.create_table(
        "ca_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("icai_number", sa.String(20), nullable=True),
        sa.Column("firm_name", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("plan", sa.String(20), server_default="starter", nullable=False),
        sa.Column("plan_client_limit", sa.Integer(), server_default="10", nullable=False),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("razorpay_subscription_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("plan IN ('starter','growth','pro','firm')", name="ca_profiles_plan_check"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("icai_number"),
    )

    # 3. smb_profiles
    op.create_table(
        "smb_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("company_type", sa.String(50), nullable=True),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("pan", sa.String(10), nullable=True),
        sa.Column("turnover_range", sa.String(20), nullable=True),
        sa.Column("employee_count_range", sa.String(20), nullable=True),
        sa.Column("sectors", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("states", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("gst_registered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("gst_composition", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("has_factory", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("import_export", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_listed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("standalone_plan", sa.String(20), server_default="free", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. ca_client_links
    op.create_table(
        "ca_client_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ca_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','active','removed')", name="ca_client_links_status_check"),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ca_id", "client_id", name="uq_ca_client_links"),
    )

    # 5. compliance_items (master catalogue)
    op.create_table(
        "compliance_items",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("compliance_type", sa.String(50), nullable=False),
        sa.Column("authority", sa.String(100), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=True),
        sa.Column("due_day", sa.Integer(), nullable=True),
        sa.Column("due_day_rule", sa.String(255), nullable=True),
        sa.Column("applicable_conditions", postgresql.JSONB(), nullable=True),
        sa.Column("penalty_per_day", sa.Integer(), nullable=True),
        sa.Column("max_penalty", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_checklist", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("ca_action_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("client_action_required", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. client_compliance_items
    op.create_table(
        "client_compliance_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ca_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("compliance_item_id", sa.String(100), nullable=False),
        sa.Column("financial_year", sa.String(10), nullable=False),
        sa.Column("period", sa.String(20), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','waiting_on_client','filed','not_applicable','overdue')",
            name="client_compliance_items_status_check",
        ),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_profiles.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compliance_item_id"], ["compliance_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 7. tasks
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ca_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("compliance_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.String(10), nullable=True),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("assigned_to IN ('ca','client')", name="tasks_assigned_to_check"),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','waiting_on_client','done','cancelled')",
            name="tasks_status_check",
        ),
        sa.CheckConstraint("created_by IN ('ca','client','system')", name="tasks_created_by_check"),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compliance_item_id"], ["client_compliance_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 8. documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ca_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("compliance_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("r2_key", sa.String(500), nullable=False),
        sa.Column("uploaded_by", sa.String(10), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=True),
        sa.Column("financial_year", sa.String(10), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("uploaded_by IN ('ca','client')", name="documents_uploaded_by_check"),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_profiles.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["compliance_item_id"], ["client_compliance_items.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("r2_key"),
    )

    # 9. messages + index
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ca_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attached_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("linked_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("sender_role IN ('ca','client')", name="messages_sender_role_check"),
        sa.ForeignKeyConstraint(["attached_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_profiles.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"]),
        sa.ForeignKeyConstraint(["linked_task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_messages_thread", "messages", ["ca_id", "client_id"])

    # 10. invoices
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ca_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("line_items", postgresql.JSONB(), nullable=False),
        sa.Column("subtotal", sa.Integer(), nullable=False),
        sa.Column("gst_rate", sa.Integer(), server_default="18", nullable=False),
        sa.Column("gst_amount", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("razorpay_payment_link_id", sa.String(100), nullable=True),
        sa.Column("razorpay_payment_link_url", sa.String(500), nullable=True),
        sa.Column("pdf_r2_key", sa.String(500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft','sent','paid','overdue','cancelled')", name="invoices_status_check"
        ),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_profiles.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
    )

    # 11. health_scores + index
    op.create_table(
        "health_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("score BETWEEN 0 AND 100", name="health_scores_score_check"),
        sa.ForeignKeyConstraint(["client_id"], ["smb_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_health_scores_client", "health_scores", ["client_id"])

    # 12. payments (stub — populated by Razorpay webhooks only)
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(100), nullable=True),
        sa.Column("razorpay_order_id", sa.String(100), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("method", sa.String(30), nullable=True),
        sa.Column("webhook_payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('captured','failed','refunded')", name="payments_status_check"
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("razorpay_payment_id"),
    )

    # 13. regulations (stub — populated by regulation_scraper_job)
    op.create_table(
        "regulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("compliance_type", sa.String(50), nullable=True),
        sa.Column("sectors_affected", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("states_affected", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("company_types_affected", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("action_required_by", sa.Date(), nullable=True),
        sa.Column("plain_english_summary", sa.Text(), nullable=True),
        sa.Column("ca_summary", sa.Text(), nullable=True),
        sa.Column("is_classified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 14. notifications (stub — populated by notification_service)
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "notification_type IN ('whatsapp','push','email','sms')",
            name="notifications_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending','sent','delivered','failed','read')",
            name="notifications_status_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("regulations")
    op.drop_table("payments")
    op.drop_index("idx_health_scores_client", table_name="health_scores")
    op.drop_table("health_scores")
    op.drop_table("invoices")
    op.drop_index("idx_messages_thread", table_name="messages")
    op.drop_table("messages")
    op.drop_table("documents")
    op.drop_table("tasks")
    op.drop_table("client_compliance_items")
    op.drop_table("compliance_items")
    op.drop_table("ca_client_links")
    op.drop_table("smb_profiles")
    op.drop_table("ca_profiles")
    op.drop_table("users")
