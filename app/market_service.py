"""Persistent adaptation of Mini-DEX's maker-price, price/time priority matching.

Carbon batches are separate markets. Buy requests execute immediately; no unfunded
resting bids are created. See docs/mini-dex-integration.md and THIRD_PARTY_NOTICES.md.
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreditBatch, LedgerKind, Listing, ListingStatus, Trade
from app.service import add_ledger, audit, fail, locked_holding


def lock_batch(db: Session, batch_id: str) -> CreditBatch:
    # Every inventory mutation takes this lock before listing/holding locks.
    batch = db.scalar(select(CreditBatch).where(CreditBatch.id == batch_id).with_for_update())
    if not batch:
        fail(404, "Carbon batch not found")
    return batch


def money(quantity: Decimal, price: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 50
        amount = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount >= Decimal("1000000000000000000"):
        fail(422, "Trade amount exceeds supported range")
    return amount


def settle(db: Session, listing: Listing, buyer_id: str, quantity: Decimal) -> Trade:
    if listing.status != ListingStatus.OPEN or listing.remaining_quantity < quantity:
        fail(409, "Requested quantity is unavailable")
    if listing.seller_id == buyer_id:
        fail(409, "Seller cannot buy their own listing")
    amount = money(quantity, listing.unit_price)
    seller = locked_holding(db, listing.seller_id, listing.batch_id)
    buyer = locked_holding(db, buyer_id, listing.batch_id, create=True)
    if seller.quantity < quantity or seller.locked_quantity < quantity:
        fail(409, "Seller inventory is inconsistent")
    seller.quantity -= quantity
    seller.locked_quantity -= quantity
    buyer.quantity += quantity
    listing.remaining_quantity -= quantity
    if listing.remaining_quantity == 0:
        listing.status = ListingStatus.FILLED
    trade = Trade(listing_id=listing.id, buyer_id=buyer_id, seller_id=listing.seller_id,
                  batch_id=listing.batch_id, quantity=quantity, unit_price=listing.unit_price,
                  total_amount=amount, currency=listing.currency)
    db.add(trade)
    db.flush()
    add_ledger(db, seller, LedgerKind.TRADE_OUT, -quantity, "trade", trade.id)
    add_ledger(db, buyer, LedgerKind.TRADE_IN, quantity, "trade", trade.id)
    audit(db, buyer_id, "trade.settled", "trade", trade.id)
    return trade


def plan_fills(db: Session, body, buyer_id: str, *, lock: bool = False):
    query = select(Listing).where(
        Listing.batch_id == body.batch_id, Listing.currency == body.currency,
        Listing.status == ListingStatus.OPEN, Listing.unit_price <= body.max_unit_price,
    ).order_by(Listing.unit_price, Listing.created_at, Listing.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    remaining = body.quantity
    fills = []
    for listing in db.scalars(query):
        if remaining == 0:
            break
        # Preflight the entire execution before making any balance changes.
        if listing.seller_id == buyer_id:
            fail(409, "Order would trade against your own listing; cancel it first")
        quantity = min(remaining, listing.remaining_quantity)
        fills.append((listing, quantity, money(quantity, listing.unit_price)))
        remaining -= quantity
    return fills, remaining
