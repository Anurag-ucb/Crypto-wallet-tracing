import logging
import hashlib
import time
from typing import Any, Dict, List, Optional
import requests

import config

logger = logging.getLogger(__name__)


class BlockchainFetcher:
    """Handles communication with Etherscan API V2 endpoints with proxy fallback and mock capabilities."""

    def __init__(self, api_key: Optional[str] = None, use_mock: bool = False) -> None:
        self.api_key = (api_key or config.ETHERSCAN_API_KEY).strip()
        self.api_url = config.ETHERSCAN_API_URL
        self.headers = config.REQUEST_HEADERS
        self.session = requests.Session()
        self.use_mock = use_mock

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes HTTP GET requests with API key binding, timeout handling, and retry logic."""
        if self.api_key in {"", "YOUR_ETHERSCAN_API_KEY"}:
            raise RuntimeError(
                "No Etherscan API key configured. Set ETHERSCAN_API_KEY or use --mock."
            )

        params["apikey"] = self.api_key
        params["chainid"] = config.DEFAULT_CHAIN_ID

        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    self.api_url,
                    params=params,
                    headers=self.headers,
                    timeout=config.DEFAULT_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "0" and data.get("message") == "NOTOK":
                    raise ValueError(
                        f"Etherscan API Error: {data.get('result', 'Unknown API Error')}"
                    )

                return data
            except (requests.RequestException, ValueError, RuntimeError) as e:
                if attempt == config.MAX_RETRIES:
                    raise RuntimeError(
                        f"API request failed after {config.MAX_RETRIES} attempts: {str(e)}"
                    )
                logger.warning("Request attempt %s failed: %s", attempt, e)
                time.sleep(1)

        return {}

    @staticmethod
    def wei_to_eth(wei_value: int) -> float:
        """Converts Wei integer representation to standard ETH float."""
        return wei_value / 10**18

    def _get_mock_data(self, tx_hash: str) -> Dict[str, Any]:
        """Generates realistic mock origin data for local testing."""
        return {
            "tx_hash": tx_hash,
            "from_address": "0x1111111111111111111111111111111111111111",
            "to_address": "0x0941dfaa0db804f37df1273e04cf10d55e6ffebffb80",
            "value_wei": 10000000000000000000,
            "value_eth": 10.0,
            "gas_price_wei": 20000000000,
            "gas_used": 21000,
            "gas_fee_eth": 0.00042,
            "block_number": 18000000,
        }

    def get_transaction_details(self, tx_hash: str) -> Dict[str, Any]:
        """Fetch transaction metadata, using synthetic data only in explicit mock mode."""
        clean_tx_hash = tx_hash.strip().lower()

        if self.use_mock:
            return self._get_mock_data(clean_tx_hash)

        # Strategy 1: Standard Proxy RPC Attempt
        try:
            params = {
                "module": "proxy",
                "action": "eth_getTransactionByHash",
                "txhash": clean_tx_hash,
            }
            raw_data = self._make_request(params)
            tx_result = raw_data.get("result")

            if tx_result and isinstance(tx_result, dict) and "from" in tx_result:
                receipt_params = {
                    "module": "proxy",
                    "action": "eth_getTransactionReceipt",
                    "txhash": clean_tx_hash,
                }
                receipt_raw = self._make_request(receipt_params)
                receipt_result = receipt_raw.get("result", {}) or {}

                value_wei = int(tx_result.get("value", "0x0"), 16)
                gas_price_wei = int(tx_result.get("gasPrice", "0x0"), 16)
                gas_used = int(receipt_result.get("gasUsed", "0x0"), 16)

                return {
                    "tx_hash": clean_tx_hash,
                    "from_address": tx_result.get("from", "").lower(),
                    "to_address": tx_result.get("to", "").lower(),
                    "value_wei": value_wei,
                    "value_eth": self.wei_to_eth(value_wei),
                    "gas_price_wei": gas_price_wei,
                    "gas_used": gas_used,
                    "gas_fee_eth": self.wei_to_eth(gas_price_wei * gas_used),
                    "block_number": int(tx_result.get("blockNumber", "0x0"), 16),
                }
        except Exception as error:
            raise RuntimeError(f"Unable to fetch transaction {clean_tx_hash}: {error}") from error

    def get_wallet_start_details(self, address: str) -> Dict[str, Any]:
        """Creates an investigation origin from a wallet's current ETH balance."""
        clean_address = address.strip().lower()
        if self.use_mock:
            balance_wei = 10_000_000_000_000_000_000
        else:
            raw_data = self._make_request(
                {"module": "account", "action": "balance", "address": clean_address, "tag": "latest"}
            )
            try:
                balance_wei = int(raw_data.get("result", "0"))
            except (TypeError, ValueError) as error:
                raise RuntimeError(f"Invalid balance response for {clean_address}") from error

        return {
            "tx_hash": f"wallet:{clean_address}",
            "from_address": clean_address,
            "to_address": clean_address,
            "value_wei": balance_wei,
            "value_eth": self.wei_to_eth(balance_wei),
            "gas_price_wei": 0,
            "gas_used": 0,
            "gas_fee_eth": 0.0,
            "block_number": 0,
        }

    def get_outgoing_transactions(
        self, address: str, max_transactions: int = config.DEFAULT_MAX_TRANSACTIONS
    ) -> List[Dict[str, Any]]:
        """Fetches outgoing transactions via standard txlist endpoint."""
        target_addr = address.strip().lower()

        if self.use_mock:
            if target_addr == "0x0941dfaa0db804f37df1273e04cf10d55e6ffebffb80":
                child_addresses = [
                    "0x28c6c06298d514db089934071355e5743bf21d60",
                    "0x70e24f392c54e428e6170ba9c4320ed643a6d909",
                ]
            else:
                child_addresses = [
                    "0x" + hashlib.sha256(f"{target_addr}:child:{index}".encode()).hexdigest()[-40:]
                    for index in (1, 2)
                ]

            return [
                {
                    "tx_hash": "0x" + hashlib.sha256(f"{target_addr}:tx:1".encode()).hexdigest(),
                    "from_address": target_addr,
                    "to_address": child_addresses[0],
                    "value_wei": 6000000000000000000,
                    "value_eth": 6.0,
                    "gas_price_wei": 20000000000,
                    "gas_used": 21000,
                    "gas_fee_eth": 0.00042,
                    "block_number": 18000001,
                    "timestamp": 1690000000,
                },
                {
                    "tx_hash": "0x" + hashlib.sha256(f"{target_addr}:tx:2".encode()).hexdigest(),
                    "from_address": target_addr,
                    "to_address": child_addresses[1],
                    "value_wei": 3990000000000000000,
                    "value_eth": 3.99,
                    "gas_price_wei": 20000000000,
                    "gas_used": 21000,
                    "gas_fee_eth": 0.00042,
                    "block_number": 18000002,
                    "timestamp": 1690000100,
                },
            ]

        params = {
            "module": "account",
            "action": "txlist",
            "address": target_addr,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
                "offset": max_transactions,
            "sort": "asc",
        }

        raw_data = self._make_request(params)
        tx_list = raw_data.get("result", [])

        if not isinstance(tx_list, list):
            return []

        outgoing_txs = []
        for tx in tx_list:
            if tx.get("from", "").lower() == target_addr and tx.get("isError") == "0":
                value_wei = int(tx.get("value", "0"))
                gas_price_wei = int(tx.get("gasPrice", "0"))
                gas_used = int(tx.get("gasUsed", "0"))

                outgoing_txs.append(
                    {
                        "tx_hash": tx.get("hash"),
                        "from_address": target_addr,
                        "to_address": tx.get("to", "").lower(),
                        "value_wei": value_wei,
                        "value_eth": self.wei_to_eth(value_wei),
                        "gas_price_wei": gas_price_wei,
                        "gas_used": gas_used,
                        "gas_fee_eth": self.wei_to_eth(gas_price_wei * gas_used),
                        "block_number": int(tx.get("blockNumber", "0")),
                        "timestamp": int(tx.get("timeStamp", "0")),
                    }
                )

        return outgoing_txs[:max_transactions]