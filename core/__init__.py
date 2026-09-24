"""Core package for Bulk Insert Runner."""

from core.config import (
    CONFIG_FILE,
    CSV_TEMPLATE,
    DATA_FILE_CANDIDATES,
    EXCEL_TEMPLATE,
    JSON_TEMPLATE,
    WORKSPACE_CLEANUP_FILES,
)
from core.curl_parser import (
    detect_array_wrapper,
    detect_url_id_candidates,
    parse_curl,
)
from core.data_handler import (
    export_csv_template,
    export_excel_template,
    export_json_template,
    format_template_str,
    group_items_for_request,
    load_data_file,
)
from core.runner import build_execution_tasks, execute_bulk_requests, get_item_label

__all__ = [
    "CONFIG_FILE",
    "CSV_TEMPLATE",
    "DATA_FILE_CANDIDATES",
    "EXCEL_TEMPLATE",
    "JSON_TEMPLATE",
    "WORKSPACE_CLEANUP_FILES",
    "build_execution_tasks",
    "detect_array_wrapper",
    "detect_url_id_candidates",
    "execute_bulk_requests",
    "export_csv_template",
    "export_excel_template",
    "export_json_template",
    "format_template_str",
    "get_item_label",
    "group_items_for_request",
    "load_data_file",
    "parse_curl",
]
