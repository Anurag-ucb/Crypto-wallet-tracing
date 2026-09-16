import unittest

from core.accounting import FundReconciler
from core.attribution import EntityAttributor
from core.fetcher import BlockchainFetcher
from core.graph import TransactionGraph


class FakeFetcher:
    def __init__(self, transactions):
        self.transactions = transactions

    def get_outgoing_transactions(self, address, max_transactions=100):
        return self.transactions.get(address, [])[:max_transactions]


class CoreTests(unittest.TestCase):
    def test_mock_branch_reconciles_exactly(self):
        fetcher = BlockchainFetcher(use_mock=True)
        origin = fetcher.get_transaction_details("0xorigin")
        graph = TransactionGraph(fetcher, max_depth=1)
        graph.build_from_origin(origin)

        report = FundReconciler(origin["value_wei"]).analyze(graph)

        self.assertTrue(report.is_fully_accounted)
        self.assertEqual(report.unaccounted_amount, 0.0)
        self.assertEqual(report.total_endpoints, 2)

    def test_live_fetch_requires_api_key(self):
        fetcher = BlockchainFetcher(api_key="YOUR_ETHERSCAN_API_KEY")
        with self.assertRaises(RuntimeError):
            fetcher.get_transaction_details("0xorigin")

    def test_cycle_is_not_expanded_forever(self):
        tx = lambda tx_hash, target: {
            "tx_hash": tx_hash,
            "to_address": target,
            "value_wei": 1_000_000_000_000_000_000,
            "gas_price_wei": 0,
            "gas_used": 0,
            "gas_fee_eth": 0.0,
            "block_number": 1,
        }
        fetcher = FakeFetcher({
            "0xroot": [tx("0x1", "0xchild")],
            "0xchild": [tx("0x2", "0xroot")],
        })
        graph = TransactionGraph(fetcher, max_depth=10)
        graph.build_from_origin({
            "tx_hash": "0xorigin",
            "to_address": "0xroot",
            "value_wei": 1_000_000_000_000_000_000,
        })

        self.assertEqual(len(graph.all_nodes), 2)

    def test_known_entity_is_loaded(self):
        attribution = EntityAttributor().get_attribution(
            "0x28c6c06298d514db089934071355e5743bf21d60"
        )
        self.assertEqual(attribution["entity"], "Binance Hot Wallet")


if __name__ == "__main__":
    unittest.main()
