"""Employee permissions, audit trail and issued document versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002_corporate"
down_revision = "0001_baseline"


def upgrade():
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.execute("UPDATE users SET role = 'sales' WHERE role IS NULL OR role NOT IN ('admin', 'sales')")
    op.create_table("audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("estimate_id", UUID(as_uuid=True)),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_estimate_id", "audit_events", ["estimate_id"])
    op.create_table("document_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("estimate_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("actor_name", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("estimate_id", "version", "kind"),
    )
    op.create_index("ix_document_versions_estimate_id", "document_versions", ["estimate_id"])
    # API users cannot rewrite the audit trail or replace an issued document row.
    op.execute("""CREATE FUNCTION wallpanels_immutable_record() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'This record is immutable'; END; $$""")
    for table in ("audit_events", "document_versions"):
        op.execute(f"CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION wallpanels_immutable_record()")


def downgrade():
    raise RuntimeError("Corporate history is retained. Roll back code only or restore a backup into a separate database.")
