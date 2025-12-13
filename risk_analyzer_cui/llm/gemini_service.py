import os
from google import genai
from .llama_service import call_llama_model


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def call_gemini(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


def call_gemini_llm_streaming(prompt: str):
    response = client.models.generate_content_stream(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    for chunk in response:
        text = chunk.text
        if text:
            yield text


def call_gemini_llm(prompt):
    try:
        return call_llama_model(prompt)
    except:
        return call_gemini(prompt)
