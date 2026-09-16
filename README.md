# CryptoTrace

CryptoTrace is a command-line tool for tracing ETH flows from a transaction or wallet, identifying known service endpoints, and producing a reconciliation report.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Put an Etherscan API key in `.env` for live investigations. Use `--mock` for deterministic offline data.

## Usage

```powershell
# Interactive mode
python main.py --interactive --mock

# Live transaction investigation
python main.py --tx 0x... --depth 7

# Wallet balance investigation
python main.py --tx 0x...40-character-wallet-address... --format json --output report.json

# Machine-readable offline report
python main.py --tx 0xexample --mock --format json --output report.json
```

Useful options include `--depth`, `--max-transactions`, `--format table|json`, `--output`, `--verbose`, and `--api-key`.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Live results depend on Etherscan availability and the selected chain configuration. The current implementation traces native ETH transfers; ERC-20 transfer support is a future extension.
