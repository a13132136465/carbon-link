from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from web3 import Web3

from app import api
from app.config import settings
from app.database import SessionLocal, engine
from app.models import ChainOperation, CreditBatch, Project, ProjectStatus, User
from tests.test_workflow import register, login, upload_required


def project(client, headers):
    result = client.post('/api/v1/projects', headers=headers, json={
        'name': 'Private draft', 'project_type': 'forestry', 'region': 'Guangxi',
        'methodology': 'AR-001', 'description': 'Confidential', 'estimated_tonnes': '12.5'})
    assert result.status_code == 201
    return result.json()['id']


def member(client, email='member@example.com'):
    register(client, email)
    return login(client, email)


def test_project_list_isolates_members_for_all_filters(client):
    alice = member(client)
    bob = member(client, 'bob@example.com')
    project_id = project(client, alice)
    for suffix in ('', '?mine=false', '?mine=true', '?status=draft'):
        result = client.get('/api/v1/projects' + suffix, headers=bob)
        assert result.json() == []
        assert result.headers['X-Total-Count'] == '0'
    admin = login(client, 'admin@example.com', 'AdminPassword123!')
    assert client.get('/api/v1/projects', headers=admin).json()[0]['id'] == project_id


@pytest.mark.parametrize('delivery', ['missing', 'error', 'success'])
def test_forgot_never_exposes_token(client, monkeypatch, delivery):
    member(client)
    def send(email, token):
        if delivery == 'error':
            raise OSError('mail failure')
        return delivery == 'success'
    monkeypatch.setattr(api, 'send_password_reset', send)
    known = client.post('/api/v1/auth/password/forgot', json={'email': 'member@example.com'})
    unknown = client.post('/api/v1/auth/password/forgot', json={'email': 'unknown@example.com'})
    assert known.json() == unknown.json()
    assert set(known.json()) == {'message'}


@pytest.mark.parametrize('method', ['change', 'reset'])
def test_password_change_revokes_sessions_and_all_reset_tokens(client, monkeypatch, method):
    old = member(client)
    tokens = []
    monkeypatch.setattr(api, 'send_password_reset', lambda email, token: tokens.append(token))
    for _ in range(2):
        client.post('/api/v1/auth/password/forgot', json={'email': 'member@example.com'})
    if method == 'change':
        result = client.post('/api/v1/users/me/password', headers=old,
                             json={'current_password': 'MemberPass123!', 'new_password': 'NewPassword123!'})
    else:
        result = client.post('/api/v1/auth/password/reset', json={'token': tokens[0], 'new_password': 'NewPassword123!'})
    assert result.status_code == 200
    assert client.get('/api/v1/users/me', headers=old).status_code == 401
    for token in tokens:
        assert client.post('/api/v1/auth/password/reset', json={'token': token, 'new_password': 'OtherPassword123!'}).status_code == 400
    fresh = login(client, 'member@example.com', 'NewPassword123!')
    assert client.get('/api/v1/users/me', headers=fresh).status_code == 200


@pytest.mark.parametrize('route', ['projects', 'applications'])
def test_both_submit_routes_require_documents(client, route):
    headers = member(client)
    pid = project(client, headers)
    assert client.post(f'/api/v1/{route}/{pid}/submit', headers=headers).status_code == 409
    upload_required(client, headers, pid)
    assert client.post(f'/api/v1/{route}/{pid}/submit', headers=headers).status_code == 200


def test_oversize_stream_leaves_no_document(client, monkeypatch):
    headers = member(client)
    pid = project(client, headers)
    monkeypatch.setattr(settings, 'max_upload_bytes', 8)
    result = client.post(f'/api/v1/projects/{pid}/documents?category=project_design',
        headers={**headers, 'Content-Type': 'application/pdf', 'X-File-Name': 'test.pdf'},
        content=iter([b'12345', b'67890']))
    assert result.status_code == 413
    assert not list(api.UPLOAD_ROOT.rglob('*.pdf'))
    assert client.get(f'/api/v1/projects/{pid}/documents', headers=headers).json() == []


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires PostgreSQL row locks')
def test_concurrent_approval_and_rejection_have_one_winner(client, monkeypatch):
    headers = member(client)
    pid = project(client, headers)
    upload_required(client, headers, pid)
    assert client.post(f'/api/v1/projects/{pid}/submit', headers=headers).status_code == 200
    admin = login(client, 'admin@example.com', 'AdminPassword123!')
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == 'member@example.com'))
        owner.wallet_address = '0x' + '11' * 20
        db.commit()
    monkeypatch.setattr(settings, 'blockchain_enabled', True)
    monkeypatch.setattr(settings, 'carbon_project_contract_address', '0x' + '22' * 20)
    barrier = Barrier(2)
    def review(approved):
        barrier.wait(timeout=10)
        return client.post(f'/api/v1/projects/{pid}/review', headers=admin, json={'approved': approved}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(review, [True, False])) == [200, 409]
    with SessionLocal() as db:
        p = db.get(Project, pid)
        operations = list(db.scalars(select(ChainOperation).where(ChainOperation.resource_id == pid)))
        assert len(operations) == (1 if p.status == ProjectStatus.APPROVED else 0)


def test_retirement_requires_original_signed_reason(client, monkeypatch):
    headers = member(client)
    pid = project(client, headers)
    address, contract_address = '0x' + '11' * 20, '0x' + '22' * 20
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == 'member@example.com'))
        owner.wallet_address = address
        batch = CreditBatch(project_id=pid, vintage=2026, methodology='AR-001', serial_prefix='AUDIT', total_issued=10, issued_by=owner.id, chain_batch_id=7)
        db.add(batch); db.commit()
        batch_id = batch.id
    monkeypatch.setattr(settings, 'blockchain_enabled', True)
    monkeypatch.setattr(settings, 'carbon_credit_contract_address', contract_address)
    args = SimpleNamespace(batchId=7, amount=10000, account=address,
        beneficiaryHash=Web3.keccak(text='beneficiary'), evidenceDigest=Web3.keccak(text='original'), retirementId=1)
    event = SimpleNamespace(args=args)
    contract = SimpleNamespace(events=SimpleNamespace(CreditRetired=lambda: SimpleNamespace(process_receipt=lambda receipt: [event])))
    eth = SimpleNamespace(block_number=100, get_transaction_receipt=lambda tx: SimpleNamespace(status=1, blockNumber=90),
        get_transaction=lambda tx: {'from': address, 'to': contract_address}, contract=lambda **kwargs: contract)
    class FakeWeb3:
        to_checksum_address = staticmethod(Web3.to_checksum_address)
        keccak = staticmethod(Web3.keccak)
        def __init__(self, *args): self.eth = eth
    monkeypatch.setattr(api, 'Web3', FakeWeb3)
    body = {'batch_id': batch_id, 'quantity': '1', 'beneficiary': 'beneficiary', 'reason': 'altered', 'transaction_hash': '0x' + 'ab' * 32}
    assert client.post('/api/v1/retirements/confirm', headers=headers, json=body).status_code == 422
    body['reason'] = 'original'
    assert client.post('/api/v1/retirements/confirm', headers=headers, json=body).status_code == 201


def test_chain_mode_never_returns_legacy_ledger(client, monkeypatch):
    headers = member(client)
    monkeypatch.setattr(settings, 'blockchain_enabled', True)
    assert client.get('/api/v1/wallet/ledger', headers=headers).status_code == 409


def test_chain_dashboard_returns_chain_totals(client, monkeypatch):
    headers = member(client)
    monkeypatch.setattr(settings, 'blockchain_enabled', True)
    monkeypatch.setattr(api, 'chain_dashboard', lambda db: (12, 2, 3, 4, []))
    data = client.get('/api/v1/dashboard', headers=headers).json()
    assert data['total_issued'] == '12' and data['total_retired'] == '2'
    assert data['blockchain_enabled'] is True
    assert data['trade_volume'] == '4' and data['open_market_quantity'] == '3'


def test_browser_never_receives_private_rpc(client, monkeypatch):
    headers = member(client)
    monkeypatch.setattr(settings, 'blockchain_rpc_url', 'https://private.invalid/secret-key')
    monkeypatch.setattr(settings, 'blockchain_public_rpc_url', 'https://public.invalid/rpc')
    response = client.get('/api/v1/chain/config', headers=headers)
    assert response.json()['rpc_url'] == 'https://public.invalid/rpc'
    assert 'secret-key' not in response.text
