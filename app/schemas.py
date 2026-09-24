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

class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    project_type: str = Field(min_length=2, max_length=80)
    region: str = Field(min_length=2, max_length=120)
    methodology: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=5000)
    estimated_tonnes: Decimal = Field(gt=0, max_digits=20, decimal_places=4)

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

class DashboardOut(BaseModel):
    total_issued: Decimal
    total_retired: Decimal
    open_market_quantity: Decimal
    trade_volume: Decimal
    project_count: int

class BlockchainConfigOut(BaseModel):
    enabled: bool
    configured: bool
    network: str
    chain_id: int
    rpc_url: str | None
    confirmations: int
    project_contract_address: str | None
    credit_contract_address: str | None
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
