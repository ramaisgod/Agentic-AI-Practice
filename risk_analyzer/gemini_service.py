import os
from google import genai


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def call_gemini_llm(prompt):
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt,
    )
    return response.text


