from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models import ListingStatus, ProjectStatus, Role

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserOut(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    role: Role
    is_active: bool
    created_at: datetime
    wallet_address: str | None

class WalletChallengeIn(BaseModel):
    address: str = Field(min_length=42, max_length=42)

class WalletChallengeOut(BaseModel):
    address: str
    message: str
    expires_at: datetime

class WalletLinkIn(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    signature: str = Field(min_length=130, max_length=132)

class ChainConfigOut(BaseModel):
    enabled: bool
    network: str
    chain_id: int
    confirmations: int
    rpc_url: str | None
    credit_contract_address: str | None
    marketplace_contract_address: str | None
    usdc_contract_address: str | None

class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    project_type: str = Field(min_length=2, max_length=80)
    region: str = Field(min_length=2, max_length=120)
    methodology: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=5000)
    estimated_tonnes: Decimal = Field(gt=0, max_digits=20, decimal_places=4)

class ProjectUpdate(ProjectIn):
    pass

class ProjectOut(ORMModel):
    id: str
    owner_id: str
    name: str
    project_type: str
    region: str
    methodology: str
    description: str
    estimated_tonnes: Decimal
    status: ProjectStatus
    review_note: str | None
    created_at: datetime
    chain_token_id: int | None

class ProjectDocumentOut(ORMModel):
    id: str
    project_id: str
    category: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime

class ApplicationReadinessOut(BaseModel):
    ready: bool
    completed_categories: list[str]
    missing_categories: list[str]
    completion_percent: int

class AgentTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)

class AgentDraft(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    project_type: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=120)
    methodology: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    estimated_tonnes: str | None = Field(default=None, max_length=40)

class AgentMessageIn(BaseModel):
    project_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    history: list[AgentTurn] = Field(default_factory=list, max_length=30)
    draft: AgentDraft = Field(default_factory=AgentDraft)

class AgentMessageOut(BaseModel):
    draft: AgentDraft | None = None
    missing_fields: list[str] = Field(default_factory=list)
    model_available: bool = False
    reply: str
    stage: str
    suggested_actions: list[str]
    readiness: ApplicationReadinessOut | None = None

class ReviewIn(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=2000)

class IssueIn(BaseModel):
    project_id: str
    vintage: int = Field(ge=1990, le=2100)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)

class BatchOut(ORMModel):
    id: str
    project_id: str
    vintage: int
    methodology: str
    serial_prefix: str
    total_issued: Decimal
    total_retired: Decimal
    issued_at: datetime
    chain_batch_id: int | None

class HoldingOut(ORMModel):
    batch_id: str
    quantity: Decimal
    locked_quantity: Decimal

class ListingIn(BaseModel):
    batch_id: str
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    unit_price: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    currency: str = Field(default="CNY", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()

class ListingOut(ORMModel):
    id: str
    seller_id: str
    batch_id: str
    quantity: Decimal
    remaining_quantity: Decimal
    unit_price: Decimal
    currency: str
    status: ListingStatus
    created_at: datetime

class BuyIn(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)

class TradeOut(ORMModel):
    id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    batch_id: str
    quantity: Decimal
    unit_price: Decimal
    total_amount: Decimal
    currency: str
    traded_at: datetime

class LedgerEntryOut(ORMModel):
    id: str
    batch_id: str
    kind: str
    quantity_delta: Decimal
    balance_after: Decimal
    reference_type: str
    reference_id: str
    created_at: datetime

class RetireIn(BaseModel):
    batch_id: str
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    beneficiary: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=2, max_length=2000)

class RetirementOut(ORMModel):
    id: str
    certificate_no: str
    user_id: str
    batch_id: str
    quantity: Decimal
    beneficiary: str
    reason: str
    retired_at: datetime
    transaction_hash: str | None
    chain_retirement_id: int | None

class RetirementConfirmIn(BaseModel):
    transaction_hash: str = Field(pattern="^0x[0-9a-fA-F]{64}$")
    batch_id: str
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    beneficiary: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=2, max_length=2000)

class AuditEventOut(ORMModel):
    id: str
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str
    detail: str
    created_at: datetime

class DashboardListingOut(BaseModel):
    id: str
    batch_id: str
    remaining_quantity: Decimal
    unit_price: Decimal
    created_at: datetime

class DashboardOut(BaseModel):
    total_issued: Decimal
    total_retired: Decimal
    open_market_quantity: Decimal
    trade_volume: Decimal
    project_count: int
    latest_market_listings: list[DashboardListingOut] = Field(default_factory=list)

class BlockchainConfigOut(BaseModel):
    enabled: bool
    configured: bool
    network: str
    chain_id: int
    rpc_url: str | None
    confirmations: int
    project_contract_address: str | None
    credit_contract_address: str | None
    marketplace_contract_address: str | None
    usdc_contract_address: str | None
    operator_address: str | None
    signing_mode: str

class ChainOperationOut(ORMModel):
    id: str
    operation_type: str
    resource_type: str
    resource_id: str
    chain_id: int
    contract_address: str
    payload: dict
    status: str
    attempts: int
    transaction_hash: str | None
    block_number: int | None
    error_message: str | None
    created_at: datetime

class UserAdminUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    is_active: bool | None = None

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class ForgotPasswordOut(BaseModel):
    message: str
    reset_token: str | None = None

class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)

class MessageOut(BaseModel):
    message: str
