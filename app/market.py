from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.deps import current_user
from app.market_service import lock_batch, plan_fills, settle
from app.models import CreditBatch, Listing, ListingStatus, Project, Trade, User
from app.schemas import ListingOut, TradeOut
from app.service import audit, fail, reserve_operation

router = APIRouter(prefix="/api/v1/market", tags=["market"])


class ExecuteIn(BaseModel):
    batch_id: str
    currency: str = Field(default="CNY", pattern="^[A-Z]{3}$")
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=4)
    max_unit_price: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    time_in_force: Literal["FOK", "IOC"] = "FOK"


@router.get("/instruments")
def instruments(db: Session = Depends(get_db)):
    currencies: dict[str, list[str]] = {}
    for batch_id, currency in db.execute(select(Listing.batch_id, Listing.currency).distinct()):
        currencies.setdefault(batch_id, []).append(currency)
    query = select(CreditBatch, Project.name, Project.region).join(Project, Project.id == CreditBatch.project_id)
    if settings.blockchain_enabled:
        query = query.where(CreditBatch.chain_batch_id.is_not(None))
    rows = db.execute(query.order_by(CreditBatch.issued_at.desc()))
    return [{"batch_id": b.id, "name": name, "region": region, "vintage": b.vintage,
             "methodology": b.methodology, "serial_prefix": b.serial_prefix,
             "chain_batch_id": b.chain_batch_id,
             "currencies": sorted(currencies.get(b.id, []))} for b, name, region in rows]


@router.get("/snapshot")
def snapshot(batch_id: str, currency: str = Query("CNY", pattern="^[A-Z]{3}$"), depth: int = Query(12, ge=1, le=50), db: Session = Depends(get_db)):
    if not db.get(CreditBatch, batch_id):
        fail(404, "Carbon batch not found")
    listing_filter = (Listing.batch_id == batch_id, Listing.currency == currency, Listing.status == ListingStatus.OPEN)
    levels = db.execute(select(Listing.unit_price, func.sum(Listing.remaining_quantity), func.count(Listing.id)).where(*listing_filter).group_by(Listing.unit_price).order_by(Listing.unit_price).limit(depth)).all()
    cumulative = Decimal(0)
    asks = []
    for price, quantity, count in levels:
        cumulative += quantity
        asks.append({"price": str(price), "quantity": str(quantity), "cumulative": str(cumulative), "orders": count})
    filters = (Trade.batch_id == batch_id, Trade.currency == currency)
    recent = list(db.scalars(select(Trade).where(*filters).order_by(Trade.traded_at.desc(), Trade.id.desc()).limit(60)))
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    high, low, volume, amount, count = db.execute(select(func.max(Trade.unit_price), func.min(Trade.unit_price), func.sum(Trade.quantity), func.sum(Trade.total_amount), func.count(Trade.id)).where(*filters, Trade.traded_at >= since)).one()
    # Public tape intentionally omits participant and listing identifiers.
    return {"batch_id": batch_id, "currency": currency, "as_of": datetime.now(timezone.utc),
            "asks": asks, "available_quantity": str(db.scalar(select(func.sum(Listing.remaining_quantity)).where(*listing_filter)) or 0),
            "ticker": {"last": str(recent[0].unit_price) if recent else None, "high": str(high) if high is not None else None,
                       "low": str(low) if low is not None else None, "volume": str(volume or 0), "amount": str(amount or 0), "count": count},
            "trades": [{"id": t.id, "price": str(t.unit_price), "quantity": str(t.quantity), "time": t.traded_at} for t in recent]}


@router.get("/orders", response_model=list[ListingOut])
def orders(response: Response, batch_id: str | None = None, currency: str | None = None,
           offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    filters = [Listing.seller_id == user.id]
    if batch_id:
        filters.append(Listing.batch_id == batch_id)
    if currency:
        filters.append(Listing.currency == currency)
    response.headers["X-Total-Count"] = str(db.scalar(select(func.count(Listing.id)).where(*filters)) or 0)
    return list(db.scalars(select(Listing).where(*filters).order_by(Listing.created_at.desc(), Listing.id).offset(offset).limit(limit)))


@router.post("/quote")
def quote(body: ExecuteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if settings.blockchain_enabled: fail(410, "Centralized quotes are disabled; read active listings from the marketplace contract")
    if not db.get(CreditBatch, body.batch_id):
        fail(404, "Carbon batch not found")
    fills, remaining = plan_fills(db, body, user.id)
    quantity = body.quantity - remaining
    total = sum((amount for _, _, amount in fills), Decimal(0))
    return {"quantity": str(quantity), "remaining_quantity": str(remaining), "total_amount": str(total),
            "average_price": str(total / quantity) if quantity else None, "fills": len(fills),
            "executable": bool(fills) and (remaining == 0 or body.time_in_force == "IOC")}


@router.post("/execute", status_code=201)
def execute(body: ExecuteIn, idempotency_key: str = Header(alias="Idempotency-Key"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if settings.blockchain_enabled: fail(410, "Centralized settlement is disabled; sign a marketplace contract transaction")
    reserve_operation(db, user.id, "market.execute", idempotency_key)
    lock_batch(db, body.batch_id)
    fills, remaining = plan_fills(db, body, user.id, lock=True)
    if not fills or (remaining and body.time_in_force == "FOK"):
        fail(409, "Insufficient liquidity within your price limit")
    trades = [settle(db, listing, user.id, quantity) for listing, quantity, _ in fills]
    audit(db, user.id, "market.executed", "batch", body.batch_id,
          {"time_in_force": body.time_in_force, "max_unit_price": str(body.max_unit_price),
           "remaining_quantity": str(remaining), "trade_ids": [t.id for t in trades]})
    db.commit()
    return {"filled_quantity": str(body.quantity - remaining), "remaining_quantity": str(remaining),
            "total_amount": str(sum((t.total_amount for t in trades), Decimal(0))),
            "trades": [TradeOut.model_validate(t) for t in trades]}
