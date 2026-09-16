from dataclasses import dataclass
from typing import Any, Dict

from core.graph import TransactionGraph


@dataclass
class ReconciliationReport:
    """Stores financial metrics for on-chain fund accounting and auditing."""

    initial_stolen_amount: float
    tracked_stolen_flow: float
    total_gas_fees_eth: float
    unaccounted_amount: float
    is_fully_accounted: bool
    total_endpoints: int
    total_nodes_analyzed: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_stolen_amount": self.initial_stolen_amount,
            "tracked_stolen_flow": self.tracked_stolen_flow,
            "total_gas_fees_eth": self.total_gas_fees_eth,
            "unaccounted_amount": self.unaccounted_amount,
            "is_fully_accounted": self.is_fully_accounted,
            "total_endpoints": self.total_endpoints,
            "total_nodes_analyzed": self.total_nodes_analyzed,
        }


class FundReconciler:
    """Calculates multi-branch fund splits, total gas overhead, and mathematical reconciliation."""

    def __init__(self, origin_amount_wei: int) -> None:
        self.origin_amount_wei = int(origin_amount_wei)

    def analyze(self, graph: TransactionGraph) -> ReconciliationReport:
        """Analyzes graph nodes and edges to generate a financial reconciliation summary."""
        endpoints = graph.get_endpoints()

        # Sum tracked flow reaching all active terminal leaf nodes
        tracked_flow_wei = sum(node.stolen_flow_wei for node in endpoints)

        # Calculate cumulative gas fees across all traversed edges
        total_gas_fees_wei = 0
        for node in graph.all_nodes.values():
            for edge in node.edges:
                total_gas_fees_wei += edge.gas_fee_wei

        # Calculate unaccounted balance with floating-point precision tolerance
        unaccounted_wei = self.origin_amount_wei - tracked_flow_wei - total_gas_fees_wei
        is_fully_accounted = unaccounted_wei == 0
        to_eth = lambda value: value / 10**18

        return ReconciliationReport(
            initial_stolen_amount=to_eth(self.origin_amount_wei),
            tracked_stolen_flow=to_eth(tracked_flow_wei),
            total_gas_fees_eth=to_eth(total_gas_fees_wei),
            unaccounted_amount=to_eth(unaccounted_wei),
            is_fully_accounted=is_fully_accounted,
            total_endpoints=len(endpoints),
            total_nodes_analyzed=len(graph.all_nodes),
        )