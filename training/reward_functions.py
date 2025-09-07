import json
import re
from datetime import datetime
from typing import List
from .utils import extract_json, is_valid_date, is_valid_phone

def json_format_reward(prompts, completions, answer, **kwargs) -> List[float]:
    """
    1.0 if a JSON object could be parsed from the response,
    -1.0 if parsing failed.
    """
    scores: List[float] = []
    for response in completions:
        parsed = extract_json(response)
        if parsed is not None:
            scores.append(1.0)
        else:
            scores.append(-1.0)
    return scores

def name_check(prompts, completions, answer, **kwargs) -> List[float]:
    """
    - If Provider Name == "Information not found" -> 1.0
    - Else if Provider Name does NOT contain titles (Dr., , MD, etc.) -> 1.0
    - Else -> 0.0
    """
    scores: List[float] = []
    for response in completions:
        data = extract_json(response)
        if data is None:
            # Could not parse JSON -> treat as neutral/0.0 (you can change to penalty if desired)
            scores.append(0.0)
            continue

        provider_name = data.get("Provider Name")
        if provider_name is None:
            # Missing field -> treat as 0.0
            scores.append(0.0)
            continue

        pn = str(provider_name).strip()
        if pn == "Information not found":
            scores.append(0.5)
            continue

        name_l = pn.lower()
        # If title present, that's considered "bad" (per earlier semantics) -> 0.0
        if ("dr." in name_l) or (", md" in name_l) or (" m.d." in name_l) or (name_l.endswith(" md")):
            scores.append(0.5)
        else:
            scores.append(1.0)
    return scores

def date_check(prompts, completions, answer, **kwargs) -> List[float]:
    """
    For each response, evaluate Effective Date and Term Date separately but aggregate:
    - For each date field:
        - If "Information not found" -> +1
        - Else if valid DD/MM/YYYY -> +1
        - Else -> +0
    Final score for response = sum of both date-field scores (range 0..2)
    """
    scores: List[float] = []
    for response in completions:
        data = extract_json(response)
        if data is None:
            scores.append(0.0)
            continue

        curr_score = 0.0

        eff = data.get("Effective Date")
        if eff is None:
            # missing key -> 0
            curr_score += 0.0
        else:
            eff_s = str(eff).strip()
            if eff_s == "Information not found":
                curr_score += 1.0
            elif is_valid_date(eff_s):
                curr_score += 1.0
            else:
                curr_score += 0.0

        term = data.get("Term Date")
        if term is None:
            curr_score += 0.0
        else:
            term_s = str(term).strip()
            if term_s == "Information not found":
                curr_score += 1.0
            elif is_valid_date(term_s):
                curr_score += 1.0
            else:
                curr_score += 0.0

        scores.append(curr_score)
    return scores

def line_of_business_check(prompts, completions, answer, **kwargs) -> List[float]:
    """
    - If "Information not found" -> 1.0
    - Else if all comma-separated values are subset of allowed -> 1.0
    - Else -> 0.0
    """
    possible = {"Medicare", "Medicaid", "Commercial"}
    scores: List[float] = []
    for response in completions:
        data = extract_json(response)
        if data is None:
            scores.append(0.0)
            continue

        lob = data.get("Line Of Business")
        if lob is None:
            scores.append(0.0)
            continue

        lob_s = str(lob).strip()
        if lob_s == "Information not found":
            scores.append(1.0)
            continue

        parts = {p.strip() for p in lob_s.split(",") if p.strip()}
        if parts and parts.issubset(possible):
            scores.append(1.0)
        else:
            scores.append(0.0)
    return scores

def phone_number_check(prompts, completions, answer, **kwargs) -> List[float]:
    """
    - If Phone Number == "Information not found" -> 1.0
    - Else if valid format XXX-XXX-XXXX -> 1.0
    - Else -> 0.0
    """
    scores: List[float] = []
    for response in completions:
        data = extract_json(response)
        if data is None:
            scores.append(0.0)
            continue

        phone = data.get("Phone Number")
        if phone is None:
            scores.append(0.0)
            continue

        phone_s = str(phone).strip()
        if phone_s == "Information not found":
            scores.append(1.0)
        elif is_valid_phone(phone_s):
            scores.append(1.0)
        else:
            scores.append(0.0)
    return scores

def npi_format_check(prompts, completions, answer, **kwargs) -> List[float]:
    """
    - If Provider NPI == "Information not found" -> 1.0
    - Else if NPI has exactly 10 digits -> 1.0
    - Else -> 0.0
    """
    scores: List[float] = []
    for response in completions:
        data = extract_json(response)
        if data is None:
            scores.append(0.0)
            continue

        npi = data.get("Provider NPI")
        if npi is None:
            scores.append(0.0)
            continue

        npi_s = str(npi).strip()
        if npi_s == "Information not found":
            scores.append(1.0)
            continue

        npi_digits = re.sub(r"\D", "", npi_s)
        if len(npi_digits) == 10:
            scores.append(1.0)
        else:
            scores.append(0.0)
    return scores

def full_check(prompts, completions, answer, **kwargs) -> List[float]:
    scores: List[float] = []
    for response in completions :
        curr_score = 0
        data = extract_json(response)
        ans  = extract_json(answer[0])
        if data is None:
            curr_score = 0
            scores.append(0.0)
            continue
        for k in ans.keys():
            val = data.get(k)
            if val:
                if val == ans.get(k):
                    curr_score += 0.4
            else :
                curr_score += -0.5
        scores.append(curr_score)
    return scores
