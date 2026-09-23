# Universal Bulk Insert Runner

A tool for sending data in bulk to internal APIs via HTTP requests — without having to input records one by one. Available in two modes: **CLI** (terminal) and **browser-based GUI** (Streamlit).

---

## Background

Many internal office applications do not provide a bulk insert feature. As a result, users are forced to enter data one by one through forms — a time-consuming and error-prone process. This tool allows anyone to send hundreds of records at once by simply copying a single request from the browser.

---

## Features

- **Automatic cURL parsing** — paste a cURL command from browser DevTools, and the tool automatically extracts the URL, method, headers, and payload.
- **Template generator** — automatically creates `.xlsx`, `.csv`, and `.json` data templates based on the request payload structure.
- **Bulk request execution** — send hundreds of HTTP requests from a spreadsheet with a configurable interval between each request.
- **Grouped Mode** — groups rows by an ID column and packs them into a single batched request (e.g., `{"courses": [...]}`).
- **Dynamic URL support** — detects and replaces dynamic path parameters (e.g., `/content/{id}/course`) using values from your data.
- **Browser GUI** — a wizard-based Streamlit interface: edit the data table directly in the browser without opening a separate Excel file.
- **Auto-stop** — automatically stops if the login session or CSRF token has expired (HTTP 401/419).
- **Workspace reset** — delete config and template files to start fresh with a new API.

---

## Project Structure

```
bulk-insert-runner/
├── main.py               # CLI entry point
├── app.py                # GUI entry point (Streamlit)
├── core/
│   ├── config.py         # File path constants
│   ├── curl_parser.py    # cURL parser and URL/payload detection
│   ├── data_handler.py   # Read & write Excel / CSV / JSON
│   └── runner.py         # HTTP request executor
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project configuration & linting
├── run.bat               # One-click runner for Windows (CLI)
├── run.sh                # One-click runner for Linux/macOS (CLI)
└── README.md
```

---

## Requirements

- Python >= 3.10
- Dependencies:

```
requests>=2.28.0
openpyxl>=3.1.0
streamlit>=1.35.0
pandas>=2.0.0
```

> `streamlit` and `pandas` are only required for GUI mode.

---

## Setup

### Linux / macOS

```bash
# Clone the repository
git clone https://github.com/zeronyms/bulk-insert-runner.git
cd bulk-insert-runner

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Windows

Double-click `run.bat` — it will automatically:
1. Create the `.venv` virtual environment (if it does not exist)
2. Install all dependencies
3. Launch the CLI program

---

## Running the Application

### GUI Mode (Streamlit) — Recommended for general users

```bash
# Linux / macOS
.venv/bin/streamlit run app.py

# Windows
.venv\Scripts\streamlit run app.py
```

Then open your browser and go to: **http://localhost:8501**

### CLI Mode (Terminal)

```bash
# Linux / macOS
python main.py
# or run directly:
bash run.sh

# Windows
python main.py
# or double-click:
run.bat
```

---

## Usage Guide — GUI (Streamlit)

### Step 1 — Paste cURL

1. Open the target application in your browser
2. Press **F12** to open Developer Tools
3. Go to the **Network** tab
4. Perform **one action** in the application (e.g., add a single record)
5. Find the request that appears, right-click → **Copy as cURL**
6. Paste it into the input field and click **Parse cURL**

The tool will automatically detect:
- The endpoint URL and HTTP method
- Request headers (including authentication tokens)
- The payload / request body structure
- Dynamic IDs in the URL (if any)
- Grouped Mode (if the payload contains an array)

### Step 2 — Fill in Data

- Edit the interactive table directly in the browser
- Click a new row to add data
- Or upload a pre-filled **Excel (.xlsx)** or **CSV (.csv)** file

### Step 3 — Preview & Run

- Review the preview of the first request payload before sending
- Set the delay between requests (default: 2 seconds)
- Set the timeout per request (default: 30 seconds)
- Click **Run** — progress and results are displayed in real time
- A results table shows the status of each request (success / failed)

---

## Usage Guide — CLI

### Menu 1 — Generate Template from cURL

1. Open browser DevTools → **Network** tab
2. Find the request you want to replicate → right-click → **Copy as cURL**
3. Run Menu 1 and paste the cURL command (type `END` on a new line when finished)
4. The tool will generate:
   - `config.json` — stores the URL, method, headers, and mode configuration
   - `data_template.xlsx` — Excel template (recommended)
   - `data_template.csv` — CSV template
   - `data_template.json` — JSON template

### Menu 2 — Execute Bulk Insert

1. Fill in `data_template.xlsx` (or `.csv` / `.json`) with the data you want to send
2. Run Menu 2
3. Select a data source if multiple files exist
4. Set the interval between requests (default: 2 seconds)
5. Confirm to start — the result of each request is printed as it completes

### Menu 3 — Reset Workspace

Deletes `config.json` and all template files so you can configure a new API from scratch.

---

## Request Modes

| Mode | When to Use | How It Works |
|------|-------------|--------------|
| **Standard** | Payload is a single object `{}` | 1 data row = 1 HTTP request |
| **Grouped** | Payload is an object containing an array `{"items": [...]}` | Rows sharing the same ID are merged into a single batch request |

### Grouped Mode Example

If the endpoint accepts a payload like:

```json
{
  "courses": [
    {"courseCode": "CS101"},
    {"courseCode": "CS102"}
  ]
}
```

Fill the data table like this:

| learningPlanId | courseCode |
|----------------|------------|
| LRPN-001       | CS101      |
| LRPN-001       | CS102      |
| LRPN-002       | CS201      |

Result: 2 requests are sent — one for `LRPN-001` (containing 2 courses), one for `LRPN-002`.

---

## Generated Files

After running Menu 1 (CLI) or completing Step 1 (GUI), the following files are created in the project root:

| File | Description |
|------|-------------|
| `config.json` | Stores the URL, method, headers, and mode configuration |
| `data_template.xlsx` | Excel template for data input |
| `data_template.csv` | CSV template for data input |
| `data_template.json` | JSON template for data input |

The files `data.xlsx`, `data.csv`, and `data.json` are also recognized as alternative data sources.

---

## Important Notes

- **Authentication tokens** are stored in `config.json`. Tokens can expire — if a 401 or 419 error occurs, restart from Step 1 with a fresh cURL command.
- **Do not share `config.json`** as it contains request headers and authentication tokens.
- For large numbers of requests, set a sufficient interval to avoid overloading the server (1–2 seconds minimum is recommended).
- Generated template files contain only one sample row — duplicate or add rows as needed.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Lint and format with Ruff
ruff check .
ruff format .
```

Linting configuration is defined in `pyproject.toml`.

---

## License

MIT License — free to use and modify.
