import re
import time
import logging
from openai import OpenAI
import streamlit as st
from services.llm_client import perform_llm_analysis
from services.cache_service import get_cached_analysis, cache_analysis
from prompts.agent3_bdd_generate_gwt import bdd_system_prompt, bdd_user_prompt

logger = logging.getLogger(__name__)

def agent3_expand_into_bdd_gwt(prd_html: str, testcases_df: str, client: OpenAI) -> tuple[dict, dict, str]:
    """
    Expand the test cases into BDD Given-When-Then feature files.

    Args:
        prd_html: HTML content of the PRD
        testcases_df: Test cases dataframe as string
        client: OpenAI client

    Returns:
        tuple containing:
        - json_data: Parsed JSON response
        - raw_response: Full raw response
        - final_prompt: Combined prompt that was sent
    """
    st.info("Expanding Test Cases into BDD-Feature File...")

    system_prompt = bdd_system_prompt
    user_prompt = f"""
                {bdd_user_prompt}

                I will provide both the PRD and the Test Cases to use to ensure
                excellent coverage.
                PRD/Requirements as html:
                {prd_html}

                Generated Test Cases as a dataframe:
                {testcases_df}
                """

    return perform_llm_analysis(client, system_prompt, user_prompt)

def process_content_with_agent_for_bdd_gwt(
    testcases_df: str,
    prd_source_html: str,
    client: OpenAI,
) -> tuple[bool, str]:
    """
    Process content with BDD GWT generation agent.

    Args:
        testcases_df: Test cases dataframe as string
        prd_source_html: Source HTML of the PRD
        client: OpenAI client

    Returns:
        tuple containing:
        - success: True if processing was successful
        - message: Status message
    """
    try:
        timer_start = time.time()

        # Extract version number from testcases dataframe
        version_match = re.search(r"V\d+", str(testcases_df))
        version_number = version_match.group(0) if version_match else "V-UNKNOWN"

        # Create cache filename
        cache_filename = f"{version_number.lower()}_BDD"

        # Check if cached result exists
        cached_result = get_cached_analysis(cache_filename)
        if cached_result:
            msg = f"Using cached analysis for {cache_filename}"
            logger.info(msg)
            st.info(msg)
            st.session_state['current_analysis'] = cached_result
            return True, "Used cached analysis"

        # Process with agent
        logger.info("Processing with LLM agent: agent3_expand_into_bdd_gwt")
        analysis_dict, raw_response, prompt = agent3_expand_into_bdd_gwt(
            prd_html=prd_source_html,
            testcases_df=testcases_df,
            client=client
        )

        # Display debug information
        st.info("BDD Generation completed!")

        with st.expander("Generated BDD Features", expanded=True):
            if "feature_files" in analysis_dict:
                for feature_file in analysis_dict["feature_files"]:
                    st.subheader(feature_file.get("filename", "Feature File"))
                    st.code(feature_file.get("content", "No content"), language="gherkin")
            else:
                st.warning("No feature files generated")

        # Cache the result
        elapsed_time = time.time() - timer_start
        analysis_dict["timestamp"] = timer_start
        analysis_dict["elapsed_time"] = elapsed_time
        analysis_dict["original_prd_content"] = prd_source_html

        cache_analysis(cache_filename, analysis_dict)

        # Store analysis in session state
        st.session_state['current_analysis'] = analysis_dict

        return True, "Successfully processed with LLM agent (BDD-GWT)"

    except Exception as e:
        logger.error(f"Error processing content with agent: {e}")
        return False, str(e)