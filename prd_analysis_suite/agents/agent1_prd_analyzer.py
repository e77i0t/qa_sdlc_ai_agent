import time
import logging
from openai import OpenAI
import streamlit as st
from models.data_models import PRDAnalysis
from services.llm_client import perform_llm_analysis
from services.cache_service import cache_analysis
from prompts.agent1_analyze_prd import analysis_system_prompt, prd_analysis_prompt

logger = logging.getLogger(__name__)

def agent1_analyze_prd(content: str, client: OpenAI) -> tuple[dict, dict, str]:
    """
    Analyze PRD content using OpenAI (Agent #1).

    Args:
        content: PRD content to analyze
        client: OpenAI client

    Returns:
        tuple containing:
        - json_data: Parsed JSON response
        - raw_response: Full raw response
        - final_prompt: Combined prompt that was sent
    """
    system_prompt = analysis_system_prompt
    user_prompt = f""" {prd_analysis_prompt}
                    Here is the PRD:
                    {content}
                    """
    return perform_llm_analysis(client, system_prompt, user_prompt)

def process_prd_with_agent1(file, client: OpenAI) -> tuple[bool, str]:
    """
    Process a PRD file with Agent 1 (PRD Analyzer).

    Args:
        file: File-like object or path to process
        client: OpenAI client

    Returns:
        tuple containing:
        - success: True if processing was successful
        - message: Status message
    """
    try:
        timer_start = time.time()
        filename = file.name if hasattr(file, "name") else str(file)

        # Read content from the uploaded file-like object
        content = file.read().decode(errors="replace") if hasattr(file, "read") else file

        # Process with the agent
        logger.info(f"Processing PRD with analysis agent")
        analysis_dict, raw_response, prompt = agent1_analyze_prd(content, client)

        # Store the original content in the analysis_dict
        analysis_dict["original_prd_content"] = content

        elapsed_time = time.time() - timer_start

        # Create analysis object
        analysis_obj = PRDAnalysis(
            filename=filename,
            prompt=prompt,
            analysis=analysis_dict,
            raw_response=raw_response,
            timestamp=timer_start,
            elapsed_time=elapsed_time
        )

        # Cache the result
        cache_analysis(filename, analysis_obj)
        st.session_state['current_analysis'] = analysis_dict

        return True, "Successfully processed PRD with analysis agent"

    except Exception as e:
        logger.error(f"Error processing PRD with agent: {e}")
        return False, str(e)