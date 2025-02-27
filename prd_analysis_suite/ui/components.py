import streamlit as st
import pandas as pd
import pickle
import logging
import re
import json
from services.cache_service import get_cached_files, get_cached_analysis
from config import CACHE_DIR

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# UI Helper Functions
# ----------------------------------------------------------------------
def format_gwt_text(text):
    """
    Format Given-When-Then text with proper line breaks and indentation.

    Args:
        text: Text containing GWT statements

    Returns:
        Formatted HTML with proper indentation and line breaks
    """
    if not isinstance(text, str):
        return text

    # Format Given-When-Then pattern
    formatted = text

    # Replace 'Given' at start of text
    formatted = re.sub(r'^Given\s+', '<strong>Given</strong> ', formatted)

    # Replace 'When' in the middle of text
    formatted = re.sub(r'When\s+', '<br>&nbsp;&nbsp;&nbsp;<strong>When</strong> ', formatted)

    # Replace 'Then' in the middle of text
    formatted = re.sub(r'Then\s+', '<br>&nbsp;&nbsp;&nbsp;<strong>Then</strong> ', formatted)

    # Replace 'And' after Then
    formatted = re.sub(r'(Then[^<]+)And\s+', r'\1<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<strong>And</strong> ', formatted)

    return formatted

def format_acceptance_criteria(criteria):
    """
    Format acceptance criteria with proper GWT styling.

    Args:
        criteria: Single criterion or list of criteria

    Returns:
        Formatted HTML content
    """
    if isinstance(criteria, list):
        # Process each criterion in the list
        formatted_criteria = []
        for item in criteria:
            formatted_criteria.append(format_gwt_text(item))
        return "<br><br>".join(formatted_criteria)
    elif isinstance(criteria, str):
        # Process a single string
        return format_gwt_text(criteria)
    else:
        # Return unchanged if not string or list
        return criteria

def is_html_content(content: str) -> bool:
    """Check if a string appears to contain HTML content."""
    if not isinstance(content, str):
        return False
    return bool(re.search(r'<(?:html|body|div|p|h[1-6]|table|ul|ol)', content.lower()))

def format_prd_content(html_content: str) -> str:
    """
    Format PRD content for better display, including title extraction.

    Args:
        html_content: HTML content of the PRD

    Returns:
        Formatted content with proper title
    """
    # Clean up title duplication
    if html_content:
        # Extract title from content if possible
        title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1)
            # Remove any HTML tags from title
            title = re.sub(r'<[^>]+>', '', title)

            # Create a cleaner display with the extracted title
            st.subheader(f"📄 {title}")

            # Return content without the title for display
            return html_content

    # If no title found, return original content
    return html_content

def display_html_in_expander(content, title="HTML Content", expanded=False):
    """
    Safely display HTML content in an expander.

    Args:
        content: Content to display
        title: Title for the expander
        expanded: Whether the expander should be expanded by default
    """
    if content and isinstance(content, str):
        with st.expander(title, expanded=expanded):
            st.markdown(content, unsafe_allow_html=True)

def extract_test_case_table_from_raw_response(raw_response):
    """
    Extract test case table data from raw response JSON.

    Args:
        raw_response: Raw response JSON from LLM

    Returns:
        DataFrame with test case data or None if extraction fails
    """
    try:
        # Handle both string and dict formats
        if isinstance(raw_response, str):
            try:
                raw_response = json.loads(raw_response)
            except:
                # If not valid JSON, try to extract JSON part
                json_match = re.search(r'({[\s\S]*})', raw_response)
                if json_match:
                    try:
                        raw_response = json.loads(json_match.group(1))
                    except:
                        st.warning("Could not parse JSON from raw response string")
                        return None
                else:
                    return None

        # Navigate through response structure
        if isinstance(raw_response, dict):
            # Try different paths to find table data
            if "choices" in raw_response and isinstance(raw_response["choices"], list):
                choice = raw_response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]

                    # Content might be a JSON string
                    if isinstance(content, str):
                        try:
                            content_json = json.loads(content)
                            if "table" in content_json and isinstance(content_json["table"], list):
                                return pd.DataFrame(content_json["table"])
                        except:
                            # Try regex extraction if JSON parsing fails
                            table_match = re.search(r'"table"\s*:\s*(\[[\s\S]*?\])', content)
                            if table_match:
                                try:
                                    table_json = json.loads(table_match.group(1))
                                    return pd.DataFrame(table_json)
                                except:
                                    st.warning("Found table data but couldn't parse it")
                                    return None

        # Final fallback - look for any table array in the raw response
        raw_str = str(raw_response)
        table_match = re.search(r'"table"\s*:\s*(\[[\s\S]*?\])', raw_str)
        if table_match:
            try:
                table_json = json.loads(table_match.group(1))
                return pd.DataFrame(table_json)
            except:
                pass

        return None

    except Exception as e:
        logger.error(f"Error extracting test case table: {str(e)}")
        return None

def format_dataframe_for_display(df, has_gwt=False):
    """
    Format DataFrame for display with special handling for GWT content.

    Args:
        df: DataFrame to format
        has_gwt: Whether to apply GWT formatting

    Returns:
        HTML representation of the DataFrame
    """
    if not isinstance(df, pd.DataFrame):
        return ""

    df_copy = df.copy()

    # Apply GWT formatting if needed
    if has_gwt:
        # Check for acceptance criteria columns
        if "Acceptance Criteria" in df_copy.columns:
            df_copy["Acceptance Criteria"] = df_copy["Acceptance Criteria"].apply(format_acceptance_criteria)
        if "Acceptance_Criteria" in df_copy.columns:
            df_copy["Acceptance_Criteria"] = df_copy["Acceptance_Criteria"].apply(format_acceptance_criteria)

        # Check for GWT columns - with added safety check for non-string column names
        for col in df_copy.columns:
            # Convert column name to string before checking
            col_str = str(col)
            if any(kw in col_str.lower() for kw in ["given", "when", "then", "scenario"]):
                df_copy[col] = df_copy[col].apply(format_gwt_text)

    # Convert to HTML
    return df_copy.to_html(escape=False)

def display_table_only(analysis_dict, selected_file):
    """
    Displays only the table from `analysis_dict["analysis"]`.

    Args:
        analysis_dict: Dictionary containing analysis data
        selected_file: Selected file name

    Returns:
        Tuple of (selected_file, table_html_string)
    """
    # First display any HTML content in an expander
    if "original_prd_content" in analysis_dict:
        display_html_in_expander(
            analysis_dict["original_prd_content"],
            title="📄 Original PRD Content",
            expanded=False
        )

    if "analysis" in analysis_dict and isinstance(analysis_dict["analysis"], dict):
        data = analysis_dict["analysis"]
        if "table" in data:
            # Determine if this is likely a test case table
            is_test_case = any("tc" in selected_file.lower() for kw in ["tc", "test", "case"])

            df = pd.DataFrame(data["table"])
            if "ID" in df.columns:
                df = df.set_index("ID")

            with st.expander("📊 Requirements & Acceptance Criteria", expanded=True):
                st.markdown(format_dataframe_for_display(df, has_gwt=True), unsafe_allow_html=True)

            return (selected_file, df)
        else:
            st.warning("No 'table' key found in 'analysis' data.")
            return (selected_file, "")
    else:
        st.warning("No 'analysis' field or invalid data structure.")
        return (selected_file, "")

def display_original_and_use_cases(analysis_dict):
    """
    Displays the 'PRD' HTML from `analysis_dict["prompt"]` and
    also displays a table of use cases/acceptance criteria.

    Args:
        analysis_dict: Dictionary containing analysis data

    Returns:
        Tuple of (prd_from_prompt, usecases_df) or similar structure
    """
    # 1) Extract the Source HTML from the payload
    prd_from_prompt = ""
    if "original_prd_content" in analysis_dict:
        prd_from_prompt = analysis_dict["original_prd_content"]
        display_html_in_expander(prd_from_prompt, title="📄 PRD Content", expanded=False)
    elif "prompt" in analysis_dict and "Here is the PRD:" in analysis_dict["prompt"]:
        prd_from_prompt = analysis_dict["prompt"].split("Here is the PRD:", 1)[1].strip()
        display_html_in_expander(prd_from_prompt, title="📄 PRD Content", expanded=False)

    # 2) Build the Requirements DF
    usecases_df = None
    if "analysis" in analysis_dict and "table" in analysis_dict["analysis"]:
        try:
            table_data = analysis_dict["analysis"]["table"]
            if isinstance(table_data, list) and len(table_data) > 0:
                usecases_df = pd.DataFrame(table_data)
                if "ID" in usecases_df.columns:
                    usecases_df = usecases_df.set_index("ID")

                with st.expander("📊 LLM Generated Use Cases & AC", expanded=True):
                    st.markdown(format_dataframe_for_display(usecases_df, has_gwt=True), unsafe_allow_html=True)
            # else:
            #     st.warning("Table data is empty or not in expected format")
        except Exception as e:
            st.error(f"Error processing user stories data: {str(e)}")
            logger.error(f"DataFrame error: {str(e)}")
    elif "table" in analysis_dict:
        try:
            table_data = analysis_dict["table"]
            if isinstance(table_data, list) and len(table_data) > 0:
                tests_df = pd.DataFrame(table_data)
                if "TC_ID" in tests_df.columns:
                    tests_df = tests_df.set_index("TC_ID")

                with st.expander("📊 Test Cases", expanded=True):
                    st.markdown(format_dataframe_for_display(tests_df, has_gwt=True), unsafe_allow_html=True)
                return (analysis_dict.get('original_prd_content', ''), tests_df)
            else:
                st.warning("Test case data is empty or not in expected format")
        except Exception as e:
            st.error(f"Error processing test case data: {str(e)}")
            logger.error(f"DataFrame error: {str(e)}")
    else:
        st.warning(f"Could not find table data in analysis. Available keys: {analysis_dict.keys()}")

    return (prd_from_prompt, usecases_df)

def display_analysis_dict(analysis_dict, selected_file=""):
    """
    Generic fallback that displays each key/value from analysis_dict in expanders.

    Args:
        analysis_dict: Dictionary containing analysis data
        selected_file: Selected file name (for TC detection)

    Returns:
        String representation of analysis_dict
    """
    # Special handling for test case files
    if "tc" in selected_file.lower() and "raw_response" in analysis_dict:
        # Try to extract and display test case table
        tc_df = extract_test_case_table_from_raw_response(analysis_dict["raw_response"])
        if tc_df is not None and not tc_df.empty:
            # Found test case table, display it
            try:
                if "Acceptance_Criteria" in tc_df.columns:
                    tc_df["Acceptance_Criteria"] = tc_df["Acceptance_Criteria"].apply(format_acceptance_criteria)

                # Try to set index
                if "TC_ID" in tc_df.columns:
                    tc_df = tc_df.set_index("TC_ID")

                with st.expander("📊 Test Case Table from Raw Response", expanded=True):
                    st.markdown(format_dataframe_for_display(tc_df, has_gwt=True), unsafe_allow_html=True)
            except Exception as e:
                st.warning(f"Error formatting test case table: {str(e)}")

    # First check for HTML content in common fields
    if "original_prd_content" in analysis_dict:
        display_html_in_expander(
            analysis_dict["original_prd_content"],
            title="📄 Original PRD Content",
            expanded=False
        )
        # Remove to avoid duplicating in the loop below
        analysis_dict_display = {k: v for k, v in analysis_dict.items() if k != "original_prd_content"}
    else:
        analysis_dict_display = analysis_dict

    # Display other fields in expanders
    for key, value in analysis_dict_display.items():
        # Check if value might be HTML content
        if isinstance(value, str) and is_html_content(value):
            display_html_in_expander(value, title=f"📄 {key.capitalize()}", expanded=False)
        else:
            with st.expander(f"📜 {key.capitalize()}", expanded=False):
                if isinstance(value, (dict, list)):
                    st.json(value)
                else:
                    st.write(value)

    return str(analysis_dict)

def get_files(prd_files_only, stories_ac_only, prd_and_stories):
    """
    Helper to decide how to filter cached files.

    Args:
        prd_files_only: If True, only return PRD files
        stories_ac_only: If True, only return stories/AC files
        prd_and_stories: If True, return all files

    Returns:
        List of cached files
    """
    if prd_files_only:
        return get_cached_files(prd_files_only=True)
    elif stories_ac_only:
        return get_cached_files(stories_ac_only=True)
    elif prd_and_stories:
        return get_cached_files()
    else:
        return get_cached_files()

def safely_load_pickle(file_path):
    """
    Safely load a pickle file with error handling.

    Args:
        file_path: Path to the pickle file

    Returns:
        Loaded object or None if error
    """
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except (pickle.UnpicklingError, ModuleNotFoundError, AttributeError, ImportError, EOFError) as e:
        st.error(f"Error loading pickle file: {str(e)}")
        logger.error(f"Pickle error on {file_path}: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error loading file: {str(e)}")
        logger.error(f"Error on {file_path}: {str(e)}")
        return None

def display_cached_file_contents(
    prd_files_only=False,
    stories_ac_only=False,
    display_title=True,
    prd_and_stories=False,
    original_and_use_cases=False,
    table_only=False,
    test_cases_only=False,
    filter_test_cases=False
):
    """
    Allows user to select from cached files, displays their contents.

    Args:
        prd_files_only: If True, only show PRD files
        stories_ac_only: If True, only show stories/AC files
        display_title: If True, display the title
        prd_and_stories: If True, show all files
        original_and_use_cases: If True, display original content and use cases
        table_only: If True, only display the table
        test_cases_only: If True, only display test cases
        filter_test_cases: If True, filter out test case files

    Returns:
        Selected file and content or None
    """
    if display_title:
        st.header("View LLM Interaction, Original Payload ")

    # 1) Retrieve cached files
    files_to_display = get_files(prd_files_only, stories_ac_only, prd_and_stories)

    if filter_test_cases and not test_cases_only:  # Do not include TC files
        files_to_display = [item for item in files_to_display if "tc" not in item.lower()]
    elif not filter_test_cases and test_cases_only:  # Only display TC files
        files_to_display = [item for item in files_to_display if "tc" in item.lower()]

    if not files_to_display:
        st.warning("No cached files found!")
        return None

    # 2) Dropdown for selecting a file
    selected_file = st.selectbox("Select a file:", files_to_display)
    cache_path = CACHE_DIR / f"{selected_file}.pkl"

    if not cache_path.exists():
        st.error(f"Error: Cache file not found at {cache_path}")
        return None

    # 3) Load the analysis object from cache - with improved error handling
    analysis = safely_load_pickle(cache_path)

    if analysis is None:
        st.error(f"Could not load cached file: {selected_file}.pkl")

        # Offer recovery options
        if st.button("View raw file content"):
            try:
                with open(cache_path, 'rb') as f:
                    content = f.read()
                    st.code(f"File size: {len(content)} bytes")

                    # Try to show first 100 bytes as hex
                    preview = content[:100].hex()
                    st.code(f"Hex preview: {preview}")
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

        return None

    # 4) Convert to dict (via `model_dump()` or fallback)
    analysis_dict = {}

    # Handle different object types
    if hasattr(analysis, "model_dump"):
        # Pydantic model
        analysis_dict = analysis.model_dump()
    elif isinstance(analysis, dict):
        # Already a dict
        analysis_dict = analysis
    elif isinstance(analysis, str):
        # Plain string content - check if it's HTML
        if is_html_content(analysis):
            display_html_in_expander(analysis, title="📄 File Content", expanded=False)
        else:
            with st.expander("📄 File Content", expanded=False):
                st.markdown(analysis, unsafe_allow_html=True)
        return (selected_file, analysis)
    else:
        # Try to convert to dict or display raw
        try:
            analysis_dict = vars(analysis)
        except:
            # Handle as string content
            content = str(analysis)
            if is_html_content(content):
                display_html_in_expander(content, title="📄 File Content", expanded=False)
            else:
                with st.expander("📄 File Content", expanded=False):
                    st.markdown(content, unsafe_allow_html=True)
            return (selected_file, content)

    if not analysis_dict:
        st.warning("No structured data found in the cached file.")
        content = str(analysis)
        display_html_in_expander(content, title="📄 Raw Content", expanded=False)
        return (selected_file, content)

    # 5) Handle different display modes
    if table_only:
        return display_table_only(analysis_dict, selected_file)

    if original_and_use_cases:
        return display_original_and_use_cases(analysis_dict)

    if test_cases_only:
        return display_original_and_use_cases(analysis_dict)

    # Default: display each key/val in expanders
    dict_str = display_analysis_dict(analysis_dict, selected_file)
    return (selected_file, dict_str)