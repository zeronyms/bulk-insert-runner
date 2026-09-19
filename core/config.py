from pathlib import Path

CONFIG_FILE = Path("config.json")
EXCEL_TEMPLATE = Path("data_template.xlsx")
CSV_TEMPLATE = Path("data_template.csv")
JSON_TEMPLATE = Path("data_template.json")

DATA_FILE_CANDIDATES: list[Path] = [
    EXCEL_TEMPLATE,
    Path("data.xlsx"),
    CSV_TEMPLATE,
    Path("data.csv"),
    JSON_TEMPLATE,
    Path("data.json"),
]

WORKSPACE_CLEANUP_FILES: list[Path] = [
    CONFIG_FILE,
    EXCEL_TEMPLATE,
    Path("data.xlsx"),
    CSV_TEMPLATE,
    Path("data.csv"),
    JSON_TEMPLATE,
    Path("data.json"),
]
