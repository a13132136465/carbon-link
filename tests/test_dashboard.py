from decimal import Decimal

from app.api import summarize_chain_market


class Result:
    def __init__(self, value):
        self.value = value

    def call(self, *, block_identifier="latest"):
        return self.value


class MarketFunctions:
    orders_by_id = {
        11: ("seller-a", 7, 125_000, 21_500_000, 0, 1, True, 100),
        12: ("buyer-a", 0, 80_000, 20_000_000, 160_000_000, 0, True, 200),
        13: ("seller-b", 8, 570_000, 23_000_000, 0, 1, True, 300),
    }
    trades = [
        (11, "buyer", "seller", 7, 25_000, 53_750_000, 21_500_000, 0, 400),
        (13, "buyer", "seller", 8, 100_000, 230_000_000, 23_000_000, 0, 500),
    ]

    def activeOrderCount(self):
        return Result(len(self.orders_by_id))

    def activeOrderIdAt(self, index):
        return Result(list(self.orders_by_id)[index])

    def orders(self, order_id):
        return Result(self.orders_by_id[order_id])

    def tradeCount(self):
        return Result(len(self.trades))

    def tradeAt(self, index):
        return Result(self.trades[index])


class Market:
    functions = MarketFunctions()


def test_chain_market_dashboard_uses_sell_orders_and_chain_trades():
    open_quantity, trade_volume, latest = summarize_chain_market({7: "batch-7", 8: "batch-8"}, Market())

    assert open_quantity == Decimal("69.5")
    assert trade_volume == Decimal("12.5")
    assert [row["id"] for row in latest] == ["13", "11"]
    assert latest[0]["batch_id"] == "batch-8"
    assert latest[0]["remaining_quantity"] == Decimal("57")
    assert latest[0]["unit_price"] == Decimal("23")


class CreditFunctions:
    def __init__(self, batches):
        self.batches = batches
        self.snapshots = []

    def getBatch(self, batch_id):
        owner = self

        class Call:
            def call(self, *, block_identifier):
                from web3 import Web3
                from web3.exceptions import ContractCustomError
                owner.snapshots.append(block_identifier)
                if batch_id > len(owner.batches):
                    data = Web3.to_hex(Web3.keccak(text="BatchNotFound(uint256)")[:4]) + batch_id.to_bytes(32, 'big').hex()
                    raise ContractCustomError(data, data=data)
                issued, retired = owner.batches[batch_id - 1]
                return (1, bytes(32), bytes(32), 2026, 100, issued, retired, True)

        return Call()


def test_credit_totals_cover_all_chain_batches_and_use_one_snapshot():
    from types import SimpleNamespace
    from app.api import summarize_chain_credits
    # Includes frozen/fully retired batches; no local DB IDs are needed.
    functions = CreditFunctions([(125001, 50001), (70000, 70000), (1, 0)])
    assert summarize_chain_credits(SimpleNamespace(functions=functions), '0xabc') == (Decimal('19.5002'), Decimal('12.0001'))
    assert set(functions.snapshots) == {'0xabc'}


def test_credit_totals_empty_chain():
    from types import SimpleNamespace
    from app.api import summarize_chain_credits
    assert summarize_chain_credits(SimpleNamespace(functions=CreditFunctions([])), '0xabc') == (Decimal(0), Decimal(0))


def test_credit_totals_span_rpc_chunks():
    from types import SimpleNamespace
    from app.api import summarize_chain_credits
    functions = CreditFunctions([(10001, 1)] * 257)
    assert summarize_chain_credits(SimpleNamespace(functions=functions), '0xabc') == (Decimal('257.0257'), Decimal('.0257'))


def test_credit_totals_do_not_turn_rpc_failures_into_zero():
    import pytest
    from types import SimpleNamespace
    from web3.exceptions import ContractCustomError
    from app.api import summarize_chain_credits
    for error in [TimeoutError('RPC timeout'), ContractCustomError('0xdeadbeef', data='0xdeadbeef')]:
        class BadCall:
            def call(self, **kwargs):
                raise error
        credits = SimpleNamespace(functions=SimpleNamespace(getBatch=lambda i: BadCall()))
        with pytest.raises(type(error)):
            summarize_chain_credits(credits, '0xabc')


def test_chain_dashboard_uses_confirmations_and_rejects_reorg(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app import api
    from web3 import Web3
    hashes = [bytes.fromhex('ab' * 32), bytes.fromhex('ab' * 32)]
    heights = []
    def get_block(height):
        heights.append(height)
        return {'hash': hashes.pop(0)}
    eth = SimpleNamespace(block_number=100, get_block=get_block, contract=lambda **kwargs: object())
    class FakeWeb3:
        to_hex = staticmethod(Web3.to_hex)
        to_checksum_address = staticmethod(Web3.to_checksum_address)
        def __init__(self, provider):
            self.eth = eth
    monkeypatch.setattr(api, 'Web3', FakeWeb3)
    monkeypatch.setattr(api.settings, 'blockchain_confirmations', 3)
    for name in ['carbon_marketplace_contract_address', 'carbon_credit_contract_address']:
        monkeypatch.setattr(api.settings, name, '0x' + '11' * 20)
    snapshots = []
    def credits(contract, snapshot):
        snapshots.append(snapshot)
        return Decimal('12'), Decimal('2')
    def market(ids, contract, snapshot):
        snapshots.append(snapshot)
        return Decimal('3'), Decimal('4'), []
    monkeypatch.setattr(api, 'summarize_chain_credits', credits)
    monkeypatch.setattr(api, 'summarize_chain_market', market)
    db = SimpleNamespace(scalars=lambda stmt: [])
    assert api.chain_dashboard(db) == (12, 2, 3, 4, [])
    assert heights == [98, 98]
    assert snapshots == ['0x' + 'ab' * 32] * 2
    hashes[:] = [bytes.fromhex('ab' * 32), bytes.fromhex('cd' * 32)]
    with pytest.raises(HTTPException) as exc:
        api.chain_dashboard(db)
    assert exc.value.status_code == 503
