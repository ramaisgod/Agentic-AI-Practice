import re
import json


def extract_json(text: str):
    # Find the first {...} block
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    json_str = match.group()

    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"Exception Raised in extract_json. {e}")
        return None
