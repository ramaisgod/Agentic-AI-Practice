# llm/openai_services.py

from openai import OpenAI
from app_config import OPENAI_API_KEY
from core.logger import logger


client = None

# Mask API key for logs
try:
    masked_key = OPENAI_API_KEY[:4] + "****" if OPENAI_API_KEY else "None"
    logger.info("Initializing OpenAI client (API key=%s)", masked_key)
    client = OpenAI(api_key=OPENAI_API_KEY)
except Exception:
    logger.exception("Failed initializing OpenAI client")


def _preview(text: str, limit: int = 200) -> str:
    """Safe prompt preview for logs."""
    if not isinstance(text, str):
        return str(text)
    return text if len(text) <= limit else text[:limit] + "..."


def call_openai_llm(prompt: str):
    logger.info("call_openai_llm invoked")
    logger.debug("Prompt preview: %s", _preview(prompt))

    if client is None:
        logger.error("OpenAI client is not initialized — cannot call OpenAI API.")
        return None

    try:
        logger.info("Sending request to OpenAI model: gpt-4.1")

        response = client.responses.create(
            model="gpt-4.1",
            input=prompt
        )

        # Log the structure of response
        try:
            logger.debug("OpenAI raw response object: %s", response)
        except Exception:
            logger.exception("Failed to log OpenAI response object")

        # Extract text output
        text_output = None
        try:
            # New unified OpenAI Responses API shape
            if hasattr(response, "output_text"):
                text_output = response.output_text
            elif hasattr(response, "text"):
                text_output = response.text
            else:
                text_output = str(response)
        except Exception:
            logger.exception("Failed extracting text from OpenAI response")

        logger.info("OpenAI call succeeded (len=%d)",
                    len(text_output) if isinstance(text_output, str) else 0)
        logger.debug("OpenAI response preview: %s", _preview(text_output))

        return text_output

    except Exception as e:
        logger.error("OpenAI LLM error: %s", e)
        logger.debug("Exception details:", exc_info=True)
        return None
