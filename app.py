import streamlit as st
import logging
from ui.pages import (
    ux01_ingest_prd_page,
    ux02_show_pickle_contents_page,
    ux03_generate_test_cases_page,
    ux04_create_gwt_page
)
from services.llm_client import get_llm_client
from services.cache_service import get_cached_files, get_cached_analysis
from config import setup_logging

# Setup logging
logger = logging.getLogger(__name__)
setup_logging()

def main():
    """Main application entry point and UI organization."""
    st.set_page_config(page_title="PRD Analysis Suite", layout="wide")

    # Initialize session state
    if 'use_local_llm' not in st.session_state:
        st.session_state['use_local_llm'] = False
    if 'client' not in st.session_state:
        st.session_state['client'] = get_llm_client(st.session_state['use_local_llm'])
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 'ingest'

    # Auto-load the latest cached PRD
    cached_prds = get_cached_files()
    if cached_prds and 'current_analysis' not in st.session_state:
        latest_prd = cached_prds[-1]
        cached_result = get_cached_analysis(latest_prd)
        if cached_result:
            st.session_state['current_analysis'] = getattr(cached_result, 'analysis', {})
            st.session_state['current_prd'] = latest_prd
            st.success(f"Loaded latest cached PRD: {latest_prd}")

    # Main title
    st.title("PRD Analysis Suite")

    # Sidebar with navigation
    with st.sidebar:
        st.header("Settings")
        # st.session_state['use_local_llm'] = st.checkbox(
        #     "Use LM Studio (Local LLM)", value=st.session_state['use_local_llm']
        # )
        st.session_state['client'] = get_llm_client(st.session_state['use_local_llm'])

        # Navigation section
        st.header("Navigation")

        # Navigation buttons
        if st.button("📄 Ingest PRD", key="nav_ingest", use_container_width=True):
            st.session_state['current_page'] = 'ingest'
        if st.button("📝 View Payloads & Responses", key="nav_llm_interaction", use_container_width=True):
            st.session_state['current_page'] = 'llm-interact'
        if st.button("📝 Expand User Stories & AC", key="nav_stories", use_container_width=True):
            st.session_state['current_page'] = 'stories'
        if st.button("🔄 Create GWT", key="nav_gwt", use_container_width=True):
            st.session_state['current_page'] = 'gwt'

    # Page routing
    page = st.session_state['current_page']
    if page == 'ingest':
        ux01_ingest_prd_page()
    elif page == 'llm-interact':
        ux02_show_pickle_contents_page()
    elif page == 'stories':
        ux03_generate_test_cases_page()
    elif page == 'gwt':
        ux04_create_gwt_page()

if __name__ == "__main__":
    main()