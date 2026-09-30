"""Reusable UI components for Bulk Insert Runner."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ui.state import reset_session

CSS_FILE = Path(__file__).resolve().parent.parent / "static" / "style.css"


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
                <p class="masthead-desc">
                    Dispatcher payload batch untuk otomasi dan replikasi request
                    API internal dari cURL.
                </p>
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
                    <div style="font-size: 0.72rem; color: #8b949e; margin-bottom: 6px;">
                        Status Sesi
                    </div>
                    <div style="display: flex; align-items: center; font-size: 0.84rem;
                                font-weight: 500; color: #34d399; margin-bottom: 6px;">
                        <span class="status-dot-active"></span> Config Siap
                    </div>
                    <div style="font-size: 0.75rem; color: #cbd5e1;
                                font-family: ui-monospace, monospace; overflow: hidden;
                                text-overflow: ellipsis; white-space: nowrap;">
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
                    <div style="font-size: 0.72rem; color: #8b949e; margin-bottom: 6px;">
                        Status Sesi
                    </div>
                    <div style="display: flex; align-items: center;
                                font-size: 0.84rem; color: #8b949e;">
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
