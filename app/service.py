import json
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings
from app.models import AuditEvent, ChainOperation, Holding, LedgerEntry, LedgerKind, OperationRequest

def fail(code: int, detail: str) -> None:
    raise HTTPException(status_code=code, detail=detail)

def audit(db: Session, actor_id: str | None, action: str, resource_type: str, resource_id: str, detail: dict | None = None) -> None:
    db.add(AuditEvent(actor_id=actor_id, action=action, resource_type=resource_type, resource_id=resource_id, detail=json.dumps(detail or {}, ensure_ascii=False)))

def locked_holding(db: Session, user_id: str, batch_id: str, *, create: bool = False) -> Holding:
    holding = db.scalar(select(Holding).where(Holding.user_id == user_id, Holding.batch_id == batch_id).with_for_update())
    if not holding and create:
        holding = Holding(user_id=user_id, batch_id=batch_id, quantity=Decimal("0"), locked_quantity=Decimal("0"))
        db.add(holding)
        db.flush()
    if not holding:
        fail(404, "Holding not found")
    return holding

def add_ledger(db: Session, holding: Holding, kind: LedgerKind, delta: Decimal, ref_type: str, ref_id: str) -> None:
    db.add(LedgerEntry(user_id=holding.user_id, batch_id=holding.batch_id, kind=kind, quantity_delta=delta, balance_after=holding.quantity, reference_type=ref_type, reference_id=ref_id))

def reserve_operation(db: Session, user_id: str, endpoint: str, key: str) -> None:
    if not key or len(key) > 100:
        fail(400, "Idempotency-Key header is required and must be at most 100 characters")
    exists = db.scalar(select(OperationRequest.id).where(OperationRequest.user_id == user_id, OperationRequest.endpoint == endpoint, OperationRequest.key == key))
    if exists:
        fail(409, "This operation has already been processed")
    db.add(OperationRequest(user_id=user_id, endpoint=endpoint, key=key))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "This operation has already been processed")

def queue_chain_operation(db: Session, operation_type: str, resource_type: str, resource_id: str, contract_address: str | None, payload: dict) -> None:
    if not settings.blockchain_enabled:
        return
    if not contract_address:
        raise RuntimeError(f"Contract address is missing for {operation_type}")
    db.add(ChainOperation(operation_type=operation_type, resource_type=resource_type, resource_id=resource_id, chain_id=settings.blockchain_chain_id, contract_address=contract_address, payload=payload))
