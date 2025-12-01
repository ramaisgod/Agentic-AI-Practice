import os
from google import genai


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def call_gemini_llm(prompt: str) -> str:
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
