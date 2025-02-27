import re
import time
import logging
import json
from openai import OpenAI
import streamlit as st
import pandas as pd
from models.data_models import TestCasesResult
from services.llm_client import perform_llm_analysis
from services.cache_service import get_cached_analysis, cache_analysis
from prompts.agent2_expand_into_testcases import testcases_system_prompt, testcases_prompt

logger = logging.getLogger(__name__)

def is_html_content(text: str) -> bool:
    """
    Check if a string contains HTML content.

    Args:
        text: String to check

    Returns:
        True if content appears to be HTML
    """
    # Check for common HTML markers
    html_patterns = [
        r'<!DOCTYPE',
        r'<html',
        r'<body',
        r'<div',
        r'<p>',
        r'<h[1-6]>'
    ]

    if not isinstance(text, str):
        return False

    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in html_patterns)

def format_dataframe_for_prompt(df):
    """
    Format a pandas DataFrame into a string representation for inclusion in a prompt.

    Args:
        df: DataFrame to format

    Returns:
        String representation of the DataFrame
    """
    if isinstance(df, pd.DataFrame):
        # Convert DataFrame to a formatted string
        return df.to_string(index=True)
    elif isinstance(df, str):
        # Already a string, but check if it's HTML
        if is_html_content(df):
            return "Error: HTML content detected instead of DataFrame"
        return df
    else:
        # Try to convert to a string representation
        try:
            return str(df)
        except:
            return "Error: Could not convert data to string"

def agent2_expand_into_test_cases(prd_html: str, usecases_ac, client: OpenAI) -> tuple[dict, dict, str]:
    """
    Expand the user stories & acceptance criteria into test cases (Agent #2).

    Args:
        prd_html: HTML content of the PRD
        usecases_ac: User stories and acceptance criteria (DataFrame or string)
        client: OpenAI client

    Returns:
        tuple containing:
        - json_data: Parsed JSON response
        - raw_response: Full raw response
        - final_prompt: Combined prompt that was sent
    """
    # st.info("Expanding User Stories & AC into Test Cases...")

    # Validate input to make sure it's not HTML when it should be data
    if isinstance(usecases_ac, str) and is_html_content(usecases_ac):
        st.error("Error: Received HTML content instead of user stories data")
        return {"error": "Input appears to be HTML, not user stories data"}, {}, ""

    # Format the usecases_ac properly for the prompt
    formatted_usecases = format_dataframe_for_prompt(usecases_ac)

    # st.info("Preparing to send data to LLM...")
    # with st.expander("Debug DataFrame", expanded=False):
    #     st.write("DataFrame Type:", type(usecases_ac))
    #     if isinstance(usecases_ac, pd.DataFrame):
    #         st.write("DataFrame Shape:", usecases_ac.shape)
    #         st.write("DataFrame Columns:", usecases_ac.columns.tolist())
    #         st.dataframe(usecases_ac)
    #     st.write("Formatted Data Preview:", formatted_usecases[:500] + "..." if len(formatted_usecases) > 500 else formatted_usecases)

    # Customize the prompt to request the specific TC_ID format
    tc_format_instruction = """
    IMPORTANT: Test case IDs must follow this exact format: {Version}-REQ-{ReqNumber}-TC-{TestCaseNumber}
    For example: V1-REQ-001-TC-001, V2-REQ-005-TC-002, etc.
    - Version: Same as the requirement version (V1, V2, etc.)
    - ReqNumber: 3-digit requirement number from the requirement ID
    - TestCaseNumber: 3-digit sequential number starting with 001
    """

    system_prompt = testcases_system_prompt + tc_format_instruction
    user_prompt = f"""
                {testcases_prompt}

                {tc_format_instruction}

                I will provide both the PRD and the Usecases to use to ensure
                excellent test case coverage.
                PRD/Requirements as html:
                {prd_html}

                Generated Use Cases and Acceptance Criteria as a dataframe:
                {formatted_usecases}
                """

    return perform_llm_analysis(client, system_prompt, user_prompt)

def validate_cached_content(cached_result):
    """
    Validate that cached content is a proper test case structure and not HTML.

    Args:
        cached_result: Cached content to validate

    Returns:
        (is_valid, error_message)
    """
    # Check if result is None
    if cached_result is None:
        return False, "Cached result is None"

    # Check if the cached content is a string (might be HTML)
    if isinstance(cached_result, str):
        if is_html_content(cached_result):
            return False, "Cached result contains HTML, not valid test case data"
        return False, "Cached result is a string, not valid test case data"

    # Check if a proper TestCasesResult object
    if not hasattr(cached_result, 'table') and not isinstance(cached_result, dict):
        return False, "Cached result doesn't have required test case structure"

    # If it's a dict, check for required keys
    if isinstance(cached_result, dict):
        if 'table' not in cached_result and 'TestCases' not in cached_result:
            return False, "Cached result missing required keys (table or TestCases)"

    return True, ""

def fix_tc_id_format(tc_id, version_number):
    """
    Fix test case ID to follow the format V#-REQ-###-TC-###

    Args:
        tc_id: Original test case ID
        version_number: Version number (e.g., "V1")

    Returns:
        Fixed test case ID
    """
    # Check if it already follows the correct pattern
    if re.match(r'^V\d+-REQ-\d{3}-TC-\d{3}$', tc_id):
        return tc_id

    # Try to extract components
    req_match = re.search(r'(V\d+)-REQ-(\d+)', tc_id)
    if req_match:
        version = req_match.group(1)
        req_num = req_match.group(2).zfill(3)  # Ensure 3 digits

        # Extract TC number
        tc_match = re.search(r'TC-(\d+)', tc_id)
        if tc_match:
            tc_num = tc_match.group(1).zfill(3)  # Ensure 3 digits
            return f"{version}-REQ-{req_num}-TC-{tc_num}"

    # If parsing failed, create a fallback ID
    return f"{version_number}-REQ-001-TC-001"

def process_content_with_agent_for_testcases(
    usecases_ac,
    prd_source_html: str,
    client: OpenAI,
) -> tuple[bool, str]:
    """
    Process content with test case generation agent.

    Args:
        usecases_ac: User stories and acceptance criteria (DataFrame or string)
        prd_source_html: Source HTML of the PRD
        client: OpenAI client

    Returns:
        tuple containing:
        - success: True if processing was successful
        - message: Status message
    """
    try:
        timer_start = time.time()

        # Extract version number from usecases_ac dataframe
        version_match = None
        if isinstance(usecases_ac, pd.DataFrame):
            # Try to find version in the DataFrame indices or values
            df_str = usecases_ac.to_string()
            version_match = re.search(r"V\d+", df_str)
        else:
            version_match = re.search(r"V\d+", str(usecases_ac))

        version_number = version_match.group(0) if version_match else "V-UNKNOWN"

        # st.info(f"Detected version: {version_number}")

        # Create cache filename
        cache_filename = f"{version_number.lower()}_TC"

        # Check if cached result exists and validate it
        cached_result = get_cached_analysis(cache_filename)
        is_valid, error_msg = validate_cached_content(cached_result)

        if cached_result and is_valid:
            msg = f"Using cached analysis for {cache_filename}"
            logger.info(msg)
            st.info(msg)
            st.session_state['current_analysis'] = cached_result
            return True, "Used cached analysis"
        elif cached_result and not is_valid:
            logger.warning(f"Found invalid cached content: {error_msg}")

        # Check input data validity
        if isinstance(usecases_ac, str) and is_html_content(usecases_ac):
            error_msg = "User stories data appears to be HTML content, not valid data"
            st.error(error_msg)
            return False, error_msg

        # Process with agent
        logger.info("Processing with LLM agent: agent2_expand_into_test_cases")
        st.info("Sending data to LLM for processing...")

        analysis_dict, raw_response, prompt = agent2_expand_into_test_cases(
            prd_html=prd_source_html,
            usecases_ac=usecases_ac,
            client=client
        )

        # Check for errors in response
        if 'error' in analysis_dict:
            st.error(f"Error in LLM response: {analysis_dict['error']}")
            return False, f"LLM processing error: {analysis_dict['error']}"

        # Debug output if needed
        with st.expander("Debug LLM Output", expanded=False):
            st.subheader("Prompt")
            st.code(prompt)
            st.subheader("Analysis Dict")
            st.json(analysis_dict)
            st.subheader("Raw Response")
            st.json(raw_response)

        elapsed_time = time.time() - timer_start

        # Process table data to ensure all required fields exist
        table_data = analysis_dict.get("table", [])
        if not table_data:
            st.error("No table data found in LLM response")
            return False, "No test case data generated"

        processed_table = []

        for item in table_data:
            # Create a new item with all required fields
            processed_item = {
                "TC_ID": item.get("TC_ID", ""),
                "Test_Type": item.get("Test_Type", "Functional"),
                "Test_Category": item.get("Test_Category", "Base"),
                "Requirement_ID": item.get("Requirement_ID", "")
            }

            # Fix TC_ID format
            if processed_item["TC_ID"]:
                processed_item["TC_ID"] = fix_tc_id_format(processed_item["TC_ID"], version_number)

            # If Requirement_ID is missing, try to extract it from TC_ID
            if not processed_item["Requirement_ID"] and processed_item["TC_ID"]:
                tc_id = processed_item["TC_ID"]
                match = re.match(r"(V\d+-REQ-\d+)", tc_id)
                processed_item["Requirement_ID"] = match.group(1) if match else f"{version_number}-REQ-001"

            # Add required fields for TestCaseDetail model
            processed_item["Scenario_Name"] = item.get("Scenario_Name", item.get("Description", ""))
            processed_item["Story Category"] = item.get("Story Category", "")
            processed_item["Type"] = item.get("Type", "Functional")
            processed_item["Review Notes"] = item.get("Review Notes", "")
            processed_item["Document Name"] = item.get("Document Name", f"{version_number} PRD")
            processed_item["Review Date"] = item.get("Review Date", "")
            processed_item["Acceptance Criteria"] = item.get("Acceptance Criteria", [])

            # Add any additional fields from the original item
            for key, value in item.items():
                if key not in processed_item:
                    processed_item[key] = value

            processed_table.append(processed_item)

        # Replace the original table with the processed one
        analysis_dict["table"] = processed_table

        # Create TestCasesResult object with all necessary fields
        test_cases_obj = TestCasesResult(
            filename=f"{version_number}_TestCases",
            prompt=prompt,
            table=processed_table,  # Use the processed table
            test_cases=analysis_dict.get("TestCases", {}),
            assumptions=analysis_dict.get("Assumptions", {}),
            original_prd_content=prd_source_html,
            raw_response=raw_response,
            timestamp=timer_start,
            elapsed_time=elapsed_time
        )

        # Cache the result
        cache_analysis(cache_filename, test_cases_obj)

        # Store analysis in session state
        st.session_state['current_analysis'] = test_cases_obj

        return True, "Successfully processed with LLM agent (test-cases)"

    except Exception as e:
        logger.error(f"Error processing content with agent: {e}")
        st.exception(e)
        return False, str(e)