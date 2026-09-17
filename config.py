import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Base Directory Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# API & Provider Configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "Your-api-key")
# Updated to Etherscan API V2 unified endpoint
ETHERSCAN_API_URL = os.getenv(
    "ETHERSCAN_API_URL", "https://api.etherscan.io/v2/api"
)
DEFAULT_CHAIN_ID = 1  # 1 = Ethereum Mainnet

# RPC Node Fallback (Alchemy / Infura / Local Node)
WEB3_PROVIDER_URL = os.getenv(
    "WEB3_PROVIDER_URL", "https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY"
)

# Traversal & Execution Defaults
DEFAULT_MAX_DEPTH = 7
DEFAULT_TIMEOUT_SECONDS = 15
MAX_RETRIES = 3
DEFAULT_MAX_TRANSACTIONS = 100

# Data Paths
ATTRIBUTION_DB_PATH = DATA_DIR / "exchanges.json"

# HTTP Headers
REQUEST_HEADERS = {
    "User-Agent": "CryptoTrace-CLI-Forensics/1.0",
    "Accept": "application/json",
}
