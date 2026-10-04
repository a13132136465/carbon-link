from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from web3.exceptions import TransactionNotFound

from app.chain_worker import ChainWorker, utcnow
from app.config import settings
from app.database import SessionLocal, engine
from app.models import ChainOperation


def operation(resource, **kwargs):
    return ChainOperation(operation_type='project.register', resource_type='project', resource_id=resource,
        chain_id=settings.blockchain_chain_id, contract_address='0x' + '22' * 20,
        payload={}, **kwargs)


def worker():
    instance = ChainWorker.__new__(ChainWorker)
    instance.operator = '0x' + '11' * 20
    instance.w3 = SimpleNamespace(eth=SimpleNamespace(
        get_transaction_count=Mock(return_value=5), gas_price=1,
        account=SimpleNamespace(sign_transaction=Mock(return_value=SimpleNamespace(raw_transaction=b'raw', hash=b'hash')))))
    instance._function = Mock(return_value=SimpleNamespace(build_transaction=lambda args: args))
    return instance


def test_prepare_reserves_nonce_even_when_rpc_pending_is_stale(client, monkeypatch):
    monkeypatch.setattr(settings, 'blockchain_signer_url', None)
    w = worker()
    with SessionLocal() as db:
        first, second = operation('one'), operation('two')
        db.add_all([first, second]); db.commit()
        w.prepare(first, db); db.commit()
        # Avoid the mock hash violating the DB uniqueness constraint.
        w.w3.eth.account.sign_transaction.return_value = SimpleNamespace(raw_transaction=b'raw2', hash=b'hash2')
        w.prepare(second, db); db.commit()
        assert (first.nonce, second.nonce) == (5, 6)
        assert second.signer_address == w.operator


def test_receipt_timeout_does_not_starve_pending_work(client):
    w = worker()
    with SessionLocal() as db:
        submitted = operation('one', status='submitted', nonce=5, raw_transaction='0x12', transaction_hash='0x01')
        pending = operation('two', status='pending')
        db.add_all([submitted, pending]); db.commit()
        w.confirm = Mock(side_effect=TimeoutError('RPC unavailable'))
        def prepare(op, session):
            op.nonce, op.raw_transaction, op.transaction_hash, op.status = 6, '0x34', '0x02', 'prepared'
        def broadcast(op): op.status = 'submitted'
        w.prepare, w.broadcast = prepare, broadcast
        assert w._run_locked(db)
        db.refresh(submitted); db.refresh(pending)
        assert submitted.status == 'submitted'
        assert submitted.error_message == 'RPC unavailable'
        assert submitted.next_attempt_at is not None
        assert pending.status == 'submitted'


def test_prepared_transaction_is_replayed_without_resigning(client):
    w = worker()
    with SessionLocal() as db:
        item = operation('one', status='prepared', nonce=5, raw_transaction='0x12', transaction_hash='0x01')
        db.add(item); db.commit()
        w.prepare = Mock(side_effect=AssertionError('must not re-sign'))
        w.w3.eth.send_raw_transaction = Mock(return_value=b'\x01')
        assert w._run_locked(db)
        assert item.status == 'submitted'
        assert item.nonce == 5
        w.w3.eth.send_raw_transaction.assert_called_once_with('0x12')


def test_dropped_transaction_keeps_first_submission_time():
    w = worker()
    original = utcnow() - timedelta(minutes=2)
    item = operation('one', status='submitted', nonce=5, raw_transaction='0x12', transaction_hash='0x01', submitted_at=original)
    w.w3.eth.get_transaction_receipt = Mock(side_effect=TransactionNotFound("not mined"))
    w.w3.eth.send_raw_transaction = Mock(return_value=b'\x01')
    w.confirm(None, item)
    assert item.submitted_at == original
    assert item.nonce == 5


def test_ambiguous_broadcast_preserves_signed_transaction(client, monkeypatch):
    monkeypatch.setattr(settings, 'blockchain_worker_max_attempts', 1)
    w = worker()
    with SessionLocal() as db:
        item = operation('one', status='prepared', nonce=5, raw_transaction='0x12', transaction_hash='0x01')
        pending = operation('two', status='pending')
        db.add_all([item, pending]); db.commit()
        w.broadcast = Mock(side_effect=TimeoutError('unknown broadcast outcome'))
        w.prepare = Mock(side_effect=AssertionError('must not allocate a later nonce'))
        w._run_locked(db)
        db.refresh(item)
        assert item.status == 'needs_attention' and item.raw_transaction == '0x12' and item.nonce == 5
        w._run_locked(db)
        db.refresh(pending)
        assert pending.status == 'pending'


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires account advisory locks')
def test_two_workers_cannot_sign_simultaneously(client):
    first, second = worker(), worker()
    acquired, release = Event(), Event()
    def held(db):
        acquired.set()
        assert release.wait(timeout=10)
        return True
    first._run_locked = held
    second._run_locked = Mock(side_effect=AssertionError('another signer entered'))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first.run_once)
        try:
            assert acquired.wait(timeout=10)
            assert second.run_once() is False
        finally:
            release.set()
        assert future.result()
    # Releasing the connection must release its session-level lock too.
    second._run_locked = lambda db: True
    assert second.run_once()
