"""Streamlit GUI for Universal Bulk Insert Runner.

A wizard-style interface:
  Step 1 - Paste cURL -> parse config
  Step 2 - Edit data table (inline) or upload Excel/CSV
  Step 3 - Preview payload, set interval, run & monitor
"""

from __future__ import annotations

import io
import json
import time
from typing import Any

import pandas as pd
import requests
import streamlit as st

from core.curl_parser import detect_array_wrapper, detect_url_id_candidates, parse_curl
from core.data_handler import (
    flatten_dict,
    format_template_str,
    group_items_for_request,
    load_csv_data,
    load_excel_data,
    unflatten_dict,
)

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Bulk Insert Runner",
    layout="wide",
)

# ─────────────────────────────────────────────
# Session state initialization
# ─────────────────────────────────────────────
DEFAULTS: dict[str, Any] = {
    "step": 1,
    "config": None,        # parsed config dict (url, method, headers, mode, array_key, group_by)
    "data_rows": None,     # list[dict] - the flat rows for the data editor
    "run_results": None,   # list[dict] - per-request results after run
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def reset_all() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def go_to(step: int) -> None:
    st.session_state.step = step


def _flatten_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [flatten_dict(item) for item in items]


def _unflatten_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [unflatten_dict(row) for row in rows]


# ─────────────────────────────────────────────
# Header / progress indicator
# ─────────────────────────────────────────────

def render_progress_indicator() -> None:
    step = st.session_state.step
    cols = st.columns(3)
    labels = ["1. Paste cURL", "2. Edit Data", "3. Run"]
    for i, (col, label) in enumerate(zip(cols, labels), start=1):
        with col:
            if i < step:
                st.success(label)
            elif i == step:
                st.info(f"**{label}**")
            else:
                st.markdown(
                    f"<div style='color:gray;text-align:center'>{label}</div>",
                    unsafe_allow_html=True,
                )
    st.divider()


# ─────────────────────────────────────────────
# STEP 1 - Paste & Parse cURL
# ─────────────────────────────────────────────

def step1_curl_input() -> None:
    st.header("Step 1 - Paste cURL Command")
    st.markdown(
        "Buka aplikasi di browser -> **Developer Tools (F12)** -> tab **Network** -> "
        "klik kanan request yang ingin di-bulk -> **Copy as cURL** -> paste di sini."
    )

    curl_input = st.text_area(
        "cURL Command",
        height=180,
        placeholder="curl 'https://example.com/api/items' -X POST -H 'Authorization: Bearer ...' --data-raw '{\"name\":\"test\"}'",
        key="curl_input_text",
    )

    if st.button("Parse cURL", type="primary", disabled=not curl_input.strip()):
        _do_parse_curl(curl_input.strip())


def _do_parse_curl(curl_input: str) -> None:
    try:
        parsed = parse_curl(curl_input)
    except ValueError as e:
        st.error(f"Gagal parse cURL: {e}")
        return

    if not parsed["sample_payload"]:
        st.warning(
            "JSON payload tidak ditemukan dalam cURL. "
            "Pastikan Anda meng-copy request POST/PUT yang memiliki body data."
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
        st.info(
            f"**Batch Payload Terdeteksi** - Key `{arr_key}` berisi array "
            f"{len(arr_items)} item. Mode Grouped akan aktif."
        )
        mode = "grouped"
        array_key = arr_key
        data_template = [dict(x) for x in arr_items]

    # Detect dynamic ID in URL
    referer_val = headers.get("Referer", "") or headers.get("referer", "")
    url_candidates = detect_url_id_candidates(url, referer_val)
    if url_candidates:
        cand_id, suggested_var = url_candidates[0]
        default_var = suggested_var or "id"

        st.info(f"**Dynamic ID Terdeteksi di URL**: `{cand_id}`")

        col1, col2 = st.columns([3, 1])
        with col1:
            var_name_input = st.text_input(
                "Nama kolom untuk ID ini di tabel data:",
                value=default_var,
                key="url_id_var_name",
            )
        with col2:
            keep_static = st.checkbox("Biarkan statis (jangan ganti)", key="url_id_static")

        if not keep_static and var_name_input:
            url = url.replace(cand_id, f"{{{var_name_input}}}")
            for h_key, h_val in headers.items():
                if cand_id in h_val:
                    headers[h_key] = h_val.replace(cand_id, f"{{{var_name_input}}}")
            group_by = var_name_input
            if data_template:
                data_template = [{var_name_input: cand_id, **row} for row in data_template]

    if not data_template:
        data_template = (
            sample_payload if isinstance(sample_payload, list) else [sample_payload]
        )

    config = {
        "url": url,
        "method": method,
        "headers": headers,
        "mode": mode,
        "array_key": array_key,
        "group_by": group_by,
        "sample_payload": sample_payload,
    }
    st.session_state.config = config
    st.session_state.data_rows = _flatten_items(data_template)
    st.session_state.run_results = None
    go_to(2)
    st.rerun()


# ─────────────────────────────────────────────
# STEP 2 - Edit Data
# ─────────────────────────────────────────────

def step2_data_editor() -> None:
    config: dict[str, Any] = st.session_state.config
    st.header("Step 2 - Isi Data")

    # Config summary
    with st.expander("Konfigurasi API", expanded=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("Method", config["method"])
        col2.metric("Mode", config["mode"].title())
        if config.get("group_by"):
            col3.metric("Group By", config["group_by"])
        st.code(config["url"], language=None)

    st.subheader("Data Tabel")
    st.markdown(
        "Edit langsung di tabel di bawah. Klik **+** untuk tambah baris, "
        "centang baris lalu klik ikon hapus untuk menghapus."
    )

    # Upload option
    uploaded = st.file_uploader(
        "Atau upload file Excel / CSV (opsional - akan mengganti data tabel)",
        type=["xlsx", "csv"],
        key="data_upload",
    )
    if uploaded is not None:
        _handle_upload(uploaded, config)

    # Data editor
    rows = st.session_state.data_rows or []
    df = pd.DataFrame(rows)
    if df.empty and config.get("sample_payload"):
        sample = config["sample_payload"]
        sample_items = sample if isinstance(sample, list) else [sample]
        df = pd.DataFrame(_flatten_items(sample_items))

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="data_editor_widget",
    )

    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("Kembali"):
            go_to(1)
            st.rerun()
    with col_next:
        if st.button("Lanjut ke Preview & Run", type="primary"):
            rows_out = edited_df.dropna(how="all").to_dict(orient="records")
            if not rows_out:
                st.warning("Data tabel kosong! Tambahkan minimal 1 baris data.")
            else:
                st.session_state.data_rows = rows_out
                go_to(3)
                st.rerun()


def _handle_upload(uploaded: Any, config: dict[str, Any]) -> None:
    try:
        sample = config.get("sample_payload")
        fname: str = uploaded.name
        if fname.endswith(".xlsx"):
            file_bytes = uploaded.read()
            items = load_excel_data(io.BytesIO(file_bytes), sample)  # type: ignore[arg-type]
        else:
            text = uploaded.read().decode("utf-8-sig")
            import tempfile, os
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
            ) as tmp:
                tmp.write(text)
                tmp_path = tmp.name
            try:
                items = load_csv_data(tmp_path, sample)
            finally:
                os.unlink(tmp_path)

        if items:
            st.session_state.data_rows = _flatten_items(items)
            st.success(f"Berhasil load {len(items)} baris dari '{fname}'.")
            st.rerun()
        else:
            st.warning("File kosong atau tidak ada baris data.")
    except Exception as e:
        st.error(f"Gagal membaca file: {e}")


# ─────────────────────────────────────────────
# STEP 3 - Preview & Run
# ─────────────────────────────────────────────

def step3_run() -> None:
    config: dict[str, Any] = st.session_state.config
    flat_rows: list[dict[str, Any]] = st.session_state.data_rows or []
    items = _unflatten_rows(flat_rows)

    st.header("Step 3 - Preview & Jalankan")

    mode = config.get("mode", "standard")
    array_key = config.get("array_key")
    group_by = config.get("group_by")

    # Summary
    with st.expander("Konfigurasi API", expanded=False):
        st.json(
            {
                "url": config["url"],
                "method": config["method"],
                "mode": mode,
                "array_key": array_key,
                "group_by": group_by,
            }
        )

    # Request preview
    st.subheader("Preview Request")
    if array_key:
        grouped = group_items_for_request(items, group_by, array_key)
        total_requests = len(grouped)
        st.info(
            f"**{len(items)} baris** akan dikelompokkan menjadi "
            f"**{total_requests} request** (Grouped Mode)."
        )
        if grouped:
            ctx0, payload0 = grouped[0]
            preview_url = format_template_str(config["url"], ctx0)
            st.markdown(f"**Contoh Request Pertama** - `{preview_url}`")
            st.json(payload0)
    else:
        total_requests = len(items)
        st.info(f"**{total_requests} request** akan dikirim (Standard Mode - 1 baris = 1 request).")
        if items:
            ex_item = items[0]
            preview_url = format_template_str(config["url"], ex_item) if "{" in config["url"] else config["url"]
            st.markdown(f"**Contoh Request Pertama** - `{preview_url}`")
            st.json(ex_item)

    st.divider()

    # Settings
    col_interval, col_timeout, _ = st.columns([2, 2, 4])
    with col_interval:
        interval = st.number_input(
            "Jeda antar request (detik)",
            min_value=0.0,
            max_value=60.0,
            value=2.0,
            step=0.5,
        )
    with col_timeout:
        timeout = st.number_input(
            "Timeout per request (detik)",
            min_value=5,
            max_value=120,
            value=30,
            step=5,
        )

    col_back, _, col_run = st.columns([1, 4, 2])
    with col_back:
        if st.button("Kembali ke Data"):
            go_to(2)
            st.rerun()
    with col_run:
        run_clicked = st.button(
            f"Jalankan {total_requests} Request",
            type="primary",
        )

    if run_clicked:
        _do_run(config, items, interval, int(timeout))


def _do_run(
    config: dict[str, Any],
    items: list[dict[str, Any]],
    interval: float,
    timeout: int,
) -> None:
    array_key = config.get("array_key")
    group_by = config.get("group_by")
    method = config["method"]
    headers = config["headers"]
    url = config["url"]

    # Build task list
    if array_key:
        grouped = group_items_for_request(items, group_by, array_key)
        tasks: list[tuple[str, dict[str, str], dict[str, Any], str]] = []
        for ctx, payload in grouped:
            req_url = format_template_str(url, ctx)
            req_headers = {k: format_template_str(v, ctx) for k, v in headers.items()}
            count = len(payload.get(array_key, []))
            if group_by and group_by in ctx:
                label = f"{group_by}={ctx[group_by]} ({count} item{'s' if count > 1 else ''})"
            else:
                label = f"Batch ({count} item{'s' if count > 1 else ''})"
            tasks.append((req_url, req_headers, payload, label))
    else:
        tasks = []
        for idx, item in enumerate(items, start=1):
            req_url = format_template_str(url, item) if "{" in url else url
            req_headers = {
                k: format_template_str(v, item) if "{" in v else v
                for k, v in headers.items()
            }
            label = (
                item.get("nama")
                or item.get("name")
                or item.get("kode")
                or item.get("code")
                or item.get("id")
                or f"Row #{idx}"
            )
            tasks.append((req_url, req_headers, item, str(label)))

    total = len(tasks)
    results: list[dict[str, Any]] = []
    stopped_early = False

    st.subheader("Progress")
    progress_bar = st.progress(0, text="Memulai...")
    log_container = st.container()

    session = requests.Session()

    for idx, (req_url, req_headers, req_payload, label) in enumerate(tasks, start=1):
        progress_bar.progress(
            (idx - 1) / total,
            text=f"[{idx}/{total}] Mengirim: {label}",
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

            status_label = "Berhasil" if resp.ok else "Gagal"
            with log_container:
                st.markdown(
                    f"**[{idx}/{total}]** `{label}` - **{resp.status_code}** ({status_label})"
                )

            if resp.status_code in (401, 419):
                st.error(
                    "Session / CSRF token expired. Kembali ke Step 1 dan paste cURL baru."
                )
                results.append(result)
                stopped_early = True
                break

        except requests.RequestException as err:
            result["response"] = str(err)
            with log_container:
                st.markdown(f"**[{idx}/{total}]** `{label}` - Network Error: `{err}`")

        results.append(result)

        if idx < total and interval > 0:
            time.sleep(interval)

    progress_bar.progress(1.0, text="Selesai!" if not stopped_early else "Dihentikan.")
    st.session_state.run_results = results

    # Summary
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    st.divider()
    st.subheader("Hasil Akhir")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Dikirim", len(results))
    c2.metric("Berhasil", success_count)
    c3.metric("Gagal", fail_count)

    if results:
        df_results = pd.DataFrame(results)[["no", "label", "status_code", "success", "response"]]
        df_results.columns = ["No", "Label", "Status", "Sukses", "Response"]
        st.dataframe(df_results, use_container_width=True)

    if st.button("Mulai Ulang (Reset)"):
        reset_all()
        st.rerun()


# ─────────────────────────────────────────────
# Main layout
# ─────────────────────────────────────────────

def main() -> None:
    st.title("Universal Bulk Insert Runner")
    st.caption(
        "Kirim ratusan data ke API internal kantor tanpa harus input satu per satu."
    )
    render_progress_indicator()

    step = st.session_state.step

    if step == 1:
        step1_curl_input()
    elif step == 2:
        step2_data_editor()
    elif step == 3:
        step3_run()

    # Sidebar - always visible
    with st.sidebar:
        st.markdown("## Navigasi")
        if st.session_state.config:
            st.success("Config loaded")
            if st.button("Reset & Mulai Ulang"):
                reset_all()
                st.rerun()
        else:
            st.info("Paste cURL di Step 1 untuk memulai.")

        st.divider()
        st.markdown("### Panduan Singkat")
        st.markdown(
            """
1. Buka aplikasi di browser
2. Tekan **F12** -> tab **Network**
3. Lakukan 1 aksi (misal: tambah 1 data)
4. Klik kanan request -> **Copy as cURL**
5. Paste di Step 1
6. Isi data di tabel (Step 2)
7. Klik **Jalankan** (Step 3)
"""
        )


if __name__ == "__main__":
    main()
