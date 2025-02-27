import time
import logging
import re
from pathlib import Path
from typing import Union, Any, Callable, Optional, BinaryIO, TextIO
import streamlit as st
from services.cache_service import cache_analysis, get_cached_analysis

logger = logging.getLogger(__name__)

def process_file_with_agent(
    file,
    client,
    agent_function: Callable,
    model_class: Any,
    cache_suffix: str = "",
    cache_filename: Optional[str] = None
) -> tuple[bool, str]:
    """
    Reads file content, checks cache, calls the specified agent_function if needed,
    stores the result in cache, and sets st.session_state['current_analysis'].

    Args:
        file: File-like object or path to process
        client: OpenAI client
        agent_function: Function to call for processing
        model_class: Class to instantiate with results
        cache_suffix: Optional suffix for cache filename
        cache_filename: Optional specific cache filename to use (overrides automatic naming)

    Returns:
        tuple containing:
        - success: True if processing was successful
        - message: Status message
    """
    try:
        timer_start = time.time()

        # Get filename from file object or path
        orig_filename = file.name if hasattr(file, "name") else str(file)

        # Determine cache filename
        if cache_filename:
            # Use the provided cache filename explicitly
            cache_file_key = cache_filename
        else:
            # Generate from the original filename
            cache_file_key = f"{orig_filename}{cache_suffix}"

        logger.info(f"Using cache key: {cache_file_key}")

        # Check cache first
        cached_result = get_cached_analysis(cache_file_key)
        if cached_result:
            msg = f"Using cached analysis for {cache_file_key}"
            logger.info(msg)
            st.info(msg)
            # Handle both object types (with .analysis attribute or direct dict)
            st.session_state['current_analysis'] = cached_result.analysis if hasattr(cached_result, "analysis") else cached_result
            return True, "Used cached analysis"

        # Read content from the uploaded file-like object, handling different types of file objects
        if isinstance(file, str):
            # It's a file path string
            content = Path(file).read_text()
        elif hasattr(file, "read"):
            # It's a file-like object
            if hasattr(file, "seek"):
                # Reset file pointer if possible
                file.seek(0)

            # Check if it's already a text stream (StringIO) or binary (BytesIO/FileIO)
            if hasattr(file, "encoding") or hasattr(file, "mode") and "b" not in file.mode:
                # It's a text stream, just read it
                content = file.read()
            else:
                # It's likely a binary stream, decode it
                try:
                    content = file.read().decode(errors="replace")
                except AttributeError:
                    # If .decode() fails, it might already be a string
                    content = file.read()
        else:
            # Fallback
            content = str(file)

        # Process with the agent
        logger.info(f"Processing with LLM agent: {agent_function.__name__}")
        analysis_dict, raw_response, prompt = agent_function(content, client)

        # Store the original content in the analysis_dict
        analysis_dict["original_prd_content"] = content

        elapsed_time = time.time() - timer_start

        # Create analysis object based on provided model class
        if hasattr(model_class, "__annotations__"):
            # Create with proper model class initialization
            analysis_obj = model_class(
                filename=orig_filename,
                prompt=prompt,
                analysis=analysis_dict,
                raw_response=raw_response,
                timestamp=timer_start,
                elapsed_time=elapsed_time
            )
        else:
            # Fallback to dict if model class is not a proper Pydantic model
            analysis_obj = {
                "filename": orig_filename,
                "prompt": prompt,
                "analysis": analysis_dict,
                "raw_response": raw_response,
                "timestamp": timer_start,
                "elapsed_time": elapsed_time
            }

        # Cache the result
        cache_analysis(cache_file_key, analysis_obj)
        st.session_state['current_analysis'] = analysis_dict

        return True, "Successfully processed with LLM agent"

    except Exception as e:
        logger.error(f"Error processing file with agent: {e}")
        st.exception(e)  # Show detailed error in Streamlit
        return False, str(e)