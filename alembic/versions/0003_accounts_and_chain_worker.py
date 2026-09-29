"""account recovery and durable chain broadcasts"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
        op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])
    chain_columns = {column["name"] for column in sa.inspect(bind).get_columns("chain_operations")}
    if "raw_transaction" not in chain_columns:
        op.add_column("chain_operations", sa.Column("raw_transaction", sa.Text()))
    if "nonce" not in chain_columns:
        op.add_column("chain_operations", sa.Column("nonce", sa.Integer()))
    if "next_attempt_at" not in chain_columns:
        op.add_column("chain_operations", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("chain_operations")}
    if "ix_chain_operations_next_attempt_at" not in indexes:
        op.create_index("ix_chain_operations_next_attempt_at", "chain_operations", ["next_attempt_at"])

def downgrade() -> None:
    op.drop_index("ix_chain_operations_next_attempt_at", table_name="chain_operations")
    op.drop_column("chain_operations", "next_attempt_at")
    op.drop_column("chain_operations", "nonce")
    op.drop_column("chain_operations", "raw_transaction")
    op.drop_table("password_reset_tokens")
