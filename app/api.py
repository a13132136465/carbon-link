from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.deps import current_user, require_roles
from app.models import ChainOperation, CreditBatch, Holding, LedgerKind, Listing, ListingStatus, Project, ProjectStatus, Retirement, Role, Trade, User
from app.schemas import BatchOut, BlockchainConfigOut, BuyIn, ChainOperationOut, DashboardOut, HoldingOut, IssueIn, ListingIn, ListingOut, LoginIn, ProjectIn, ProjectOut, RegisterIn, RetireIn, RetirementOut, ReviewIn, TokenOut, TradeOut, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.service import add_ledger, audit, fail, locked_holding, queue_chain_operation, reserve_operation

router = APIRouter(prefix="/api/v1")

@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), display_name=body.display_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); fail(409, "Email is already registered")
    db.refresh(user)
    audit(db, user.id, "user.registered", "user", user.id); db.commit()
    return user

@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        fail(401, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id, user.role.value), expires_in=settings.access_token_minutes * 60)

@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = Project(owner_id=user.id, **body.model_dump())
    db.add(project); db.flush(); audit(db, user.id, "project.created", "project", project.id); db.commit(); db.refresh(project)
    return project

@router.get("/projects", response_model=list[ProjectOut])
def projects(status_filter: ProjectStatus | None = Query(None, alias="status"), mine: bool = False, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Project).order_by(Project.created_at.desc()).offset(offset).limit(limit)
    if status_filter: query = query.where(Project.status == status_filter)
    if mine: query = query.where(Project.owner_id == user.id)
    return list(db.scalars(query))

@router.post("/projects/{project_id}/submit", response_model=ProjectOut)
def submit_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: fail(404, "Project not found")
    if project.owner_id != user.id: fail(403, "Only the owner can submit this project")
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED): fail(409, "Project cannot be submitted in its current state")
    project.status = ProjectStatus.PENDING; project.review_note = None
    audit(db, user.id, "project.submitted", "project", project.id); db.commit(); db.refresh(project)
    return project

@router.post("/projects/{project_id}/review", response_model=ProjectOut)
def review_project(project_id: str, body: ReviewIn, user: User = Depends(require_roles(Role.ADMIN, Role.VERIFIER)), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: fail(404, "Project not found")
    if project.status != ProjectStatus.PENDING: fail(409, "Only pending projects can be reviewed")
    project.status = ProjectStatus.APPROVED if body.approved else ProjectStatus.REJECTED
    project.review_note = body.note; project.reviewed_by = user.id; project.reviewed_at = datetime.now(timezone.utc)
    audit(db, user.id, "project.reviewed", "project", project.id, {"approved": body.approved})
    if body.approved:
        queue_chain_operation(db, "project.register", "project", project.id, settings.carbon_project_contract_address, {"project_id": project.id, "owner_id": project.owner_id, "name": project.name, "methodology": project.methodology, "region": project.region})
    db.commit(); db.refresh(project)
    return project

@router.post("/credits/issue", response_model=BatchOut, status_code=201)
def issue(body: IssueIn, idempotency_key: str = Header(alias="Idempotency-Key"), user: User = Depends(require_roles(Role.ADMIN, Role.VERIFIER)), db: Session = Depends(get_db)):
    reserve_operation(db, user.id, "credits.issue", idempotency_key)
    project = db.get(Project, body.project_id)
    if not project: fail(404, "Project not found")
    if project.status != ProjectStatus.APPROVED: fail(409, "Credits may only be issued for approved projects")
    batch = CreditBatch(project_id=project.id, vintage=body.vintage, methodology=project.methodology, serial_prefix=f"CL-{body.vintage}-{uuid4().hex[:10].upper()}", total_issued=body.quantity, issued_by=user.id)
    db.add(batch)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); fail(409, "A batch already exists for this project and vintage")
    holding = locked_holding(db, project.owner_id, batch.id, create=True); holding.quantity += body.quantity
    add_ledger(db, holding, LedgerKind.ISSUE, body.quantity, "batch", batch.id)
    queue_chain_operation(db, "credit.issue", "batch", batch.id, settings.carbon_credit_contract_address, {"batch_id": batch.id, "project_id": project.id, "vintage": body.vintage, "quantity": str(body.quantity), "serial_prefix": batch.serial_prefix})
    audit(db, user.id, "credits.issued", "batch", batch.id, {"quantity": str(body.quantity)}); db.commit(); db.refresh(batch)
    return batch

@router.get("/credits/batches", response_model=list[BatchOut])
def batches(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), _: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(CreditBatch).order_by(CreditBatch.issued_at.desc()).offset(offset).limit(limit)))

@router.get("/wallet/holdings", response_model=list[HoldingOut])
def holdings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Holding).where(Holding.user_id == user.id).order_by(Holding.batch_id)))

@router.post("/market/listings", response_model=ListingOut, status_code=201)
def create_listing(body: ListingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    holding = locked_holding(db, user.id, body.batch_id)
    if holding.quantity - holding.locked_quantity < body.quantity: fail(409, "Insufficient available credits")
    holding.locked_quantity += body.quantity
    listing = Listing(seller_id=user.id, batch_id=body.batch_id, quantity=body.quantity, remaining_quantity=body.quantity, unit_price=body.unit_price, currency=body.currency)
    db.add(listing); db.flush(); audit(db, user.id, "listing.created", "listing", listing.id); db.commit(); db.refresh(listing)
    return listing

@router.get("/market/listings", response_model=list[ListingOut])
def list_market(batch_id: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    query = select(Listing).where(Listing.status == ListingStatus.OPEN).order_by(Listing.unit_price, Listing.created_at).offset(offset).limit(limit)
    if batch_id: query = query.where(Listing.batch_id == batch_id)
    return list(db.scalars(query))

@router.post("/market/listings/{listing_id}/buy", response_model=TradeOut, status_code=201)
def buy(listing_id: str, body: BuyIn, idempotency_key: str = Header(alias="Idempotency-Key"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    reserve_operation(db, user.id, f"listing.buy:{listing_id}", idempotency_key)
    listing = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if not listing: fail(404, "Listing not found")
    if listing.status != ListingStatus.OPEN or listing.remaining_quantity < body.quantity: fail(409, "Requested quantity is unavailable")
    if listing.seller_id == user.id: fail(409, "Seller cannot buy their own listing")
    seller = locked_holding(db, listing.seller_id, listing.batch_id)
    buyer = locked_holding(db, user.id, listing.batch_id, create=True)
    if seller.quantity < body.quantity or seller.locked_quantity < body.quantity: fail(409, "Seller inventory is inconsistent")
    seller.quantity -= body.quantity; seller.locked_quantity -= body.quantity; buyer.quantity += body.quantity
    listing.remaining_quantity -= body.quantity
    if listing.remaining_quantity == 0: listing.status = ListingStatus.FILLED
    trade = Trade(listing_id=listing.id, buyer_id=user.id, seller_id=listing.seller_id, batch_id=listing.batch_id, quantity=body.quantity, unit_price=listing.unit_price, total_amount=body.quantity * listing.unit_price, currency=listing.currency)
    db.add(trade); db.flush()
    add_ledger(db, seller, LedgerKind.TRADE_OUT, -body.quantity, "trade", trade.id); add_ledger(db, buyer, LedgerKind.TRADE_IN, body.quantity, "trade", trade.id)
    audit(db, user.id, "trade.settled", "trade", trade.id); db.commit(); db.refresh(trade)
    return trade

@router.delete("/market/listings/{listing_id}", status_code=204)
def cancel_listing(listing_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    listing = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if not listing: fail(404, "Listing not found")
    if listing.seller_id != user.id and user.role != Role.ADMIN: fail(403, "Only the seller can cancel this listing")
    if listing.status != ListingStatus.OPEN: fail(409, "Listing is not open")
    holding = locked_holding(db, listing.seller_id, listing.batch_id); holding.locked_quantity -= listing.remaining_quantity; listing.status = ListingStatus.CANCELLED
    audit(db, user.id, "listing.cancelled", "listing", listing.id); db.commit()

@router.post("/retirements", response_model=RetirementOut, status_code=201)
def retire(body: RetireIn, idempotency_key: str = Header(alias="Idempotency-Key"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    reserve_operation(db, user.id, "credits.retire", idempotency_key)
    holding = locked_holding(db, user.id, body.batch_id)
    if holding.quantity - holding.locked_quantity < body.quantity: fail(409, "Insufficient available credits")
    batch = db.scalar(select(CreditBatch).where(CreditBatch.id == body.batch_id).with_for_update())
    holding.quantity -= body.quantity; batch.total_retired += body.quantity
    record = Retirement(certificate_no=f"CLR-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}", user_id=user.id, **body.model_dump())
    db.add(record); db.flush(); add_ledger(db, holding, LedgerKind.RETIRE, -body.quantity, "retirement", record.id)
    queue_chain_operation(db, "credit.retire", "retirement", record.id, settings.carbon_credit_contract_address, {"retirement_id": record.id, "batch_id": body.batch_id, "quantity": str(body.quantity), "beneficiary": body.beneficiary, "reason": body.reason})
    audit(db, user.id, "credits.retired", "retirement", record.id); db.commit(); db.refresh(record)
    return record

@router.get("/retirements/{certificate_no}", response_model=RetirementOut)
def certificate(certificate_no: str, db: Session = Depends(get_db)):
    record = db.scalar(select(Retirement).where(Retirement.certificate_no == certificate_no))
    if not record: fail(404, "Retirement certificate not found")
    return record

@router.get("/dashboard", response_model=DashboardOut)
def dashboard(_: User = Depends(current_user), db: Session = Depends(get_db)):
    scalar = lambda stmt: db.scalar(stmt) or Decimal("0")
    return DashboardOut(total_issued=scalar(select(func.sum(CreditBatch.total_issued))), total_retired=scalar(select(func.sum(CreditBatch.total_retired))), open_market_quantity=scalar(select(func.sum(Listing.remaining_quantity)).where(Listing.status == ListingStatus.OPEN)), trade_volume=scalar(select(func.sum(Trade.quantity))), project_count=int(db.scalar(select(func.count(Project.id))) or 0))

@router.get("/system/blockchain", response_model=BlockchainConfigOut)
def blockchain_config(_: User = Depends(require_roles(Role.ADMIN))):
    configured = all((settings.blockchain_rpc_url, settings.carbon_project_contract_address, settings.carbon_credit_contract_address, settings.blockchain_operator_address)) and bool(settings.blockchain_operator_private_key or settings.blockchain_signer_url)
    signing_mode = "external_signer" if settings.blockchain_signer_url else "local_private_key" if settings.blockchain_operator_private_key else "not_configured"
    return BlockchainConfigOut(enabled=settings.blockchain_enabled, configured=configured, network=settings.blockchain_name, chain_id=settings.blockchain_chain_id, rpc_url=settings.blockchain_rpc_url, confirmations=settings.blockchain_confirmations, project_contract_address=settings.carbon_project_contract_address, credit_contract_address=settings.carbon_credit_contract_address, operator_address=settings.blockchain_operator_address, signing_mode=signing_mode)

@router.get("/system/blockchain/operations", response_model=list[ChainOperationOut])
def blockchain_operations(status: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), _: User = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    query = select(ChainOperation).order_by(ChainOperation.created_at.desc()).offset(offset).limit(limit)
    if status:
        query = query.where(ChainOperation.status == status)
    return list(db.scalars(query))
