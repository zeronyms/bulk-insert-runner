# Universal Bulk Insert Runner

A CLI tool for executing bulk HTTP requests using data from **Excel**, **CSV**, or **JSON** files — driven by cURL commands copied directly from the browser DevTools.

---

## Features

- **Parse cURL** — paste a cURL command from browser DevTools, and the tool automatically extracts the URL, HTTP method, headers, and payload.
- **Template Generator** — auto-generates `.xlsx`, `.csv`, and `.json` data templates based on the request payload structure.
- **Bulk Request Execution** — send hundreds of HTTP requests from your spreadsheet with configurable intervals.
- **Grouped Mode** — automatically groups rows by a dynamic ID column and packs them into a single batched request (e.g., `{"courses": [...]}`).
- **Dynamic URL Support** — detects and replaces dynamic path parameters (e.g., `/content/{id}/course`) from your data.
- **Workspace Reset** — clear current config and template files to start fresh for a new API.

---

## Project Structure

```
bulk-insert-runner/
├── main.py               # CLI entry point
├── core/
│   ├── config.py         # File path constants & configuration
│   ├── curl_parser.py    # cURL parsing & URL/payload detection
│   ├── data_handler.py   # Load & export Excel / CSV / JSON
│   └── runner.py         # HTTP request executor
├── requirements.txt
├── run.bat               # Windows one-click runner
└── README.md
```

---

## Requirements

- Python >= 3.10
- Dependencies:
  ```
  requests>=2.28.0
  openpyxl>=3.1.0
  ```

---

## Setup

### Linux / macOS

```bash
# Clone the repository
git clone https://github.com/yourname/bulk-insert-runner.git
cd bulk-insert-runner

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Windows

Double-click `run.bat` — it will automatically:
1. Create the `.venv` virtual environment (if not exists)
2. Install all dependencies
3. Run the program

---

## ▶️ Running the App

```bash
python main.py
```

You will see the main menu:

```
==============================================
         UNIVERSAL BULK INSERT
==============================================
1. Generate Template & Save Auth from cURL
2. Execute Bulk Insert
3. Reset / Clear Current API Config & Data
0. Exit
==============================================
```

---

## Usage Guide

### Menu 1 — Generate Template from cURL

1. Open browser DevTools → **Network** tab
2. Find the request you want to replicate → Right-click → **Copy as cURL**
3. Run Menu 1 and paste the cURL command (type `END` on a new line when done)
4. The tool will:
   - Save the config to `config.json`
   - Generate `data_template.xlsx` (recommended)
   - Generate `data_template.csv`
   - Generate `data_template.json`

> **Tip:** The Excel template is pre-filled with your payload structure — just add or duplicate rows.

---

### Menu 2 — Execute Bulk Insert

1. Fill in `data_template.xlsx` (or `.csv` / `.json`) with your data rows
2. Run Menu 2
3. Select the data source (if multiple files exist)
4. Set the interval between requests (default: 2 seconds)
5. Confirm to start — results will be printed as each request completes

**Modes:**

| Mode | Description |
|------|-------------|
| **Standard** | 1 row = 1 HTTP request |
| **Grouped** | Rows with the same ID are grouped into 1 batched request |

---

### Menu 3 — Reset Workspace

Deletes `config.json` and all template files so you can configure a new API from scratch.

---

## Generated Files

After running Menu 1, these files will be created in the project root:

| File | Description |
|------|-------------|
| `config.json` | Stores URL, method, headers, and mode config |
| `data_template.xlsx` | Excel template for data input |
| `data_template.csv` | CSV template for data input |
| `data_template.json` | JSON template for data input |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Lint & format with Ruff
ruff check .
ruff format .
```

---

## License

MIT License — feel free to use and modify.
