import json
import logging
import streamlit as st
from openai import OpenAI

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# LLM Client
# ----------------------------------------------------------------------
def get_llm_client(use_local: bool) -> OpenAI:
    """
    Return local or remote OpenAI client.

    Args:
        use_local: If True, uses a local LM Studio. Otherwise, uses OpenAI API.

    Returns:
        OpenAI client instance
    """
    if use_local:
        return OpenAI(base_url="http://host.docker.internal:45310/v1/")  # Adjust for LM Studio
    return OpenAI()

# ----------------------------------------------------------------------
# Generic LLM Call
# ----------------------------------------------------------------------
def perform_llm_analysis(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    show_prompt_in_expander: bool = True
) -> tuple[dict, dict, str]:
    """
    A generic helper to perform an LLM analysis with prompt/response logic.

    Args:
        client: OpenAI client instance
        system_prompt: System prompt for the LLM
        user_prompt: User prompt for the LLM
        show_prompt_in_expander: Whether to show the prompt in a Streamlit expander

    Returns:
        tuple containing:
        - json_data: Parsed JSON response
        - raw_response: Full raw response
        - final_prompt: Combined prompt that was sent
    """
    final_prompt = f"{system_prompt}\n\n{user_prompt}"

    if show_prompt_in_expander:
        with st.expander("Prompt sent to LLM", expanded=False):
            st.code(final_prompt)

    try:
        if st.session_state['use_local_llm']:
            logger.info('Using Local Phi4 LLM')
            response = client.chat.completions.create(
                model="phi4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "response": {"type": "string"}
                        },
                        "required": ["response"]
                    }
                }
            )
        else: #ASSUME GPT4
            logger.info('Using OpenAI GPT4')
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0
            )


        analysis_text = response.choices[0].message.content.strip() if response.choices else ""

        if not analysis_text:
            st.error("Empty response from LLM.")
            return {}, response.model_dump(), final_prompt

        # Improved error handling for JSON parsing
        try:
            # Check if response starts with HTML tags (common error case)
            if analysis_text.lstrip().startswith(("<!DOCTYPE", "<html", "<?xml")):
                st.error("Received HTML instead of JSON. This might indicate an API error or incorrect content.")
                logger.error(f"HTML content detected in JSON response: {analysis_text[:100]}...")

                # Return empty dict with error indication
                return {"error": "HTML content received instead of JSON"}, response.model_dump(), final_prompt

            json_data = json.loads(analysis_text)

        except json.JSONDecodeError as e:
            st.error(f"JSON parsing error: {e}")

            # Show a preview of the problematic content
            with st.expander("Failed Response Preview"):
                st.write(analysis_text[:500] + ("..." if len(analysis_text) > 500 else ""))

            # Create a fallback response with error information
            json_data = {
                "error": f"JSON parsing error: {str(e)}",
                "content_preview": analysis_text[:200] + ("..." if len(analysis_text) > 200 else "")
            }

            logger.error(f"Failed JSON Response: {analysis_text[:500]}...")

        return json_data, response.model_dump(), final_prompt

    except Exception as e:
        error_msg = f"Error in LLM request: {e}"
        logger.exception(error_msg)
        st.error(error_msg)
        return {"error": error_msg}, {}, final_prompt