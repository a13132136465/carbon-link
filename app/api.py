from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.deps import current_user, require_roles
from app.models import AuditEvent, ChainOperation, CreditBatch, Holding, LedgerEntry, LedgerKind, Listing, ListingStatus, PasswordResetToken, Project, ProjectDocument, ProjectStatus, Retirement, Role, Trade, User
from app.notifications import send_password_reset
from app.schemas import AgentMessageIn, AgentMessageOut, ApplicationReadinessOut, AuditEventOut, BatchOut, BlockchainConfigOut, BuyIn, ChainOperationOut, ChangePasswordIn, DashboardOut, ForgotPasswordIn, ForgotPasswordOut, HoldingOut, IssueIn, LedgerEntryOut, ListingIn, ListingOut, LoginIn, MessageOut, ProjectDocumentOut, ProjectIn, ProjectOut, ProjectUpdate, RegisterIn, ResetPasswordIn, RetireIn, RetirementOut, ReviewIn, TokenOut, TradeOut, UserAdminUpdate, UserOut
from app.application_agent import REQUIRED_DOCUMENTS, run_application_agent
from app.security import create_access_token, create_reset_token, hash_password, hash_reset_token, verify_password
from app.service import add_ledger, audit, fail, locked_holding, queue_chain_operation, reserve_operation

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)
UPLOAD_ROOT = Path(settings.upload_dir).resolve()
ALLOWED_UPLOAD_TYPES = {
    "application/pdf", "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg", "image/png",
}

def total_header(response: Response, total: int) -> None:
    response.headers["X-Total-Count"] = str(total)

def owned_project(db: Session, project_id: str, user: User, *, reviewer: bool = False) -> Project:
    project = db.get(Project, project_id)
    if not project: fail(404, "Project not found")
    if project.owner_id != user.id and not (reviewer and user.role in (Role.ADMIN, Role.VERIFIER)):
        fail(403, "You do not have access to this project")
    return project

def project_readiness(db: Session, project_id: str) -> ApplicationReadinessOut:
    completed = set(db.scalars(select(ProjectDocument.category).where(ProjectDocument.project_id == project_id)))
    missing = [key for key in REQUIRED_DOCUMENTS if key not in completed]
    return ApplicationReadinessOut(
        ready=not missing,
        completed_categories=[key for key in REQUIRED_DOCUMENTS if key in completed],
        missing_categories=missing,
        completion_percent=round((len(REQUIRED_DOCUMENTS) - len(missing)) / len(REQUIRED_DOCUMENTS) * 100),
    )

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

@router.post("/auth/password/forgot", response_model=ForgotPasswordOut)
def forgot_password(body: ForgotPasswordIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.is_active.is_(True)))
    raw_token = None
    if user:
        raw_token, token_hash = create_reset_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_minutes)))
        db.commit()
        try:
            delivered = send_password_reset(user.email, raw_token)
        except Exception:
            delivered = False
            logger.exception("failed to send password reset email")
        if settings.environment == "production" or delivered:
            raw_token = None
    return ForgotPasswordOut(message="If the account exists, reset instructions have been sent", reset_token=raw_token)

@router.post("/auth/password/reset", response_model=MessageOut)
def reset_password(body: ResetPasswordIn, db: Session = Depends(get_db)):
    token = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_reset_token(body.token),
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).with_for_update())
    if not token: fail(400, "Invalid or expired reset token")
    user = db.get(User, token.user_id)
    if not user or not user.is_active: fail(400, "Invalid or expired reset token")
    user.password_hash = hash_password(body.new_password)
    token.used_at = datetime.now(timezone.utc)
    audit(db, user.id, "user.password_reset", "user", user.id)
    db.commit()
    return MessageOut(message="Password has been reset")

@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)): return user

@router.post("/users/me/password", response_model=MessageOut)
def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash): fail(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit(db, user.id, "user.password_changed", "user", user.id)
    db.commit()
    return MessageOut(message="Password changed")

@router.get("/users", response_model=list[UserOut])
def users(response: Response, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), _: User = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    total_header(response, db.scalar(select(func.count(User.id))) or 0)
    return list(db.scalars(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)))

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserAdminUpdate, actor: User = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target: fail(404, "User not found")
    changes = body.model_dump(exclude_none=True)
    if target.id == actor.id and (changes.get("is_active") is False or changes.get("role") not in (None, Role.ADMIN)):
        fail(409, "Administrators cannot remove their own access")
    for key, value in changes.items(): setattr(target, key, value)
    audit(db, actor.id, "user.updated", "user", target.id, {key: str(value) for key, value in changes.items()})
    db.commit(); db.refresh(target)
    return target

@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = Project(owner_id=user.id, **body.model_dump())
    db.add(project); db.flush(); audit(db, user.id, "project.created", "project", project.id); db.commit(); db.refresh(project)
    return project

@router.get("/projects", response_model=list[ProjectOut])
def projects(response: Response, status_filter: ProjectStatus | None = Query(None, alias="status"), mine: bool = False, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    filters = []
    if status_filter: filters.append(Project.status == status_filter)
    if mine: filters.append(Project.owner_id == user.id)
    total_header(response, db.scalar(select(func.count(Project.id)).where(*filters)) or 0)
    return list(db.scalars(select(Project).where(*filters).order_by(Project.created_at.desc()).offset(offset).limit(limit)))

@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: fail(404, "Project not found")
    if project.owner_id != user.id: fail(403, "Only the owner can edit this project")
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED): fail(409, "Only draft or rejected projects can be edited")
    for key, value in body.model_dump().items(): setattr(project, key, value)
    project.review_note = None
    audit(db, user.id, "project.updated", "project", project.id)
    db.commit(); db.refresh(project)
    return project

@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: fail(404, "Project not found")
    if project.owner_id != user.id and user.role != Role.ADMIN: fail(403, "Only the owner can delete this project")
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED): fail(409, "Only draft or rejected projects can be deleted")
    audit(db, user.id, "project.deleted", "project", project.id)
    db.delete(project); db.commit()

@router.post("/projects/{project_id}/submit", response_model=ProjectOut)
def submit_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project: fail(404, "Project not found")
    if project.owner_id != user.id: fail(403, "Only the owner can submit this project")
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED): fail(409, "Project cannot be submitted in its current state")
    project.status = ProjectStatus.PENDING; project.review_note = None
    audit(db, user.id, "project.submitted", "project", project.id); db.commit(); db.refresh(project)
    return project

@router.get("/applications/{project_id}/readiness", response_model=ApplicationReadinessOut)
def application_readiness(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, project_id, user, reviewer=True)
    return project_readiness(db, project_id)

@router.get("/projects/{project_id}/documents", response_model=list[ProjectDocumentOut])
def project_documents(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, project_id, user, reviewer=True)
    return list(db.scalars(select(ProjectDocument).where(ProjectDocument.project_id == project_id).order_by(ProjectDocument.created_at.desc())))

@router.post("/projects/{project_id}/documents", response_model=ProjectDocumentOut, status_code=201)
async def upload_project_document(
    project_id: str,
    request: Request,
    category: str = Query(...),
    x_file_name: str = Header(..., alias="X-File-Name"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    project = owned_project(db, project_id, user)
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED):
        fail(409, "Documents can only be changed for draft or rejected projects")
    if category not in REQUIRED_DOCUMENTS:
        fail(400, "Unknown document category")
    content_type = request.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
    if content_type not in ALLOWED_UPLOAD_TYPES:
        fail(415, "Only PDF, Word, Excel, JPG and PNG files are accepted")
    content = await request.body()
    if not content or len(content) > settings.max_upload_bytes:
        fail(413, f"File must be between 1 byte and {settings.max_upload_bytes} bytes")
    original_name = Path(unquote(x_file_name) or "document").name[:255]
    suffix = Path(original_name).suffix.lower()[:12]
    storage_name = f"{project_id}/{uuid4().hex}{suffix}"
    destination = UPLOAD_ROOT / storage_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    document = ProjectDocument(project_id=project_id, uploaded_by=user.id, category=category, original_name=original_name, storage_name=storage_name, content_type=content_type, size_bytes=len(content))
    db.add(document); db.flush()
    audit(db, user.id, "project.document_uploaded", "project", project.id, {"document_id": document.id, "category": category})
    db.commit(); db.refresh(document)
    return document

@router.get("/projects/{project_id}/documents/{document_id}/download")
def download_project_document(project_id: str, document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, project_id, user, reviewer=True)
    document = db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id: fail(404, "Document not found")
    path = UPLOAD_ROOT / document.storage_name
    if not path.is_file(): fail(404, "Stored file not found")
    return FileResponse(path, media_type=document.content_type, filename=document.original_name)

@router.delete("/projects/{project_id}/documents/{document_id}", status_code=204)
def delete_project_document(project_id: str, document_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED): fail(409, "Submitted documents are locked")
    document = db.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id: fail(404, "Document not found")
    path = UPLOAD_ROOT / document.storage_name
    if path.is_file(): path.unlink()
    audit(db, user.id, "project.document_deleted", "project", project.id, {"document_id": document.id})
    db.delete(document); db.commit()

@router.post("/applications/{project_id}/submit", response_model=ProjectOut)
def submit_application(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = owned_project(db, project_id, user)
    if project.status not in (ProjectStatus.DRAFT, ProjectStatus.REJECTED): fail(409, "Project cannot be submitted in its current state")
    readiness = project_readiness(db, project_id)
    if not readiness.ready:
        missing = ", ".join(REQUIRED_DOCUMENTS[key] for key in readiness.missing_categories)
        fail(409, f"Please upload all required review materials: {missing}")
    project.status = ProjectStatus.PENDING; project.review_note = None
    audit(db, user.id, "application.submitted", "project", project.id, {"document_categories": readiness.completed_categories})
    db.commit(); db.refresh(project)
    return project

@router.post("/application-agent/message", response_model=AgentMessageOut, response_model_exclude_none=True)
def application_agent(body: AgentMessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = None
    readiness = None
    if body.project_id:
        project = owned_project(db, body.project_id, user)
        readiness = project_readiness(db, project.id)
    result = run_application_agent({
        "message": body.message,
        "project_name": project.name if project else "",
        "project": ProjectOut.model_validate(project).model_dump(mode="json") if project else None,
        "documents": [{"category": doc.category, "name": doc.original_name} for doc in db.scalars(select(ProjectDocument).where(ProjectDocument.project_id == project.id))] if project else [],
        "history": [turn.model_dump() for turn in body.history],
        "draft": body.draft.model_dump(exclude_none=True),
        "missing_documents": readiness.missing_categories if readiness else list(REQUIRED_DOCUMENTS),
        "completion_percent": readiness.completion_percent if readiness else 0,
    })
    return AgentMessageOut(reply=result["reply"], stage=result["stage"], suggested_actions=result["suggested_actions"], readiness=readiness, draft=result.get("draft"), missing_fields=result.get("missing_fields", []), model_available=result.get("model_available", False))

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
def batches(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), _: User = Depends(current_user), db: Session = Depends(get_db)):
    total_header(response, db.scalar(select(func.count(CreditBatch.id))) or 0)
    return list(db.scalars(select(CreditBatch).order_by(CreditBatch.issued_at.desc()).offset(offset).limit(limit)))

@router.get("/wallet/holdings", response_model=list[HoldingOut])
def holdings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Holding).where(Holding.user_id == user.id).order_by(Holding.batch_id)))

@router.get("/wallet/ledger", response_model=list[LedgerEntryOut])
def ledger(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    total_header(response, db.scalar(select(func.count(LedgerEntry.id)).where(LedgerEntry.user_id == user.id)) or 0)
    return list(db.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id).order_by(LedgerEntry.created_at.desc()).offset(offset).limit(limit)))

@router.post("/market/listings", response_model=ListingOut, status_code=201)
def create_listing(body: ListingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    holding = locked_holding(db, user.id, body.batch_id)
    if holding.quantity - holding.locked_quantity < body.quantity: fail(409, "Insufficient available credits")
    holding.locked_quantity += body.quantity
    listing = Listing(seller_id=user.id, batch_id=body.batch_id, quantity=body.quantity, remaining_quantity=body.quantity, unit_price=body.unit_price, currency=body.currency)
    db.add(listing); db.flush(); audit(db, user.id, "listing.created", "listing", listing.id); db.commit(); db.refresh(listing)
    return listing

@router.get("/market/listings", response_model=list[ListingOut])
def list_market(response: Response, batch_id: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    filters = [Listing.status == ListingStatus.OPEN]
    if batch_id: filters.append(Listing.batch_id == batch_id)
    total_header(response, db.scalar(select(func.count(Listing.id)).where(*filters)) or 0)
    return list(db.scalars(select(Listing).where(*filters).order_by(Listing.unit_price, Listing.created_at).offset(offset).limit(limit)))

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

@router.get("/market/trades", response_model=list[TradeOut])
def trades(response: Response, mine: bool = True, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    filters = [or_(Trade.buyer_id == user.id, Trade.seller_id == user.id)] if mine or user.role != Role.ADMIN else []
    total_header(response, db.scalar(select(func.count(Trade.id)).where(*filters)) or 0)
    return list(db.scalars(select(Trade).where(*filters).order_by(Trade.traded_at.desc()).offset(offset).limit(limit)))

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

@router.get("/retirements", response_model=list[RetirementOut])
def retirements(response: Response, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), db: Session = Depends(get_db)):
    total_header(response, db.scalar(select(func.count(Retirement.id)).where(Retirement.user_id == user.id)) or 0)
    return list(db.scalars(select(Retirement).where(Retirement.user_id == user.id).order_by(Retirement.retired_at.desc()).offset(offset).limit(limit)))

@router.get("/dashboard", response_model=DashboardOut)
def dashboard(_: User = Depends(current_user), db: Session = Depends(get_db)):
    scalar = lambda stmt: db.scalar(stmt) or Decimal("0")
    return DashboardOut(total_issued=scalar(select(func.sum(CreditBatch.total_issued))), total_retired=scalar(select(func.sum(CreditBatch.total_retired))), open_market_quantity=scalar(select(func.sum(Listing.remaining_quantity)).where(Listing.status == ListingStatus.OPEN)), trade_volume=scalar(select(func.sum(Trade.quantity))), project_count=int(db.scalar(select(func.count(Project.id))) or 0))

@router.get("/system/blockchain", response_model=BlockchainConfigOut)
def blockchain_config(_: User = Depends(require_roles(Role.ADMIN))):
    configured = all((settings.blockchain_rpc_url, settings.carbon_project_contract_address, settings.carbon_credit_contract_address, settings.blockchain_operator_address)) and bool(settings.blockchain_operator_private_key or settings.blockchain_signer_url)
    signing_mode = "disabled" if not settings.blockchain_enabled else "external_signer" if settings.blockchain_signer_url else "local_signer" if settings.blockchain_operator_private_key else "not_configured"
    return BlockchainConfigOut(enabled=settings.blockchain_enabled, configured=configured, network=settings.blockchain_name, chain_id=settings.blockchain_chain_id, rpc_url=settings.blockchain_rpc_url, confirmations=settings.blockchain_confirmations, project_contract_address=settings.carbon_project_contract_address, credit_contract_address=settings.carbon_credit_contract_address, operator_address=settings.blockchain_operator_address, signing_mode=signing_mode)

@router.get("/system/blockchain/operations", response_model=list[ChainOperationOut])
def blockchain_operations(response: Response, status: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), _: User = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    filters = [ChainOperation.status == status] if status else []
    total_header(response, db.scalar(select(func.count(ChainOperation.id)).where(*filters)) or 0)
    return list(db.scalars(select(ChainOperation).where(*filters).order_by(ChainOperation.created_at.desc()).offset(offset).limit(limit)))

@router.get("/system/audit-events", response_model=list[AuditEventOut])
def audit_events(response: Response, action: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), _: User = Depends(require_roles(Role.ADMIN)), db: Session = Depends(get_db)):
    filters = [AuditEvent.action == action] if action else []
    total_header(response, db.scalar(select(func.count(AuditEvent.id)).where(*filters)) or 0)
    return list(db.scalars(select(AuditEvent).where(*filters).order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)))
