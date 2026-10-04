import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

def now() -> datetime:
    return datetime.now(timezone.utc)

def uid() -> str:
    return str(uuid.uuid4())

class Role(str, enum.Enum):
    ADMIN = "admin"
    VERIFIER = "verifier"
    MEMBER = "member"

class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ListingStatus(str, enum.Enum):
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"

class LedgerKind(str, enum.Enum):
    ISSUE = "issue"
    TRADE_IN = "trade_in"
    TRADE_OUT = "trade_out"
    RETIRE = "retire"

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.MEMBER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_address: Mapped[str | None] = mapped_column(String(42), unique=True, index=True)
    wallet_nonce: Mapped[str | None] = mapped_column(String(64))
    wallet_nonce_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(120))
    methodology: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_tonnes: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    chain_token_id: Mapped[int | None] = mapped_column(Integer, unique=True)

class ProjectDocument(Base):
    __tablename__ = "project_documents"
    __table_args__ = (Index("ix_project_document_project_category", "project_id", "category"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    original_name: Mapped[str] = mapped_column(String(255))
    storage_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class CreditBatch(Base):
    __tablename__ = "credit_batches"
    __table_args__ = (UniqueConstraint("project_id", "vintage", name="uq_project_vintage"), CheckConstraint("total_issued > 0", name="ck_batch_issued_positive"), CheckConstraint("total_retired >= 0 AND total_retired <= total_issued", name="ck_batch_retired_valid"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    vintage: Mapped[int] = mapped_column(Integer)
    methodology: Mapped[str] = mapped_column(String(120))
    serial_prefix: Mapped[str] = mapped_column(String(80), unique=True)
    total_issued: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    total_retired: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    issued_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    chain_batch_id: Mapped[int | None] = mapped_column(Integer, unique=True)

class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("user_id", "batch_id", name="uq_user_batch"), CheckConstraint("quantity >= 0", name="ck_holding_quantity_nonnegative"), CheckConstraint("locked_quantity >= 0 AND locked_quantity <= quantity", name="ck_holding_locked_valid"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("credit_batches.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    locked_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (Index("ix_ledger_user_created", "user_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("credit_batches.id"), index=True)
    kind: Mapped[LedgerKind] = mapped_column(Enum(LedgerKind))
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    reference_type: Mapped[str] = mapped_column(String(30))
    reference_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("credit_batches.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.OPEN, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

class OperationRequest(Base):
    __tablename__ = "operation_requests"
    __table_args__ = (UniqueConstraint("user_id", "endpoint", "key", name="uq_operation_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    listing_id: Mapped[str] = mapped_column(ForeignKey("listings.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    seller_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("credit_batches.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(3))
    traded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Retirement(Base):
    __tablename__ = "retirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    certificate_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("credit_batches.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    beneficiary: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    retired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    transaction_hash: Mapped[str | None] = mapped_column(String(80), unique=True)
    chain_retirement_id: Mapped[int | None] = mapped_column(Integer, unique=True)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ChainOperation(Base):
    __tablename__ = "chain_operations"
    __table_args__ = (UniqueConstraint("operation_type", "resource_id", name="uq_chain_operation_resource"), Index("ix_chain_operation_status_created", "status", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    operation_type: Mapped[str] = mapped_column(String(40))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    chain_id: Mapped[int] = mapped_column(Integer)
    contract_address: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    transaction_hash: Mapped[str | None] = mapped_column(String(80), unique=True)
    raw_transaction: Mapped[str | None] = mapped_column(Text)
    signer_address: Mapped[str | None] = mapped_column(String(42), index=True)
    nonce: Mapped[int | None] = mapped_column(Integer)
    block_number: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
