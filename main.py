import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

import config
from core.accounting import FundReconciler
from core.attribution import EntityAttributor
from core.fetcher import BlockchainFetcher
from core.graph import TransactionGraph
from ui.formatter import TerminalFormatter


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crypto-tracer",
        description="CryptoTrace: Stolen-Cryptocurrency On-Chain Tracing & Reconciliation Terminal Tool",
    )

    parser.add_argument(
        "--tx",
        type=str,
        help="Transaction hash or starting wallet address to investigate.",
    )

    parser.add_argument(
        "--depth",
        type=int,
        default=config.DEFAULT_MAX_DEPTH,
        help=f"Maximum hop depth to trace fund transfers (default: {config.DEFAULT_MAX_DEPTH}).",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Override default Etherscan / RPC provider API key.",
    )

    parser.add_argument("--mock", action="store_true", help="Use deterministic offline demo data.")
    parser.add_argument("--interactive", action="store_true", help="Prompt for investigation options.")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--output", type=Path, help="Write a JSON report to this file.")
    parser.add_argument("--max-transactions", type=int, default=config.DEFAULT_MAX_TRANSACTIONS)
    parser.add_argument("--verbose", action="store_true", help="Enable request and traversal logs.")

    return parser.parse_args()


def run_investigation(
    tx_hash: str,
    max_depth: int,
    api_key: Optional[str] = None,
    use_mock: bool = False,
    output_format: str = "table",
    output_path: Optional[Path] = None,
    max_transactions: int = config.DEFAULT_MAX_TRANSACTIONS,
) -> None:
    formatter = TerminalFormatter()
    formatter.print_banner()

    try:
        if max_depth < 0 or max_transactions < 1:
            raise ValueError("Depth must be non-negative and max transactions must be positive.")
        is_wallet = bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", tx_hash))
        is_transaction = bool(re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash))
        if not use_mock and not (is_wallet or is_transaction):
            raise ValueError("Input must be a 40-character wallet address or 64-character transaction hash.")
        # Step 1: Initialize API Fetcher and verify connection
        formatter.print_status("Initializing Blockchain Fetcher...")
        fetcher = BlockchainFetcher(
            api_key=api_key or config.ETHERSCAN_API_KEY, use_mock=use_mock
        )

        # Step 2: Extract origin transaction / stolen amount details
        formatter.print_status(f"Fetching origin transaction metadata for: {tx_hash}")
        if len(tx_hash) == 42 and tx_hash.startswith("0x"):
            origin_data = fetcher.get_wallet_start_details(tx_hash)
        else:
            origin_data = fetcher.get_transaction_details(tx_hash)

        # Step 3: Build transaction graph and execute depth traversal
        formatter.print_status(
            f"Building directed transaction graph up to depth {max_depth}..."
        )
        graph = TransactionGraph(
            fetcher=fetcher, max_depth=max_depth, max_transactions=max_transactions
        )
        graph.build_from_origin(origin_data)

        # Step 4: Perform fund reconciliation and split accounting
        formatter.print_status("Calculating fund reconciliation & gas fee totals...")
        reconciler = FundReconciler(origin_amount_wei=origin_data["value_wei"])
        reconciliation_report = reconciler.analyze(graph)

        # Step 5: Match leaf nodes against known service attributions
        formatter.print_status("Matching endpoints against Known-Service Database...")
        attributor = EntityAttributor(db_path=config.ATTRIBUTION_DB_PATH)
        attributed_nodes = attributor.label_graph_endpoints(graph.get_endpoints())

        # Step 6: Render visual output trees and reconciliation tables
        formatter.print_status("Generating investigation report...")
        report = {
            "origin": origin_data,
            "endpoints": [
                {
                    "address": item["address"],
                    "stolen_flow_eth": item["stolen_flow"],
                    "entity": item["entity"],
                    "category": item["category"],
                    "confidence": item["confidence"],
                    "source": item["source"],
                    "last_verified": item["last_verified"],
                }
                for item in attributed_nodes
            ],
            "reconciliation": reconciliation_report.to_dict(),
        }
        if output_format == "json":
            formatter.render_json(report)
        else:
            formatter.render_graph_tree(origin_node=graph.root, endpoints=attributed_nodes)
            formatter.render_reconciliation_summary(reconciliation_report)
        if output_path:
            output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            formatter.print_status(f"Report written to {output_path}")

    except KeyboardInterrupt:
        formatter.print_error("\nInvestigation aborted by user.")
        sys.exit(1)
    except Exception as e:
        formatter.print_error(f"Investigation failed: {str(e)}")
        sys.exit(1)


def main() -> None:
    args = parse_arguments()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    if args.interactive or not args.tx:
        print("CryptoTrace interactive investigation")
        args.tx = input("Transaction hash or wallet address: ").strip()
        depth = input(f"Maximum depth [{args.depth}]: ").strip()
        if depth:
            args.depth = int(depth)
        if not args.mock:
            args.mock = input("Use offline mock data? [y/N]: ").strip().lower() == "y"
    run_investigation(
        tx_hash=args.tx,
        max_depth=args.depth,
        api_key=args.api_key,
        use_mock=args.mock,
        output_format=args.format,
        output_path=args.output,
        max_transactions=args.max_transactions,
    )


if __name__ == "__main__":
    main()