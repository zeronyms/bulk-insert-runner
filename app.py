"""Streamlit GUI for Universal Bulk Insert Runner.

A high-utility, precision batch runner for internal APIs:
  Step 1 - Capture & Parse cURL
  Step 2 - Dataset & Parameter Mapping
  Step 3 - Dispatch & Live Telemetry
"""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from core.curl_parser import detect_array_wrapper, detect_url_id_candidates, parse_curl
from core.data_handler import (
    cast_cell_value,
    flatten_dict,
    format_template_str,
    load_csv_data,
    load_excel_data,
    unflatten_dict,
)
import core.runner

if not hasattr(core.runner, "build_execution_tasks"):
    import importlib
    importlib.reload(core.runner)

from core.runner import build_execution_tasks

# ─────────────────────────────────────────────
# Page configuration & Constants
# ─────────────────────────────────────────────

CSS_FILE = Path(__file__).parent / "static" / "style.css"

st.set_page_config(
    page_title="Bulk Insert Runner",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

STATE_DEFAULTS: dict[str, Any] = {
    "step": 1,
    "config": None,        # dict: url, method, headers, mode, array_key, group_by
    "data_rows": None,     # list[dict]: flattened rows for data editor
    "run_results": None,   # list[dict]: per-request telemetry results
    "_upload_id": None,
    "_extension_import_done": False,
}


# ─────────────────────────────────────────────
# State Management Helpers
# ─────────────────────────────────────────────

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


def get_flattened_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten nested dictionaries for table editing."""
    return [flatten_dict(item) for item in items]


def get_unflattened_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unflatten tabular rows back to nested payload objects."""
    return [unflatten_dict(row) for row in rows]


# ─────────────────────────────────────────────
# Theme & Static Assets
# ─────────────────────────────────────────────

@st.cache_data
def load_stylesheet() -> str:
    """Load external CSS stylesheet from disk."""
    if CSS_FILE.exists():
        return CSS_FILE.read_text(encoding="utf-8")
    return ""


def inject_custom_css() -> None:
    """Inject custom stylesheet into the Streamlit app."""
    css = load_stylesheet()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Extension Query Parameter Importer
# ─────────────────────────────────────────────

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

        st.query_params.clear()
        st.toast("Konfigurasi dari Browser Extension berhasil dimuat.", icon="✓")

    except Exception as err:
        st.warning(f"Gagal membaca konfigurasi extension: {err}")
        st.session_state._extension_import_done = True


# ─────────────────────────────────────────────
# Layout Components (Masthead & Pipeline)
# ─────────────────────────────────────────────

def render_masthead() -> None:
    """Render the top application masthead."""
    st.markdown(
        """
        <header class="app-masthead">
            <div class="masthead-main">
                <div class="masthead-title-row">
                    <span class="masthead-badge">v2.0</span>
                    <h1 class="masthead-title">Bulk Insert Runner</h1>
                </div>
                <p class="masthead-desc">Dispatcher payload batch untuk otomasi dan replikasi request API internal dari cURL.</p>
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_progress_pipeline() -> None:
    """Render the 3-step connected pipeline indicator."""
    step = st.session_state.step

    def get_state(i: int) -> tuple[str, str]:
        if i < step:
            return "completed", "✓"
        if i == step:
            return "active", str(i)
        return "pending", str(i)

    s1_state, s1_badge = get_state(1)
    s2_state, s2_badge = get_state(2)
    s3_state, s3_badge = get_state(3)

    st.markdown(
        f"""
        <div class="pipeline-bar">
            <div class="pipeline-step {s1_state}">
                <span class="pipeline-chip">{s1_badge}</span>
                <span>1. Input cURL</span>
            </div>
            <div class="pipeline-divider"></div>
            <div class="pipeline-step {s2_state}">
                <span class="pipeline-chip">{s2_badge}</span>
                <span>2. Data & Parameter</span>
            </div>
            <div class="pipeline-divider"></div>
            <div class="pipeline-step {s3_state}">
                <span class="pipeline-chip">{s3_badge}</span>
                <span>3. Eksekusi & Monitoring</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# STEP 1: Capture & Parse cURL
# ─────────────────────────────────────────────

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
                <li>Lakukan 1 kali submit data sampel pada form web untuk menangkap request di tab <strong>Network</strong>.</li>
                <li>Klik kanan pada request (POST / PUT), pilih <strong>Copy &rarr; Copy as cURL</strong>, lalu tempelkan di bawah.</li>
            </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )

    curl_input = st.text_area(
        "Script cURL",
        height=180,
        placeholder="curl 'https://api.internal/v1/resource' -X POST -H 'Authorization: Bearer ...' --data-raw '{\"name\":\"sample\"}'",
        key="curl_input_text",
        label_visibility="collapsed",
    )

    col_btn, _ = st.columns([2, 5])
    with col_btn:
        if st.button("Ekstrak & Validasi cURL", type="primary", disabled=not curl_input.strip()):
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
        data_template = (
            sample_payload if isinstance(sample_payload, list) else [sample_payload]
        )

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
    go_to_step(2)
    st.rerun()


# ─────────────────────────────────────────────
# STEP 2: Dataset & Parameter Mapping
# ─────────────────────────────────────────────

def render_step2() -> None:
    """Step 2 view: Target inspector, file ingestion, and interactive data table editor."""
    config: dict[str, Any] = st.session_state.config
    method = config.get("method", "POST")
    mode = config.get("mode", "standard").title()
    group_by = config.get("group_by") or "None"
    url_target = config.get("url", "")
    rows = st.session_state.data_rows or []

    method_class = f"method-{method.lower()}"

    st.markdown(
        f"""
        <div class="target-inspector">
            <div class="inspector-item">
                <span class="method-badge {method_class}">{method}</span>
                <span class="inspector-url">{url_target}</span>
            </div>
            <div class="inspector-meta">
                <span class="meta-tag">Mode: <strong>{mode}</strong></span>
                {f'<span class="meta-tag">Group by: <strong>{group_by}</strong></span>' if group_by != "None" else ""}
                <span class="meta-tag">Terkonfigurasi: <strong>{len(rows)} baris</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"Header HTTP & URL Evaluasi ({len(config.get('headers', {}))} header)", expanded=False):
        st.code(url_target, language=None)
        st.json(config.get("headers", {}))

    # Ingestion Toolbar
    col_title, col_upload = st.columns([3, 2])
    with col_title:
        st.markdown(
            """
            <div style="font-size: 0.92rem; font-weight: 600; color: #f0f3f6; margin-bottom: 2px;">
                Tabel Data Payload
            </div>
            <div style="font-size: 0.8rem; color: #8b949e; margin-bottom: 8px;">
                Edit sel secara langsung, tambah baris dengan tombol (+), atau impor dari file.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_upload:
        uploaded_file = st.file_uploader(
            "Impor file CSV atau Excel",
            type=["xlsx", "csv"],
            key="data_upload",
            label_visibility="collapsed",
        )
        if uploaded_file is not None and uploaded_file.file_id != st.session_state.get("_upload_id"):
            st.session_state._upload_id = uploaded_file.file_id
            process_file_upload(uploaded_file, config)

    # Interactive Table Editor
    df = pd.DataFrame(rows)
    if df.empty and config.get("sample_payload"):
        sample = config["sample_payload"]
        sample_items = sample if isinstance(sample, list) else [sample]
        df = pd.DataFrame(get_flattened_items(sample_items))
    template_row = (rows or df.to_dict(orient="records") or [{}])[0]

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="data_editor_widget",
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    col_back, _, col_next = st.columns([2, 3, 2])
    with col_back:
        if st.button("← Kembali ke Input cURL"):
            go_to_step(1)
            st.rerun()
    with col_next:
        if st.button("Lanjut ke Preview Eksekusi →", type="primary"):
            cleaned = edited_df.dropna(how="all")
            cleaned = cleaned.astype(object).where(cleaned.notna(), None)
            rows_out = [
                {k: cast_cell_value(v, template_row.get(k)) for k, v in row.items()}
                for row in cleaned.to_dict(orient="records")
            ]
            if not rows_out:
                st.warning("Tabel data kosong. Tambahkan minimal 1 baris data sebelum melanjutkan.")
            else:
                st.session_state.data_rows = rows_out
                go_to_step(3)
                st.rerun()


def process_file_upload(uploaded_file: Any, config: dict[str, Any]) -> None:
    """Process an uploaded CSV or Excel file and load rows into session state."""
    try:
        sample = config.get("sample_payload")
        fname: str = uploaded_file.name
        if fname.endswith(".xlsx"):
            file_bytes = uploaded_file.read()
            items = load_excel_data(io.BytesIO(file_bytes), sample)  # type: ignore[arg-type]
        else:
            text = uploaded_file.read().decode("utf-8-sig")
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
            ) as tmp:
                tmp.write(text)
                tmp_path = tmp.name
            try:
                items = load_csv_data(tmp_path, sample)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        if items:
            st.session_state.data_rows = get_flattened_items(items)
            st.success(f"Berhasil memuat {len(items)} baris data dari '{fname}'.")
            st.rerun()
        else:
            st.warning("File tidak memiliki baris data yang valid.")
    except Exception as err:
        st.error(f"Gagal membaca file: {err}")


# ─────────────────────────────────────────────
# STEP 3: Preview, Dispatch & Telemetry
# ─────────────────────────────────────────────

def render_step3() -> None:
    """Step 3 view: Payload inspection, parameter tuning, live telemetry stream, and results."""
    config: dict[str, Any] = st.session_state.config
    flat_rows: list[dict[str, Any]] = st.session_state.data_rows or []
    items = get_unflattened_rows(flat_rows)

    mode = config.get("mode", "standard")
    array_key = config.get("array_key")
    group_by = config.get("group_by")
    url = config["url"]
    headers = config["headers"]

    # Pre-calculate tasks for inspection using core.runner
    tasks = build_execution_tasks(
        url=url,
        headers=headers,
        items=items,
        group_by=group_by,
        array_key=array_key,
    )
    total_requests = len(tasks)

    # Spec metrics grid
    st.markdown(
        f"""
        <div class="spec-grid">
            <div class="spec-card">
                <div class="spec-label">Total Baris Data</div>
                <div class="spec-value">{len(items)}</div>
                <div class="spec-sub">Entitas input dari tabel</div>
            </div>
            <div class="spec-card">
                <div class="spec-label">Request Terjadwal</div>
                <div class="spec-value">{total_requests}</div>
                <div class="spec-sub">Total panggilan HTTP keluar</div>
            </div>
            <div class="spec-card">
                <div class="spec-label">Strategi Payload</div>
                <div class="spec-value" style="font-size: 1.15rem;">{mode.title()}</div>
                <div class="spec-sub">{"Array batch (" + str(array_key) + ")" if array_key else "Single item per request"}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Inspeksi Payload Request Pertama", expanded=True):
        if tasks:
            preview_url, _, preview_payload, preview_label = tasks[0]
            st.markdown(f"**Target URL**: `{preview_url}` &nbsp;&middot;&nbsp; **Label**: `{preview_label}`")
            st.json(preview_payload)

    # Execution Parameters Box
    st.markdown(
        """
        <div class="workbench-panel" style="margin-top: 14px; padding: 14px 18px;">
            <div style="font-size: 0.88rem; font-weight: 600; color: #f0f3f6; margin-bottom: 8px;">
                Parameter Eksekusi
            </div>
        """,
        unsafe_allow_html=True,
    )

    col_interval, col_timeout, _ = st.columns([2, 2, 3])
    with col_interval:
        interval = st.number_input(
            "Jeda antar request (detik)",
            min_value=0.0,
            max_value=60.0,
            value=2.0,
            step=0.5,
            help="Atur jeda untuk mencegah rate limit (429 Too Many Requests) atau beban berlebih pada server.",
        )
    with col_timeout:
        timeout = st.number_input(
            "Batas timeout (detik)",
            min_value=5,
            max_value=120,
            value=30,
            step=5,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    col_back, _, col_run = st.columns([2, 3, 2])
    with col_back:
        if st.button("← Kembali ke Edit Data"):
            go_to_step(2)
            st.rerun()
    with col_run:
        run_clicked = st.button(
            f"Mulai Eksekusi ({total_requests} Request)",
            type="primary",
        )

    if run_clicked:
        execute_requests_stream(tasks, config["method"], interval, int(timeout))


def execute_requests_stream(
    tasks: list[tuple[str, dict[str, str], dict[str, Any], str]],
    method: str,
    interval: float,
    timeout: int,
) -> None:
    """Execute prepared HTTP tasks sequentially with live streaming telemetry."""
    total = len(tasks)
    results: list[dict[str, Any]] = []
    stopped_early = False

    st.markdown(
        """
        <div style="margin-top: 20px; margin-bottom: 8px; font-weight: 600; font-size: 0.95rem; color: #f0f3f6;">
            Log Telemetri Request
        </div>
        """,
        unsafe_allow_html=True,
    )
    progress_bar = st.progress(0, text="Menginisialisasi sesi HTTP...")
    log_container = st.container()

    session = requests.Session()

    for idx, (req_url, req_headers, req_payload, label) in enumerate(tasks, start=1):
        progress_bar.progress(
            (idx - 1) / total,
            text=f"Mengirim [{idx}/{total}]: {label}",
        )

        result: dict[str, Any] = {
            "no": idx,
            "label": label,
            "url": req_url,
            "status_code": None,
            "success": False,
            "response": "",
        }

        try:
            resp = session.request(
                method=method,
                url=req_url,
                headers=req_headers,
                json=req_payload,
                timeout=timeout,
            )
            result["status_code"] = resp.status_code
            result["success"] = resp.ok
            result["response"] = resp.text[:300]

            with log_container:
                status_class = "stream-status-ok" if resp.ok else "stream-status-err"
                status_text = f"{resp.status_code} {'OK' if resp.ok else 'ERR'}"

                st.markdown(
                    f"""
                    <div class="stream-row">
                        <div class="stream-row-left">
                            <span class="stream-idx">#{idx:02d}</span>
                            <span class="{status_class}">{status_text}</span>
                            <span class="stream-label">{label}</span>
                        </div>
                        <span class="stream-url">{req_url[:55]}...</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Auto-abort on authentication expiry
            if resp.status_code in (401, 419):
                st.error(
                    "Autentikasi kedaluwarsa (HTTP 401 / 419). "
                    "Harap perbarui cURL dengan session atau CSRF token yang masih aktif."
                )
                results.append(result)
                stopped_early = True
                break

        except requests.RequestException as err:
            result["response"] = str(err)
            with log_container:
                st.markdown(
                    f"""
                    <div class="stream-row">
                        <div class="stream-row-left">
                            <span class="stream-idx">#{idx:02d}</span>
                            <span class="stream-status-err">NET_ERR</span>
                            <span style="color: #f87171;">{label} — {err}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        results.append(result)

        if idx < total and interval > 0:
            time.sleep(interval)

    progress_bar.progress(1.0, text="Selesai." if not stopped_early else "Eksekusi dihentikan.")
    st.session_state.run_results = results

    # Render summary
    render_execution_summary(results)


def render_execution_summary(results: list[dict[str, Any]]) -> None:
    """Render completion metrics and data table for finished requests."""
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    st.markdown(
        f"""
        <div style="margin-top: 24px; margin-bottom: 10px; font-weight: 600; font-size: 0.95rem; color: #f0f3f6;">
            Hasil Eksekusi
        </div>
        <div class="spec-grid">
            <div class="spec-card">
                <div class="spec-label">Total Dikirim</div>
                <div class="spec-value">{len(results)}</div>
                <div class="spec-sub">Total request diproses</div>
            </div>
            <div class="spec-card" style="border-color: rgba(16, 185, 129, 0.4);">
                <div class="spec-label" style="color: #34d399;">Berhasil</div>
                <div class="spec-value" style="color: #34d399;">{success_count}</div>
                <div class="spec-sub">Status 2xx</div>
            </div>
            <div class="spec-card" style="border-color: rgba(239, 68, 68, 0.4);">
                <div class="spec-label" style="color: #f87171;">Gagal / Error</div>
                <div class="spec-value" style="color: #f87171;">{fail_count}</div>
                <div class="spec-sub">Non-2xx atau koneksi gagal</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if results:
        df_results = pd.DataFrame(results)[["no", "label", "status_code", "success", "response"]]
        df_results.columns = ["No", "Label", "Status Code", "Sukses", "Response Body"]
        st.dataframe(df_results, use_container_width=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    if st.button("Mulai Sesi Baru"):
        reset_session()
        st.rerun()


# ─────────────────────────────────────────────
# Sidebar Component
# ─────────────────────────────────────────────

def render_sidebar() -> None:
    """Render the application sidebar with session status and quick workflow guide."""
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand-box">
                <div class="sidebar-app-name">Bulk Insert Runner</div>
                <div class="sidebar-app-sub">HTTP Batch Automation Console</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        config = st.session_state.config
        if config:
            url_preview = config.get("url", "")
            method = config.get("method", "POST")
            total_rows = len(st.session_state.data_rows or [])
            st.markdown(
                f"""
                <div class="sidebar-status-box">
                    <div style="font-size: 0.72rem; color: #8b949e; margin-bottom: 6px;">Status Sesi</div>
                    <div style="display: flex; align-items: center; font-size: 0.84rem; font-weight: 500; color: #34d399; margin-bottom: 6px;">
                        <span class="status-dot-active"></span> Config Siap
                    </div>
                    <div style="font-size: 0.75rem; color: #cbd5e1; font-family: ui-monospace, monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        {method} {url_preview[:28]}...
                    </div>
                    <div style="font-size: 0.75rem; color: #8b949e; margin-top: 4px;">
                        Data: {total_rows} baris
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Reset Konfigurasi"):
                reset_session()
                st.rerun()
        else:
            st.markdown(
                """
                <div class="sidebar-status-box">
                    <div style="font-size: 0.72rem; color: #8b949e; margin-bottom: 6px;">Status Sesi</div>
                    <div style="display: flex; align-items: center; font-size: 0.84rem; color: #8b949e;">
                        <span class="status-dot-idle"></span> Menunggu cURL
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with st.expander("Panduan Alur Kerja", expanded=True):
            st.markdown(
                """
                **1. Capture via DevTools**
                - Buka browser &rarr; tekan <kbd>F12</kbd> &rarr; tab **Network**.
                - Submit 1 sample data pada form web target.
                - Klik kanan request &rarr; **Copy as cURL**.
                
                **2. Ekstrak & Mapping Data**
                - Tempel cURL di Step 1.
                - Sesuaikan nilai tabel atau unggah file Excel/CSV di Step 2.
                
                **3. Eksekusi Berjeda**
                - Tetapkan jeda antar request (misal 2 detik) untuk menjaga reliabilitas server.
                """,
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────
# Main Application Entrypoint
# ─────────────────────────────────────────────

def main() -> None:
    """Main application orchestrator."""
    init_session_state()
    inject_custom_css()
    handle_extension_import()

    render_masthead()
    render_progress_pipeline()

    step = st.session_state.step
    if step == 1:
        render_step1()
    elif step == 2:
        render_step2()
    elif step == 3:
        render_step3()

    render_sidebar()


if __name__ == "__main__":
    main()
