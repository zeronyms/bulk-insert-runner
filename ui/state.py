"""Session state management and state helpers for Bulk Insert Runner."""

from __future__ import annotations

import base64
import json
from typing import Any

import streamlit as st

from core.data_handler import flatten_dict, unflatten_dict

STATE_DEFAULTS: dict[str, Any] = {
    "step": 1,
    "config": None,  # dict: url, method, headers, mode, array_key, group_by
    "data_rows": None,  # list[dict]: flattened rows for data editor
    "run_results": None,  # list[dict]: per-request telemetry results
    "_upload_id": None,
    "_extension_import_done": False,
    "editor_version": 0,
}


def init_session_state() -> None:
    """Ensure all expected session state variables are initialized."""
    for key, val in STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val


def reset_session() -> None:
    """Reset session state to initial defaults."""
    for key, val in STATE_DEFAULTS.items():
        st.session_state[key] = val


def go_to_step(step: int) -> None:
    """Transition to a specific wizard step."""
    st.session_state.step = step


def invalidate_editor() -> None:
    """Force Streamlit data_editor to re-render with fresh session data."""
    st.session_state.editor_version = st.session_state.get("editor_version", 0) + 1
    for k in list(st.session_state.keys()):
        if k.startswith("data_editor_widget"):
            del st.session_state[k]


def get_flattened_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested dictionaries for table editing."""
    return [flatten_dict(item) for item in items]


def get_unflattened_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unflatten tabular rows back to nested payload objects."""
    return [unflatten_dict(row) for row in rows]


def handle_extension_import() -> None:
    """Parse configuration passed from the browser extension via URL query param."""
    if st.session_state.get("_extension_import_done"):
        return

    encoded = st.query_params.get("bulk_config")
    if not encoded:
        return

    try:
        decoded = base64.b64decode(encoded.replace(" ", "+").encode()).decode("utf-8")
        config: dict[str, Any] = json.loads(decoded)

        if not config.get("url") or not config.get("method"):
            return

        config.setdefault("mode", "standard")
        config.setdefault("array_key", None)
        config.setdefault("group_by", None)
        config.setdefault("headers", {})
        config.setdefault("sample_payload", {})

        sample = config["sample_payload"]
        sample_items = sample if isinstance(sample, list) else [sample]

        st.session_state.config = config
        st.session_state.data_rows = get_flattened_items(sample_items)
        st.session_state.run_results = None
        st.session_state.step = 2
        st.session_state._extension_import_done = True
        st.session_state._upload_id = None
        invalidate_editor()

        st.query_params.clear()
        st.toast("Konfigurasi dari Browser Extension berhasil dimuat.", icon="✓")

    except Exception as err:
        st.warning(f"Gagal membaca konfigurasi extension: {err}")
        st.session_state._extension_import_done = True
