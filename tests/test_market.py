from datetime import datetime, timedelta, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models import CreditBatch, Holding, LedgerEntry, Listing, Project, ProjectStatus, Trade, User
from app.security import create_access_token


@pytest.fixture()
def market(client):
    with SessionLocal() as db:
        users = [User(email=f"trader{i}@example.com", password_hash="unused", display_name=f"Trader {i}") for i in range(3)]
        db.add_all(users); db.flush()
        project = Project(owner_id=users[0].id, name="碳交易测试", project_type="forestry", region="广东", methodology="AR-001", estimated_tonnes=1000, status=ProjectStatus.APPROVED)
        db.add(project); db.flush()
        batches = [CreditBatch(project_id=project.id, vintage=2025+i, methodology="AR-001", serial_prefix=f"TEST-{i}", total_issued=300, issued_by=users[0].id) for i in range(2)]
        db.add_all(batches); db.flush()
        for b in batches:
            db.add_all([Holding(user_id=u.id, batch_id=b.id, quantity=100, locked_quantity=0) for u in users])
        db.commit()
        headers = [{"Authorization": f"Bearer {create_access_token(u.id, u.role.value)}"} for u in users]
        return client, headers, [b.id for b in batches], [u.id for u in users]


def sell(market, qty="10", price="50", trader=0, batch=0, currency="CNY", key=None):
    client, headers, batches, _ = market
    response = client.post('/api/v1/market/listings', headers={**headers[trader], **({'Idempotency-Key': key} if key else {})}, json={"batch_id": batches[batch], "quantity": qty, "unit_price": price, "currency": currency})
    assert response.status_code == 201, response.text
    return response.json()


def execute(market, qty="10", price="50", policy="FOK", key="execute-1", trader=2, **extra):
    client, headers, batches, _ = market
    return client.post('/api/v1/market/execute', headers={**headers[trader], "Idempotency-Key": key}, json={"batch_id": batches[0], "quantity": qty, "max_unit_price": price, "time_in_force": policy, **extra})


def test_price_time_priority_maker_price_and_ledger_conservation(market):
    expensive = sell(market, price="60")
    first = sell(market, price="50")
    second = sell(market, price="50", trader=1)
    result = execute(market, qty="15", price="65")
    assert result.status_code == 201, result.text
    body = result.json()
    assert [t['listing_id'] for t in body['trades']] == [first['id'], second['id']]
    assert Decimal(body['total_amount']) == 750
    assert all(Decimal(t['unit_price']) == 50 for t in body['trades'])
    with SessionLocal() as db:
        holdings = list(db.scalars(select(Holding).where(Holding.batch_id == market[2][0])))
        assert sum(h.quantity for h in holdings) == 300
        assert sum(h.locked_quantity for h in holdings) == 15
        assert sum(e.quantity_delta for e in db.scalars(select(LedgerEntry))) == 0
        assert db.get(Listing, expensive['id']).remaining_quantity == 10
    assert execute(market, qty="15", price="65").status_code == 409


def test_fok_rolls_back_and_ioc_cancels_remainder(market):
    listing = sell(market, qty="5")
    assert execute(market, qty="9").status_code == 409
    with SessionLocal() as db:
        assert db.get(Listing, listing['id']).remaining_quantity == 5
        assert not list(db.scalars(select(Trade)))
    # Failed request rolls its idempotency reservation back too.
    result = execute(market, qty="9", policy="IOC")
    assert result.status_code == 201
    assert Decimal(result.json()['filled_quantity']) == 5
    assert Decimal(result.json()['remaining_quantity']) == 4


def test_batch_currency_price_isolation_and_empty_book(market):
    sell(market, batch=1, price="1")
    sell(market, currency="USD", price="1")
    sell(market, price="51")
    assert execute(market).status_code == 409
    assert execute(market, policy="IOC").status_code == 409
    result = execute(market, price="51")
    assert result.status_code == 201
    assert result.json()['total_amount'] == '510.00'


def test_self_trade_preflight_prevents_partial_mutation(market):
    first = sell(market, qty="2", price="40")
    sell(market, qty="2", price="50", trader=2)
    assert execute(market, qty="3").status_code == 409
    with SessionLocal() as db:
        assert db.get(Listing, first['id']).remaining_quantity == 2
        assert not list(db.scalars(select(Trade)))
    # An own order beyond the requested fill does not block the earlier fill.
    assert execute(market, qty="2").status_code == 201


def test_quote_read_only_and_revalidated_at_execution(market):
    listing = sell(market, qty="2")
    client, headers, batches, _ = market
    body = {"batch_id": batches[0], "quantity": "2", "max_unit_price": "50"}
    quote = client.post('/api/v1/market/quote', headers=headers[2], json=body)
    assert quote.status_code == 200
    assert quote.json()['executable'] is True
    assert Decimal(quote.json()['total_amount']) == 100
    with SessionLocal() as db:
        assert not list(db.scalars(select(Trade)))
    assert client.delete(f"/api/v1/market/listings/{listing['id']}", headers=headers[0]).status_code == 204
    assert execute(market, qty="2").status_code == 409


def test_depth_aggregates_full_book_and_public_tape_hides_participants(market):
    sell(market, qty="10", price="50")
    sell(market, qty="20", price="50", trader=1)
    sell(market, qty="5", price="60")
    assert execute(market, qty="1").status_code == 201
    response = market[0].get(f'/api/v1/market/snapshot?batch_id={market[2][0]}&depth=1')
    data = response.json()
    assert Decimal(data['available_quantity']) == 34
    assert len(data['asks']) == 1
    assert Decimal(data['asks'][0]['quantity']) == 29
    assert data['asks'][0]['orders'] == 2
    assert data['ticker']['count'] == 1
    assert Decimal(data['ticker']['volume']) == 1
    assert set(data['trades'][0]) == {'id', 'price', 'quantity', 'time'}
    assert market[0].get('/api/v1/market/snapshot?batch_id=missing').status_code == 404


def test_cancel_partial_listing_and_private_order_history(market):
    listing = sell(market)
    assert execute(market, qty="3").status_code == 201
    client, headers, batches, users = market
    assert client.delete(f"/api/v1/market/listings/{listing['id']}", headers=headers[1]).status_code == 403
    assert client.delete(f"/api/v1/market/listings/{listing['id']}", headers=headers[0]).status_code == 204
    with SessionLocal() as db:
        h = db.scalar(select(Holding).where(Holding.user_id == users[0], Holding.batch_id == batches[0]))
        assert h.quantity == 97 and h.locked_quantity == 0
    orders = client.get('/api/v1/market/orders', headers=headers[0])
    assert orders.headers['X-Total-Count'] == '1'
    assert orders.json()[0]['status'] == 'cancelled'
    assert client.get('/api/v1/market/orders', headers=headers[1]).json() == []
    assert client.get('/api/v1/market/orders').status_code == 401


@pytest.mark.parametrize('extra', [{'quantity': '0'}, {'quantity': '-1'}, {'quantity': '0.00001'}, {'max_unit_price': '1.001'}, {'max_unit_price': 'NaN'}, {'time_in_force': 'GTC'}, {'currency': 'abc'}])
def test_input_validation(market, extra):
    assert execute(market, **({'qty': extra.pop('quantity')} if 'quantity' in extra else {}), **extra).status_code == 422


def test_amount_rounding_and_listing_idempotency(market):
    sell(market, qty="0.0001", price="50", key="sell-1")
    client, headers, batches, _ = market
    retry = client.post('/api/v1/market/listings', headers={**headers[0], 'Idempotency-Key': 'sell-1'}, json={'batch_id': batches[0], 'quantity': '0.0001', 'unit_price': '50'})
    assert retry.status_code == 409
    result = execute(market, qty="0.0001")
    assert result.status_code == 201
    assert result.json()['total_amount'] == '0.01'


def test_ticker_excludes_old_trades(market):
    sell(market)
    result = execute(market, qty="1")
    with SessionLocal() as db:
        trade = db.get(Trade, result.json()['trades'][0]['id'])
        trade.traded_at = datetime.now(timezone.utc) - timedelta(days=2)
        db.commit()
    ticker = market[0].get(f'/api/v1/market/snapshot?batch_id={market[2][0]}').json()['ticker']
    assert ticker['count'] == 0 and ticker['high'] is None
    assert ticker['last'] == '50.00'


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires PostgreSQL row locks')
def test_concurrent_buyers_cannot_oversell(market):
    sell(market, qty='10')
    barrier = Barrier(2)
    def take(trader):
        barrier.wait(timeout=10)
        return execute(market, trader=trader, key=f'concurrent-{trader}').status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(take, [1, 2]))
    assert sorted(results) == [201, 409]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Trade)))) == 1
        holdings = list(db.scalars(select(Holding).where(Holding.batch_id == market[2][0])))
        assert sum(h.quantity for h in holdings) == 300
        assert sum(h.locked_quantity for h in holdings) == 0


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires PostgreSQL row locks')
def test_legacy_buy_and_matching_share_inventory_lock(market):
    listing = sell(market, qty='10')
    barrier = Barrier(2)
    def take(legacy):
        barrier.wait(timeout=10)
        if legacy:
            return market[0].post(f"/api/v1/market/listings/{listing['id']}/buy", headers={**market[1][1], 'Idempotency-Key': 'legacy'}, json={'quantity': '10'}).status_code
        return execute(market).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(take, [True, False]))
    assert sorted(results) == [201, 409]
