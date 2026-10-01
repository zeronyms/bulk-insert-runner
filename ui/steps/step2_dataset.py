"""Step 2: Dataset & Parameter Mapping view."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from core.data_handler import cast_cell_value, parse_uploaded_file
from ui.state import get_flattened_items, go_to_step, invalidate_editor


def render_step2() -> None:
    """Step 2 view: Target inspector, file ingestion, and interactive data table editor."""
    config: dict[str, Any] = st.session_state.config
    method = config.get("method", "POST")
    mode = config.get("mode", "standard").title()
    group_by = config.get("group_by") or "None"
    url_target = config.get("url", "")

    sample = config.get("sample_payload")
    sample_items = sample if isinstance(sample, list) else ([sample] if sample else [])
    sample_flat = get_flattened_items(sample_items) if sample_items else []
    sample_cols = list(sample_flat[0].keys()) if sample_flat else []

    if st.session_state.data_rows is None:
        st.session_state.data_rows = list(sample_flat)

    rows = st.session_state.data_rows
    method_class = f"method-{method.lower()}"

    group_tag = (
        f'<span class="meta-tag">Group by: <strong>{group_by}</strong></span>'
        if group_by != "None"
        else ""
    )
    header_count = len(config.get("headers", {}))

    st.markdown(
        f"""
        <div class="target-inspector">
            <div class="inspector-item">
                <span class="method-badge {method_class}">{method}</span>
                <span class="inspector-url">{url_target}</span>
            </div>
            <div class="inspector-meta">
                <span class="meta-tag">Mode: <strong>{mode}</strong></span>
                {group_tag}
                <span class="meta-tag">Terkonfigurasi: <strong>{len(rows)} baris</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(f"Header HTTP & URL Evaluasi ({header_count} header)", expanded=False):
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
        c_clear, c_reset, _ = st.columns([1.2, 1.4, 2.4])
        with c_clear:
            if st.button("Kosongkan Tabel", help="Hapus seluruh baris data pada tabel"):
                st.session_state.data_rows = []
                invalidate_editor()
                st.rerun()
        with c_reset:
            if st.button("Reset ke Sampel", help="Kembalikan tabel ke data sampel cURL"):
                st.session_state.data_rows = list(sample_flat)
                invalidate_editor()
                st.rerun()

    with col_upload:
        uploaded_file = st.file_uploader(
            "Impor file CSV atau Excel",
            type=["xlsx", "csv"],
            key="data_upload",
            label_visibility="collapsed",
        )
        if uploaded_file is None:
            st.session_state._upload_id = None
        elif uploaded_file.file_id != st.session_state.get("_upload_id"):
            st.session_state._upload_id = uploaded_file.file_id
            process_file_upload(uploaded_file, config)

    # Interactive Table Editor
    if rows:
        df = pd.DataFrame(rows)
    elif sample_cols:
        df = pd.DataFrame(columns=sample_cols)
    else:
        df = pd.DataFrame()

    template_row = rows[0] if rows else (sample_flat[0] if sample_flat else {})

    editor_key = f"data_editor_widget_{st.session_state.get('editor_version', 0)}"
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=editor_key,
    )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    col_back, _, col_next = st.columns([2, 3, 2])
    with col_back:
        if st.button("← Kembali ke Input cURL", use_container_width=True):
            go_to_step(1)
            st.rerun()
    with col_next:
        if st.button("Lanjut ke Preview Eksekusi →", type="primary", use_container_width=True):
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
        items = parse_uploaded_file(uploaded_file, fname, sample)

        if items:
            st.session_state.data_rows = get_flattened_items(items)
            invalidate_editor()
            st.success(f"Berhasil memuat {len(items)} baris data dari '{fname}'.")
            st.rerun()
        else:
            st.warning("File tidak memiliki baris data yang valid.")
    except Exception as err:
        st.error(f"Gagal membaca file: {err}")
