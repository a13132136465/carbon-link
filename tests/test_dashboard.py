from decimal import Decimal

from app.api import summarize_chain_market


class Result:
    def __init__(self, value):
        self.value = value

    def call(self):
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
