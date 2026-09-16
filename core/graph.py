from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from core.fetcher import BlockchainFetcher


@dataclass
class Edge:
    """Represents a directed transaction hop between two blockchain addresses."""

    tx_hash: str
    from_address: str
    to_address: str
    amount_wei: int
    gas_fee_wei: int
    stolen_flow_wei: int
    block_number: int

    @property
    def amount_eth(self) -> float:
        return BlockchainFetcher.wei_to_eth(self.amount_wei)

    @property
    def gas_fee_eth(self) -> float:
        return BlockchainFetcher.wei_to_eth(self.gas_fee_wei)


class Node:
    """Represents a wallet address node in the fund propagation graph."""

    def __init__(
        self, address: str, depth: int = 0, initial_stolen_flow_wei: int = 0
    ) -> None:
        self.address: str = address.lower()
        self.depth: int = depth
        self.stolen_flow_wei: int = initial_stolen_flow_wei
        self.edges: List[Edge] = []
        self.children: List["Node"] = []

    @property
    def stolen_flow(self) -> float:
        return BlockchainFetcher.wei_to_eth(self.stolen_flow_wei)

    @property
    def is_endpoint(self) -> bool:
        """Determines if the node is a terminal leaf in the current traversal tree."""
        return len(self.children) == 0


class TransactionGraph:
    """Constructs and manages directed transaction graphs for stolen fund propagation."""

    def __init__(self, fetcher: BlockchainFetcher, max_depth: int = 7, max_transactions: int = 100) -> None:
        self.fetcher = fetcher
        self.max_depth = max_depth
        self.max_transactions = max_transactions
        self.root: Optional[Node] = None
        self.visited_txs: Set[str] = set()
        self.all_nodes: Dict[str, Node] = {}

    def build_from_origin(self, origin_data: Dict) -> Node:
        """Initializes graph root from origin theft transaction and triggers recursive traversal."""
        stolen_amount_wei = int(origin_data["value_wei"])
        origin_address = origin_data["to_address"]

        self.root = Node(
            address=origin_address,
            depth=0,
            initial_stolen_flow_wei=stolen_amount_wei,
        )
        self.all_nodes[origin_address] = self.root
        self.visited_txs.add(origin_data["tx_hash"])

        self._trace_recursive(self.root)
        return self.root

    def _trace_recursive(self, current_node: Node, path_addresses: Optional[Set[str]] = None) -> None:
        """Recursively traverses outgoing transactions up to max_depth while tracking splits and preventing cycles."""
        if current_node.depth >= self.max_depth:
            return

        path_addresses = path_addresses or set()
        if current_node.address in path_addresses:
            return
        path_addresses = path_addresses | {current_node.address}
        outgoing_txs = self.fetcher.get_outgoing_transactions(
            current_node.address, max_transactions=self.max_transactions
        )
        if not outgoing_txs:
            return

        # Sum total outgoing ETH to compute proportional split fractions
        total_outgoing_wei = sum(int(tx["value_wei"]) for tx in outgoing_txs)
        total_gas_wei = sum(int(tx["gas_price_wei"]) * int(tx["gas_used"]) for tx in outgoing_txs)
        available_flow_wei = max(0, current_node.stolen_flow_wei - total_gas_wei)
        if total_outgoing_wei == 0 or available_flow_wei == 0:
            return

        allocated_total_wei = 0
        for index, tx in enumerate(outgoing_txs):
            tx_hash = tx["tx_hash"]
            if tx_hash in self.visited_txs:
                continue

            self.visited_txs.add(tx_hash)

            # Calculate mathematical split ratio for fund flow propagation
            if index == len(outgoing_txs) - 1:
                allocated_stolen_flow_wei = available_flow_wei - allocated_total_wei
            else:
                allocated_stolen_flow_wei = (
                    available_flow_wei * int(tx["value_wei"]) // total_outgoing_wei
                )
            allocated_total_wei += allocated_stolen_flow_wei
            target_address = tx["to_address"]

            edge = Edge(
                tx_hash=tx_hash,
                from_address=current_node.address,
                to_address=target_address,
                amount_wei=int(tx["value_wei"]),
                gas_fee_wei=int(tx["gas_price_wei"]) * int(tx["gas_used"]),
                stolen_flow_wei=allocated_stolen_flow_wei,
                block_number=tx["block_number"],
            )
            current_node.edges.append(edge)

            # Node reuse or instantiation
            if target_address in self.all_nodes:
                child_node = self.all_nodes[target_address]
                child_node.stolen_flow_wei += allocated_stolen_flow_wei
            else:
                child_node = Node(
                    address=target_address,
                    depth=current_node.depth + 1,
                    initial_stolen_flow_wei=allocated_stolen_flow_wei,
                )
                self.all_nodes[target_address] = child_node

            current_node.children.append(child_node)

            # Recurse down child branch
            self._trace_recursive(child_node, path_addresses)

    def get_endpoints(self) -> List[Node]:
        """Returns all leaf nodes where fund propagation terminates or hits max depth."""
        return [node for node in self.all_nodes.values() if node.is_endpoint]