import requests

rapidapi_key = "f1d87746aemsh0b3225ffc9c75e8p108645jsn066ccdd26f5c"


def call_llama_model(prompt):
    url = "https://open-ai21.p.rapidapi.com/conversationllama"

    payload = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "web_access": False
    }

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "open-ai21.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("result")
    except Exception as e:
        print("LLaMA API Error:", e)
        return None
