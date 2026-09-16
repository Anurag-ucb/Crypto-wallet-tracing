import json
from typing import Any, Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from core.accounting import ReconciliationReport
from core.graph import Node


class TerminalFormatter:
    """Handles rich terminal UI rendering, transaction trees, and reconciliation tables."""

    def __init__(self) -> None:
        self.console = Console()

    def print_banner(self) -> None:
        """Renders the CLI tool banner."""
        banner_text = (
            "[bold cyan]CryptoTrace[/bold cyan] - On-Chain Forensics & Fund Tracing Engine\n"
            "[dim]Tracking stolen cryptocurrency flows & financial reconciliation[/dim]"
        )
        self.console.print(Panel(banner_text, expand=False, border_style="cyan"))

    def print_status(self, message: str) -> None:
        """Displays formatted progress status messages."""
        self.console.print(f"[bold blue][*][/bold blue] {message}")

    def print_error(self, message: str) -> None:
        """Displays error messages in bold red."""
        self.console.print(f"[bold red][!][/bold red] {message}")

    def render_graph_tree(
        self, origin_node: Node, endpoints: List[Dict]
    ) -> None:
        """Renders the fund propagation graph as a visual hierarchical tree."""
        if not origin_node:
            self.console.print("[yellow]No transaction graph to display.[/yellow]")
            return

        # Map endpoint addresses to metadata for quick entity lookup
        endpoint_map = {item["address"]: item for item in endpoints}

        root_label = (
            f"[bold yellow]Origin Node:[/bold yellow] [green]{origin_node.address}[/green] "
            f"({origin_node.stolen_flow:.4f} ETH)"
        )
        tree = Tree(root_label)

        def _add_children(parent_tree: Tree, node: Node) -> None:
            for child in node.children:
                is_end = child.is_endpoint
                meta = endpoint_map.get(child.address, {})
                entity_label = meta.get("entity", "Unknown Wallet")
                confidence = meta.get("confidence", "Low")

                if is_end and entity_label != "Unknown Wallet":
                    node_str = (
                        f"[bold magenta]{child.address}[/bold magenta] "
                        f"([cyan]{child.stolen_flow:.4f} ETH[/cyan]) "
                        f"[bold green]➜ {entity_label}[/bold green] [{confidence}]"
                    )
                elif is_end:
                    node_str = (
                        f"[red]{child.address}[/red] "
                        f"([cyan]{child.stolen_flow:.4f} ETH[/cyan]) [dim](Endpoint)[/dim]"
                    )
                else:
                    node_str = (
                        f"[white]{child.address}[/white] "
                        f"([cyan]{child.stolen_flow:.4f} ETH[/cyan])"
                    )

                branch = parent_tree.add(node_str)
                _add_children(branch, child)

        _add_children(tree, origin_node)
        self.console.print("\n[bold underline]Transaction Propagation Tree[/bold underline]")
        self.console.print(tree)
        self.console.print()

    def render_reconciliation_summary(
        self, report: ReconciliationReport
    ) -> None:
        """Prints a structured financial audit table of the investigation."""
        table = Table(title="Financial Reconciliation & Audit Summary", show_header=True)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="bold white")

        table.add_row("Initial Stolen Amount", f"{report.initial_stolen_amount:.6f} ETH")
        table.add_row("Tracked Stolen Flow", f"{report.tracked_stolen_flow:.6f} ETH")
        table.add_row("Total Network Gas Fees", f"{report.total_gas_fees_eth:.6f} ETH")
        table.add_row("Unaccounted Balance", f"{report.unaccounted_amount:.6f} ETH")
        table.add_row("Total Nodes Analyzed", str(report.total_nodes_analyzed))
        table.add_row("Active Terminal Endpoints", str(report.total_endpoints))

        status_str = (
            "[bold green]FULLY BALANCED[/bold green]"
            if report.is_fully_accounted
            else "[bold yellow]DISCREPANCY DETECTED[/bold yellow]"
        )
        table.add_row("Audit Status", status_str)

        self.console.print(table)

    def render_json(self, report: Dict[str, Any]) -> None:
        """Prints a machine-readable report for scripts and integrations."""
        self.console.print(json.dumps(report, indent=2))