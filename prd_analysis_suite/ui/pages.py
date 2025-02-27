import streamlit as st
import pandas as pd
import re
from pathlib import Path
from utils.file_utils import process_file_with_agent
from utils.prd_optimizer import display_optimization_options
from agents.agent1_prd_analyzer import agent1_analyze_prd
from agents.agent2_test_generator import process_content_with_agent_for_testcases
from agents.agent3_bdd_generator import process_content_with_agent_for_bdd_gwt
from services.cache_service import get_cached_analysis, cache_analysis, get_cached_files, extract_version_from_filename
from models.data_models import PRDAnalysis
from utils.requirement_utils import ensure_requirement_ids
from ui.components import display_cached_file_contents, format_dataframe_for_display

# ----------------------------------------------------------------------
# Streamlit Pages
# ----------------------------------------------------------------------
def ux01_ingest_prd_page():
    """Page for ingesting and analyzing PRD files."""
    st.info("Ingest PRD/Requirements HTML File")
    uploaded_file = st.file_uploader("Upload PRD File", type=["html", "txt"])

    if uploaded_file is not None:
        st.write(f"File uploaded:", uploaded_file.name)

        # Extract version for better cache identification
        version = extract_version_from_filename(uploaded_file.name)
        # st.write(f"Detected version: {version}")

        # Read the file content once
        file_content = uploaded_file.read().decode(errors="replace")

        # Offer token optimization options
        optimized_content, was_optimized = display_optimization_options(file_content)

        # Create a temporary file-like object with the possibly optimized content
        import io
        temp_file = io.StringIO(optimized_content)
        temp_file.name = uploaded_file.name  # Keep the original name

        if st.button("Process PRD"):
            with st.spinner("Processing PRD with AI..."):
                # Create a clean cache key that doesn't include the file extension
                # or duplicate version information
                base_name = uploaded_file.name
                if "." in base_name:
                    base_name = base_name.split(".")[0]

                # Remove any existing version prefix if found
                base_name = re.sub(r'^[vV]\d+[_-]', '', base_name)

                # Create a clean cache filename: v{number}_prd
                clean_cache_name = f"{version}_prd"

                # Add optimization indicator if content was optimized
                if was_optimized:
                    clean_cache_name += "_optimized"

                success, message = process_file_with_agent(
                    file=temp_file,
                    client=st.session_state['client'],
                    agent_function=agent1_analyze_prd,
                    model_class=PRDAnalysis,
                    cache_filename=clean_cache_name  # Use clean name
                )

                if success:
                    # Cache the original file content with a consistent name
                    original_req_filename = f"{version}_original_requirements"
                    if was_optimized:
                        original_req_filename += "_optimized"
                    cache_analysis(original_req_filename, optimized_content)

                    if message != "Used cached analysis":
                        st.success(f"PRD processed successfully! {message}")

                    # Validate & fix requirement IDs
                    ensure_requirement_ids()

                    if 'current_analysis' in st.session_state:
                        st.subheader("Analysis Summary")
                        st.json(st.session_state['current_analysis'])
                else:
                    st.error(f"Failed to process PRD: {message}")

def ux02_show_pickle_contents_page():
    """Page for viewing cached analysis results."""
    return display_cached_file_contents(
        display_title=True,
        prd_files_only=False,
        stories_ac_only=False,
        prd_and_stories=False,
        table_only=False
    )

def ux03_generate_test_cases_page():
    """Page for generating test cases from user stories and acceptance criteria."""
    st.header("Generate Test Cases from User Stories & AC")

    result = display_cached_file_contents(
        display_title=True,
        prd_files_only=False,
        stories_ac_only=False,
        prd_and_stories=False,
        original_and_use_cases=True,
        table_only=False,
        filter_test_cases=True
    )
    if not result:
        return
    prd_source_html, usecases_ac = result

    if st.button("Expand Stories & AC into Tests"):
        with st.spinner("Generating Test Cases..."):
            success, message = process_content_with_agent_for_testcases(
                usecases_ac=usecases_ac,
                prd_source_html=prd_source_html,
                client=st.session_state['client']
            )
            if success:
                st.success(f"Test cases generated successfully! {message}")
                if 'current_analysis' in st.session_state:
                    st.subheader("Test Case Analysis")
                    st.json(st.session_state['current_analysis'])
            else:
                st.error(f"Failed to generate test cases: {message}")

def ux04_create_gwt_page():
    """Page for creating BDD Given-When-Then tests from test cases."""
    st.header("Create G-W-T BDD Tests")
    result = display_cached_file_contents(
        display_title=True,
        prd_files_only=False,
        stories_ac_only=False,
        prd_and_stories=False,
        original_and_use_cases=True,
        table_only=False,
        test_cases_only=True,
        filter_test_cases=False,
    )
    if not result:
        return
    prd_source_html, testcases_df = result

    if st.button("Generate Given-When-Then Python Code"):
        with st.spinner("Generating G-W-T Python BDD.."):
            success, message = process_content_with_agent_for_bdd_gwt(
                testcases_df=testcases_df,
                prd_source_html=prd_source_html,
                client=st.session_state['client']
            )
            if success:
                st.success(f"G-W-T BDD generated successfully! {message}")
                if 'current_analysis' in st.session_state:
                    st.subheader("LLM Response: BDD G-W-T Tests")
                    st.json(st.session_state['current_analysis'])
            else:
                st.error(f"Failed to generate G-W-T BDD: {message}")

def ux05_view_all_test_cases_page():
    """Page for viewing and merging all generated test cases across versions with detailed requirement info."""
    import pandas as pd
    import re
    import json
    from services.cache_service import get_cached_files, get_cached_analysis
    from config import CACHE_DIR
    from ui.components import format_acceptance_criteria, format_gwt_text
    import logging

    logger = logging.getLogger(__name__)

    st.header("All Generated Test Cases")

    # First, load all PRD files to get requirement details
    prd_files = [f for f in get_cached_files() if 'prd' in f.lower() and 'original' not in f.lower()]

    # Create a dictionary to store requirement details, indexed by requirement ID
    requirement_details = {}

    # Add debug option to see raw data
    show_raw_data = st.checkbox("Show raw data structure (for debugging)")

    # Load requirement data from PRD files
    for prd_file in prd_files:
        prd_cached_result = get_cached_analysis(prd_file)
        if not prd_cached_result:
            continue

        # Show raw PRD data for debugging if enabled
        if show_raw_data:
            with st.expander(f"Raw requirement data from {prd_file}"):
                if hasattr(prd_cached_result, 'analysis') and isinstance(prd_cached_result.analysis, dict):
                    st.json(prd_cached_result.analysis)
                elif isinstance(prd_cached_result, dict):
                    st.json(prd_cached_result)
                else:
                    st.write(str(prd_cached_result))

        # Extract requirement data from analysis
        req_data = None
        if hasattr(prd_cached_result, 'analysis') and isinstance(prd_cached_result.analysis, dict) and 'table' in prd_cached_result.analysis:
            req_data = prd_cached_result.analysis['table']
        elif isinstance(prd_cached_result, dict) and 'table' in prd_cached_result:
            req_data = prd_cached_result['table']

        if not req_data:
            continue

        # Process each requirement
        for req in req_data:
            req_id = req.get('ID', '')
            if not req_id:
                continue

            # Display raw requirement data for debugging if enabled
            if show_raw_data:
                with st.expander(f"Raw data for requirement {req_id}"):
                    st.json(req)

            # Handle both underscore and space versions of field names
            review_notes = req.get('Review Notes', req.get('Review_Notes', ''))
            story_category = req.get('Story Category', req.get('Story_Category', ''))
            document_name = req.get('Document Name', req.get('Document_Name', ''))
            review_date = req.get('Review Date', req.get('Review_Date', ''))
            acceptance_criteria = req.get('Acceptance Criteria', req.get('Acceptance_Criteria', []))

            # Store all requirement details
            requirement_details[req_id] = {
                'Story': req.get('Story', ''),
                'Story_Category': story_category,
                'Type': req.get('Type', ''),
                'Review_Notes': review_notes,  # Ensure we get this field
                'Document_Name': document_name,
                'Review_Date': review_date,
                'Requirement_Acceptance_Criteria': acceptance_criteria
            }

    # Get all test case files from cache (files with 'tc' in the name)
    tc_files = [f for f in get_cached_files() if 'tc' in f.lower()]

    if not tc_files:
        st.warning("No test case files found in cache!")
        return

    # Sort files by version number
    def extract_version(filename):
        match = re.search(r'v(\d+)', filename.lower())
        if match:
            return int(match.group(1))
        return 0

    tc_files.sort(key=extract_version)

    st.info(f"Found {len(tc_files)} test case files: {', '.join(tc_files)}")
    if requirement_details:
        st.info(f"Found {len(requirement_details)} requirement details for cross-referencing")
        if show_raw_data:
            with st.expander("Requirement IDs loaded"):
                st.write(list(requirement_details.keys()))
    else:
        st.warning("No requirement details found for cross-referencing. Test cases will not show requirement information.")

    # Load each file and extract test cases
    all_dataframes = []
    all_test_cases = {}

    # Define the columns we want to display and their order
    desired_columns = [
        'TC_ID', 'Test_Type', 'Test_Category', 'Requirement_ID',
        'Scenario_Name', 'Story', 'Story_Category', 'Type', 'Review_Notes',
        'Document_Name', 'Review_Date', 'Acceptance_Criteria', 'Requirement_Acceptance_Criteria', 'Version'
    ]

    for file in tc_files:
        cached_result = get_cached_analysis(file)
        if not cached_result:
            st.warning(f"Could not load file: {file}")
            continue

        # Extract version for labeling
        version = f"V{extract_version(file)}"

        # Show raw structure if debug is enabled
        if show_raw_data:
            with st.expander(f"Raw data structure for {file}"):
                # Try to display the structure in a readable way
                if hasattr(cached_result, 'model_dump'):
                    st.json(cached_result.model_dump())
                elif hasattr(cached_result, '__dict__'):
                    st.json(cached_result.__dict__)
                elif isinstance(cached_result, dict):
                    st.json(cached_result)
                else:
                    st.write(str(cached_result))

        # Try to extract test cases from different data structures
        test_cases_data = None

        # First check raw_response for data (often contains the most complete dataset)
        if hasattr(cached_result, 'raw_response'):
            try:
                # Try to extract table from raw_response
                raw_response = cached_result.raw_response
                if isinstance(raw_response, dict) and 'choices' in raw_response:
                    content = raw_response['choices'][0]['message']['content']
                    if isinstance(content, str):
                        content_json = json.loads(content)
                        if 'table' in content_json and isinstance(content_json['table'], list):
                            test_cases_data = content_json['table']
                            if show_raw_data:
                                st.success(f"Successfully extracted test cases from raw_response for {file}")
            except Exception as e:
                logger.error(f"Error extracting from raw_response: {e}")
                # Continue to next method if this fails
                pass

        # If not found in raw_response, check other places
        if not test_cases_data:
            # Check for direct 'table' attribute (TestCasesResult object)
            if hasattr(cached_result, 'table') and isinstance(cached_result.table, list):
                test_cases_data = cached_result.table
            # Check for 'table' key in dict
            elif isinstance(cached_result, dict) and 'table' in cached_result and isinstance(cached_result['table'], list):
                test_cases_data = cached_result['table']
            # Check for 'table' in analysis attribute
            elif hasattr(cached_result, 'analysis') and isinstance(cached_result.analysis, dict) and 'table' in cached_result.analysis:
                test_cases_data = cached_result.analysis['table']

        if not test_cases_data:
            st.warning(f"Could not find valid test case data in {file}")
            continue

        # Show first few test cases in raw form if debug is enabled
        if show_raw_data and test_cases_data:
            with st.expander(f"Sample test case data from {file}"):
                st.write("First test case:")
                st.json(test_cases_data[0] if test_cases_data else {})

        # Convert the test cases to a proper DataFrame with consistent structure
        rows = []
        for tc in test_cases_data:
            # Handle different formats of test case data
            row = {}

            if isinstance(tc, dict):
                # For dictionary objects, just copy the data
                row = tc.copy()
            elif hasattr(tc, '__dict__'):
                # For objects with __dict__, extract attributes
                row = tc.__dict__.copy()
            elif hasattr(tc, 'model_dump'):
                # For Pydantic models
                row = tc.model_dump()
            else:
                # Try to parse from string representation
                try:
                    tc_str = str(tc)
                    # Extract key-value pairs
                    pattern = r"(\w+)='([^']*)'"
                    matches = re.findall(pattern, tc_str)
                    row = {k: v for k, v in matches}
                except Exception as e:
                    logger.error(f"Could not parse test case: {tc} - {e}")
                    continue

            # Handle field name variations (with or without underscores)
            for field in ['Story Category', 'Review Notes', 'Document Name', 'Review Date', 'Acceptance Criteria']:
                underscore_field = field.replace(' ', '_')
                if field in row and underscore_field not in row:
                    row[underscore_field] = row[field]
                elif underscore_field in row and field not in row:
                    row[field] = row[underscore_field]

            # Add version
            row['Version'] = version

            # Ensure Acceptance_Criteria is in proper format (as a list)
            if 'Acceptance_Criteria' in row:
                ac_value = row['Acceptance_Criteria']

                # If it's a string representation of a list, parse it
                if isinstance(ac_value, str):
                    if ac_value.startswith('[') and ac_value.endswith(']'):
                        try:
                            # Try to parse as JSON
                            cleaned_str = ac_value.replace("'", '"')
                            row['Acceptance_Criteria'] = json.loads(cleaned_str)
                        except json.JSONDecodeError:
                            # Try regex approach if JSON parsing fails
                            try:
                                ac_items = re.findall(r'"([^"]*)"', ac_value)
                                if ac_items:
                                    row['Acceptance_Criteria'] = ac_items
                                else:
                                    ac_items = re.findall(r"'([^']*)'", ac_value)
                                    row['Acceptance_Criteria'] = ac_items
                            except:
                                # Keep as is if all parsing fails
                                pass
                    elif ac_value.startswith('Given') or ac_value.startswith('When') or ac_value.startswith('Then'):
                        # It's a single GWT string, convert to a list with one item
                        row['Acceptance_Criteria'] = [ac_value]

                # Ensure it's a list
                if not isinstance(row['Acceptance_Criteria'], list):
                    row['Acceptance_Criteria'] = [str(row['Acceptance_Criteria'])]
            else:
                # If acceptance criteria are missing, add empty list
                row['Acceptance_Criteria'] = []

            # Add requirement details if available
            req_id = row.get('Requirement_ID', '')
            if req_id and req_id in requirement_details:
                req_info = requirement_details[req_id]

                # Add requirement details to the row
                row.update(req_info)

                # Debug the requirement detail merging if enabled
                if show_raw_data:
                    with st.expander(f"Merging test case with requirement {req_id}"):
                        st.write("Original test case data:")
                        st.json(tc)
                        st.write("Requirement details being added:")
                        st.json(req_info)
                        st.write("Merged row:")
                        st.json(row)

            rows.append(row)

        if not rows:
            st.warning(f"No valid test cases found in {file}")
            continue

        # Create DataFrame with consistent columns
        df = pd.DataFrame(rows)

        # Show raw DataFrame if debugging
        if show_raw_data:
            with st.expander(f"Raw DataFrame for {file}"):
                st.write(f"DataFrame columns: {df.columns.tolist()}")
                st.dataframe(df)

        # Reorder and select columns that exist
        available_columns = [col for col in desired_columns if col in df.columns]
        df = df[available_columns]

        all_dataframes.append((version, df, cached_result))

        # Track test case IDs for duplicate detection
        if 'TC_ID' in df.columns:
            for tc_id in df['TC_ID']:
                if tc_id in all_test_cases:
                    all_test_cases[tc_id] = all_test_cases[tc_id] + 1
                else:
                    all_test_cases[tc_id] = 1

    if not all_dataframes:
        st.error("No valid test case data found in any files!")
        return

    # Merge all dataframes
    all_df_versions = [df for _, df, _ in all_dataframes]
    merged_df = pd.concat(all_df_versions, ignore_index=True)

    # Find duplicate TC_IDs
    duplicate_tc_ids = {tc_id: count for tc_id, count in all_test_cases.items() if count > 1}

    # Display duplicate warning if any found
    if duplicate_tc_ids:
        duplicates_to_show = list(duplicate_tc_ids.keys())[:5]
        st.warning(f"Found {len(duplicate_tc_ids)} duplicate TC_IDs across versions: {', '.join(duplicates_to_show)}{'...' if len(duplicate_tc_ids) > 5 else ''}")

    # Define a custom style for tables
    st.markdown("""
    <style>
    .dataframe-container {
        overflow-x: auto;
        max-width: 100%;
    }
    .dataframe {
        width: 100%;
        border-collapse: collapse;
    }
    .dataframe th {
        background-color: #f0f2f6;
        font-weight: bold;
        text-align: left;
        padding: 8px;
        border: 1px solid #ddd;
    }
    .dataframe td {
        padding: 8px;
        border: 1px solid #ddd;
        vertical-align: top;
    }
    .requirement-info {
        background-color: #f8f8ff;
        padding: 5px;
        border-left: 3px solid #007bff;
    }
    .review-notes {
        font-style: italic;
        color: #6c757d;
        padding: 3px;
        border-left: 3px solid #dc3545;
    }
    </style>
    """, unsafe_allow_html=True)

    # Display column selection
    st.subheader("Customize Display")

    # Get all available columns from the merged DataFrame
    all_available_columns = merged_df.columns.tolist()

    # Group columns into categories for easier selection
    column_groups = {
        "Test Case Details": ['TC_ID', 'Test_Type', 'Test_Category', 'Requirement_ID', 'Scenario_Name', 'Version'],
        "Requirement Details": ['Story', 'Story_Category', 'Type', 'Review_Notes', 'Document_Name', 'Review_Date'],
        "Acceptance Criteria": ['Acceptance_Criteria', 'Requirement_Acceptance_Criteria']
    }

    # Create selection for each group
    selected_columns = []
    for group, cols in column_groups.items():
        st.write(f"**{group}**")
        # Only offer columns that actually exist in the DataFrame
        available_group_cols = [col for col in cols if col in all_available_columns]
        default_selection = available_group_cols

        # Ensure Review_Notes is included in default selection
        if 'Review_Notes' in available_group_cols and 'Review_Notes' not in default_selection:
            default_selection.append('Review_Notes')

        selected_group_cols = st.multiselect(
            f"Select {group} to display",
            available_group_cols,
            default=default_selection  # Start with all columns selected
        )
        selected_columns.extend(selected_group_cols)

    # We always want TC_ID and Requirement_ID
    if 'TC_ID' not in selected_columns and 'TC_ID' in all_available_columns:
        selected_columns.insert(0, 'TC_ID')
    if 'Requirement_ID' not in selected_columns and 'Requirement_ID' in all_available_columns:
        selected_columns.insert(1, 'Requirement_ID')

    # Always ensure Review_Notes is included if available
    if 'Review_Notes' not in selected_columns and 'Review_Notes' in all_available_columns:
        selected_columns.append('Review_Notes')

    # Filter DataFrame to only show selected columns
    display_df = merged_df[[col for col in selected_columns if col in merged_df.columns]].copy()

    # Display merged dataframe with improved formatting
    with st.expander("📊 All Test Cases (Merged)", expanded=True):
        # Create a more readable HTML table
        html_table = "<div class='dataframe-container'><table class='dataframe'>"

        # Add header row
        html_table += "<tr>"
        for col in display_df.columns:
            html_table += f"<th>{col.replace('_', ' ')}</th>"
        html_table += "</tr>"

        # Add data rows
        for _, row in display_df.iterrows():
            html_table += "<tr>"
            for col in display_df.columns:
                cell_value = row[col]

                # Format Acceptance Criteria specially
                if col in ['Acceptance_Criteria', 'Requirement_Acceptance_Criteria']:
                    if isinstance(cell_value, list) and cell_value:
                        # Format each criterion with GWT styling
                        criteria_html = ""
                        for i, criterion in enumerate(cell_value):
                            if i > 0:
                                criteria_html += "<br><br>"
                            formatted = format_gwt_text(criterion) if criterion else ""
                            criteria_html += formatted
                        html_table += f"<td>{criteria_html}</td>"
                    else:
                        html_table += "<td>None</td>"
                # Format story with special styling
                elif col == 'Story' and cell_value:
                    html_table += f"<td><div class='requirement-info'>{cell_value}</div></td>"
                # Format Review Notes with special styling
                elif col == 'Review_Notes' and cell_value:
                    html_table += f"<td><div class='review-notes'>{cell_value}</div></td>"
                else:
                    # Convert everything else to string
                    html_table += f"<td>{str(cell_value)}</td>"
            html_table += "</tr>"

        html_table += "</table></div>"
        st.markdown(html_table, unsafe_allow_html=True)

        # Also provide a download option
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download All Test Cases as CSV",
            csv,
            "all_test_cases.csv",
            "text/csv",
            key='download-csv'
        )

    # Display individual version dataframes with tabs
    st.subheader("Test Cases by Version")

    # Create tabs for each version
    tabs = st.tabs([f"{version}" for version, _, _ in all_dataframes])

    # Fill each tab with content
    for i, (version, df, cached_result) in enumerate(all_dataframes):
        with tabs[i]:
            st.markdown(f"### Test Cases for {version}")

            # Filter DataFrame to only show selected columns
            version_display_df = df[[col for col in selected_columns if col in df.columns]].copy()

            # Create a more readable HTML table for this version
            html_table = "<div class='dataframe-container'><table class='dataframe'>"

            # Add header row
            html_table += "<tr>"
            for col in version_display_df.columns:
                if col != 'Version':  # Skip Version column since we're already in version tab
                    html_table += f"<th>{col.replace('_', ' ')}</th>"
            html_table += "</tr>"

            # Add data rows
            for _, row in version_display_df.iterrows():
                html_table += "<tr>"
                for col in version_display_df.columns:
                    if col != 'Version':  # Skip Version column
                        cell_value = row[col]

                        # Format Acceptance Criteria specially
                        if col in ['Acceptance_Criteria', 'Requirement_Acceptance_Criteria']:
                            if isinstance(cell_value, list) and cell_value:
                                # Format each criterion with GWT styling
                                criteria_html = ""
                                for i, criterion in enumerate(cell_value):
                                    if i > 0:
                                        criteria_html += "<br><br>"
                                    formatted = format_gwt_text(criterion) if criterion else ""
                                    criteria_html += formatted
                                html_table += f"<td>{criteria_html}</td>"
                            else:
                                html_table += "<td>None</td>"
                        # Format story with special styling
                        elif col == 'Story' and cell_value:
                            html_table += f"<td><div class='requirement-info'>{cell_value}</div></td>"
                        # Format Review Notes with special styling
                        elif col == 'Review_Notes' and cell_value:
                            html_table += f"<td><div class='review-notes'>{cell_value}</div></td>"
                        else:
                            # Convert everything else to string
                            html_table += f"<td>{str(cell_value)}</td>"
                html_table += "</tr>"

            html_table += "</table></div>"
            st.markdown(html_table, unsafe_allow_html=True)

            # Provide version-specific download
            csv = version_display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                f"Download {version} Test Cases as CSV",
                csv,
                f"{version}_test_cases.csv",
                "text/csv",
                key=f'download-csv-{version}'
            )

            # PRD Content button (not in an expander)
            if st.button(f"Show Original PRD Content for {version}", key=f"btn_prd_{version}"):
                prd_content = None
                if hasattr(cached_result, 'original_prd_content') and cached_result.original_prd_content:
                    prd_content = cached_result.original_prd_content
                elif isinstance(cached_result, dict) and 'original_prd_content' in cached_result:
                    prd_content = cached_result['original_prd_content']

                if prd_content:
                    st.markdown("### Original PRD Content")
                    st.markdown(prd_content, unsafe_allow_html=True)
                else:
                    st.warning("No original PRD content available")