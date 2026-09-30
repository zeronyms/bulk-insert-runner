"""Step 3: Preview, Dispatch & Telemetry view."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests
import streamlit as st

from core.runner import build_execution_tasks
from ui.state import get_unflattened_rows, go_to_step, reset_session


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

    batch_sub = f"Array batch ({array_key})" if array_key else "Single item per request"

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
                <div class="spec-sub">{batch_sub}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Inspeksi Payload Request Pertama", expanded=True):
        if tasks:
            preview_url, _, preview_payload, preview_label = tasks[0]
            st.markdown(
                f"**Target URL**: `{preview_url}` &nbsp;&middot;&nbsp; **Label**: `{preview_label}`"
            )
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
            help=(
                "Atur jeda untuk mencegah rate limit (429 Too Many Requests) "
                "atau beban berlebih pada server."
            ),
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
        <div style="margin-top: 20px; margin-bottom: 8px; font-weight: 600;
                    font-size: 0.95rem; color: #f0f3f6;">
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
        <div style="margin-top: 24px; margin-bottom: 10px; font-weight: 600;
                    font-size: 0.95rem; color: #f0f3f6;">
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
