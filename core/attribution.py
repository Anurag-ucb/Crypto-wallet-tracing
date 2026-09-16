import json
from pathlib import Path
from typing import Dict, List, Optional

import config
from core.graph import Node


class EntityAttributor:
    """Matches blockchain addresses against a database of known centralized exchanges,

    mixers, and bridge endpoints.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.ATTRIBUTION_DB_PATH
        self.known_entities: Dict[str, Dict[str, str]] = self._load_database()

    def _load_database(self) -> Dict[str, Dict[str, str]]:
        """Loads and normalizes the entity JSON mapping file."""
        if not self.db_path.exists():
            return {}

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                return {k.lower(): v for k, v in raw_data.items()}
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to load attribution database ({e})")
            return {}

    def get_attribution(self, address: str) -> Dict[str, str]:
        """Looks up metadata for a specific address."""
        target_addr = address.lower()
        return self.known_entities.get(
            target_addr,
            {
                "entity": "Unknown Wallet",
                "category": "Unclassified",
                "confidence": "Low",
            },
        )

    def label_graph_endpoints(self, endpoints: List[Node]) -> List[Dict]:
        """Applies entity labeling across all leaf endpoints in the transaction graph."""
        attributed_nodes = []

        for node in endpoints:
            attribution = self.get_attribution(node.address)
            attributed_nodes.append(
                {
                    "node": node,
                    "address": node.address,
                    "stolen_flow": node.stolen_flow,
                    "entity": attribution["entity"],
                    "category": attribution["category"],
                    "confidence": attribution["confidence"],
                    "source": attribution.get("source", "Unspecified"),
                    "last_verified": attribution.get("last_verified", "Unknown"),
                }
            )

        return attributed_nodes