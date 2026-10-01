"""Step 1: Capture & Parse cURL view."""

from __future__ import annotations

from typing import Any

import streamlit as st

from core.curl_parser import detect_array_wrapper, detect_url_id_candidates, parse_curl
from ui.state import get_flattened_items, go_to_step, invalidate_editor


def render_step1() -> None:
    """Step 1 view: cURL command input and validation."""
    st.markdown(
        """
        <div class="workbench-panel">
            <div class="panel-header">
                <span class="panel-title">Capture Request HTTP</span>
                <span class="panel-meta">DevTools &rarr; Network &rarr; Copy as cURL</span>
            </div>
            <ol class="guide-steps">
                <li>Buka aplikasi web target di browser dan buka DevTools (<kbd>F12</kbd>).</li>
                <li>
                    Lakukan 1 kali submit data sampel pada form web untuk menangkap request di
                    tab <strong>Network</strong>.
                </li>
                <li>
                    Klik kanan pada request (POST / PUT), pilih
                    <strong>Copy &rarr; Copy as cURL</strong>, lalu tempelkan di bawah.
                </li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )

    curl_input = st.text_area(
        "Script cURL",
        height=180,
        placeholder=(
            "curl 'https://api.internal/v1/resource' -X POST -H 'Authorization: Bearer ...' "
            '--data-raw \'{"name":"sample"}\''
        ),
        key="curl_input_text",
        label_visibility="collapsed",
    )

    col_btn, _ = st.columns([2, 5])
    with col_btn:
        if st.button(
            "Ekstrak & Validasi cURL",
            type="primary",
            disabled=not curl_input.strip(),
            use_container_width=True,
        ):
            process_curl_input(curl_input.strip())


def process_curl_input(curl_cmd: str) -> None:
    """Parse cURL input, detect batch arrays & dynamic IDs, and transition to Step 2."""
    try:
        parsed = parse_curl(curl_cmd)
    except ValueError as err:
        st.error(f"Gagal mem-parse cURL: {err}")
        return

    if not parsed["sample_payload"]:
        st.warning(
            "JSON payload tidak ditemukan dalam perintah cURL. "
            "Pastikan Anda menyalin request method POST atau PUT yang memiliki data body."
        )
        return

    sample_payload: Any = parsed["sample_payload"]
    url: str = parsed["url"]
    headers: dict[str, str] = parsed["headers"]
    method: str = parsed["method"]

    # Detect grouped mode
    array_wrapper = detect_array_wrapper(sample_payload)
    mode = "standard"
    array_key: str | None = None
    group_by: str | None = None
    data_template: list[dict[str, Any]] = []

    if array_wrapper:
        arr_key, arr_items = array_wrapper
        mode = "grouped"
        array_key = arr_key
        data_template = [dict(x) for x in arr_items]

    # Detect dynamic ID in URL
    referer_val = headers.get("Referer", "") or headers.get("referer", "")
    url_candidates = detect_url_id_candidates(url, referer_val)
    if url_candidates:
        cand_id, suggested_var = url_candidates[0]
        default_var = suggested_var or "id"
        url = url.replace(cand_id, f"{{{default_var}}}")
        for h_key, h_val in headers.items():
            if cand_id in h_val:
                headers[h_key] = h_val.replace(cand_id, f"{{{default_var}}}")
        group_by = default_var
        if data_template:
            data_template = [{default_var: cand_id, **row} for row in data_template]

    if not data_template:
        data_template = sample_payload if isinstance(sample_payload, list) else [sample_payload]

    st.session_state.config = {
        "url": url,
        "method": method,
        "headers": headers,
        "mode": mode,
        "array_key": array_key,
        "group_by": group_by,
        "sample_payload": sample_payload,
    }
    st.session_state.data_rows = get_flattened_items(data_template)
    st.session_state.run_results = None
    st.session_state._upload_id = None
    invalidate_editor()
    go_to_step(2)
    st.rerun()
