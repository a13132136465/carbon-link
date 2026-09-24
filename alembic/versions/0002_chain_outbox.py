"""add transactional blockchain outbox"""
from alembic import op
from app.database import Base
from app import models  # noqa: F401

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    Base.metadata.tables["chain_operations"].create(bind=op.get_bind(), checkfirst=True)

def downgrade() -> None:
    Base.metadata.tables["chain_operations"].drop(bind=op.get_bind(), checkfirst=True)
