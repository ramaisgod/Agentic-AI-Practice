# llm/gemini_service.py
import os
from google import genai
from core.logger import logger
from app_config import GEMINI_API_KEY


client = genai.Client(api_key=GEMINI_API_KEY)

# Masked API key log
try:
    masked_key = GEMINI_API_KEY[:4] + "****" if GEMINI_API_KEY else "None"
    logger.info("Gemini client initialized (API key=%s)", masked_key)
except Exception:
    logger.exception("Failed logging masked GEMINI_API_KEY")


def _preview(text: str, limit: int = 200) -> str:
    """Utility: safe preview for logging."""
    if not isinstance(text, str):
        return str(text)
    return text if len(text) <= limit else text[:limit] + "..."


def call_gemini_llm(prompt: str) -> str:
    logger.info("call_gemini_llm invoked")
    logger.debug("Prompt preview: %s", _preview(prompt))

    try:
        logger.info("Sending request to Gemini model: gemini-2.0-flash")
        response = client.models.generate_content(
            model="gemini-2.0-flash",  # gemini-2.0-flash, gemini-2.5-flash-lite
            contents=prompt,
        )

        # Log what response object contains
        try:
            logger.debug(
                "Gemini raw response object fields: has_text=%s, text_preview=%s",
                hasattr(response, "text"),
                _preview(getattr(response, "text", "")),
            )
        except Exception:
            logger.exception("Failed to log Gemini response preview")

        # Extract text
        result_text = response.text if hasattr(response, "text") else ""
        logger.info("Gemini request succeeded (response_length=%d)", len(result_text))

        return result_text

    except Exception as e:
        logger.error("Gemini model failed (%s). Falling back to LLaMA...", e)
        logger.debug("Exception details: ", exc_info=True)

        try:
            from llm.llama_service import call_llama_model
            return call_llama_model(prompt)
        except Exception:
            logger.exception("Fallback LLaMA model also failed")
            raise


def call_gemini_llm_streaming(prompt: str):
    logger.info("call_gemini_llm_streaming invoked")
    logger.debug("Streaming prompt preview: %s", _preview(prompt))

    try:
        logger.info("Initiating Gemini streaming request: gemini-2.0-flash")
        response_stream = client.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        for chunk in response_stream:
            try:
                text = chunk.text
                if text:
                    logger.debug("Streaming chunk received (len=%d)", len(text))
                    yield text
            except Exception:
                logger.exception("Error processing Gemini streaming chunk")

    except Exception as e:
        logger.error("Gemini streaming failed: %s", e)
        logger.debug("Streaming failure details:", exc_info=True)
        raise
