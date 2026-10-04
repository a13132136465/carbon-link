"""add self-custody wallet and on-chain identifiers"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004_project_documents"
branch_labels = None
depends_on = None

def upgrade() -> None:
    bind = op.get_bind()
    def columns(table: str) -> set[str]:
        return {column["name"] for column in sa.inspect(bind).get_columns(table)}
    def add(table: str, column: sa.Column) -> None:
        if column.name not in columns(table):
            op.add_column(table, column)
    def unique(table: str, name: str, names: list[str]) -> None:
        existing = {tuple(item["column_names"]) for item in sa.inspect(bind).get_unique_constraints(table)}
        if tuple(names) not in existing:
            op.create_unique_constraint(name, table, names)

    add("users", sa.Column("wallet_address", sa.String(42)))
    add("users", sa.Column("wallet_nonce", sa.String(64)))
    add("users", sa.Column("wallet_nonce_expires_at", sa.DateTime(timezone=True)))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "ix_users_wallet_address" not in indexes:
        op.create_index("ix_users_wallet_address", "users", ["wallet_address"], unique=True)
    add("projects", sa.Column("chain_token_id", sa.Integer()))
    unique("projects", "uq_projects_chain_token_id", ["chain_token_id"])
    add("credit_batches", sa.Column("chain_batch_id", sa.Integer()))
    unique("credit_batches", "uq_credit_batches_chain_batch_id", ["chain_batch_id"])
    add("retirements", sa.Column("transaction_hash", sa.String(80)))
    add("retirements", sa.Column("chain_retirement_id", sa.Integer()))
    unique("retirements", "uq_retirements_transaction_hash", ["transaction_hash"])
    unique("retirements", "uq_retirements_chain_id", ["chain_retirement_id"])

def downgrade() -> None:
    op.drop_constraint("uq_retirements_chain_id", "retirements", type_="unique")
    op.drop_constraint("uq_retirements_transaction_hash", "retirements", type_="unique")
    op.drop_column("retirements", "chain_retirement_id")
    op.drop_column("retirements", "transaction_hash")
    op.drop_constraint("uq_credit_batches_chain_batch_id", "credit_batches", type_="unique")
    op.drop_column("credit_batches", "chain_batch_id")
    op.drop_constraint("uq_projects_chain_token_id", "projects", type_="unique")
    op.drop_column("projects", "chain_token_id")
    op.drop_index("ix_users_wallet_address", table_name="users")
    op.drop_column("users", "wallet_nonce_expires_at")
    op.drop_column("users", "wallet_nonce")
    op.drop_column("users", "wallet_address")
