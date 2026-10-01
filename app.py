"""Streamlit GUI for Universal Bulk Insert Runner.

A high-utility, precision batch runner for internal APIs:
  Step 1 - Capture & Parse cURL
  Step 2 - Dataset & Parameter Mapping
  Step 3 - Dispatch & Live Telemetry
"""

from __future__ import annotations

import streamlit as st

from ui.components import (
    inject_custom_css,
    render_masthead,
    render_progress_pipeline,
    render_sidebar,
)
from ui.state import handle_extension_import, init_session_state
from ui.steps import render_step1, render_step2, render_step3

st.set_page_config(
    page_title="Bulk Insert Runner",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
