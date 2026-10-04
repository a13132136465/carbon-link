"""project application documents

Revision ID: 0004_project_documents
Revises: 0003_accounts_and_chain_worker
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_project_documents"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():

    if sa.inspect(op.get_bind()).has_table("project_documents"):
        return
    op.create_table(
        "project_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("storage_name", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_documents_project_id", "project_documents", ["project_id"])
    op.create_index("ix_project_documents_uploaded_by", "project_documents", ["uploaded_by"])
    op.create_index("ix_project_document_project_category", "project_documents", ["project_id", "category"])


def downgrade():
    if sa.inspect(op.get_bind()).has_table("project_documents"):
        op.drop_table("project_documents")
