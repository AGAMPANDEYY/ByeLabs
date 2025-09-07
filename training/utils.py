import re
import json
import datetime
from typing import Optional, Dict, Any
from email import policy
from email.parser import BytesParser

def extract_json(response: str) -> Optional[Dict[str, Any]]:
    """
    Extract substring from first '{' to last '}' and try to json.loads it.
    Returns parsed dict or None on failure.
    """
    if not isinstance(response, str):
        return None
    start = response.find("{")
    end = response.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    substr = response[start:end+1]
    try:
        return json.loads(substr)
    except json.JSONDecodeError:
        return None
    

def write_json(responses, filename, emails):
    arr = []
    for output, email in zip(responses, emails):
        resp      = output.outputs[0].text
        json_resp = extract_json(resp)
        json_data = {
            "email" : email,
            "extracted_data" : json_resp
        }
        arr.append(json_data)
    with open(filename, "w") as file:
        file.write(json.dumps(arr, indent = 4))
    print(f"Wrote to {filename}")

def is_valid_date(date_str: str) -> bool:
    """DD/MM/YYYY strict format and valid calendar date."""
    try:
        datetime.strptime(date_str, "%d/%m/%Y")
        return True
    except (ValueError, TypeError):
        return False

def is_valid_phone(number: str) -> bool:
    """Strict XXX-XXX-XXXX format."""
    if not isinstance(number, str):
        return False
    pattern = r"^\d{3}-\d{3}-\d{4}$"
    return bool(re.fullmatch(pattern, number))