"""Credential revocation and durable signer identity."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The legacy initial migration builds current Base.metadata on fresh installs.
    inspector = sa.inspect(op.get_bind())
    if "token_version" not in {c["name"] for c in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    if "signer_address" not in {c["name"] for c in inspector.get_columns("chain_operations")}:
        op.add_column("chain_operations", sa.Column("signer_address", sa.String(42), nullable=True))
    if "ix_chain_operations_signer_address" not in {i["name"] for i in inspector.get_indexes("chain_operations")}:
        op.create_index("ix_chain_operations_signer_address", "chain_operations", ["signer_address"])


def downgrade() -> None:
    op.drop_index("ix_chain_operations_signer_address", table_name="chain_operations")
    op.drop_column("chain_operations", "signer_address")
    op.drop_column("users", "token_version")
