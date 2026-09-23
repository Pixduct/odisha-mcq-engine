import json
import re
from typing import Dict, Any

def parse_ai_json_response(raw_text: str) -> Dict[str, Any]:
    """
    Robust JSON parser for LLM responses. Extracts JSON even if wrapped in markdown or contains control characters.
    """
    clean_text = raw_text.strip()
    
    # Strip thinking tags if present
    if "<think>" in clean_text and "</think>" in clean_text:
        clean_text = clean_text.split("</think>")[-1].strip()

    # Strip markdown codeblocks ```json ... ```
    if "```" in clean_text:
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_text, flags=re.DOTALL)
        if match:
            clean_text = match.group(1).strip()
        else:
            clean_text = re.sub(r'```[a-z]*', '', clean_text).replace('```', '').strip()

    # Find boundaries of first { and last }
    start = clean_text.find('{')
    end = clean_text.rfind('}')
    if start != -1 and end != -1 and end > start:
        clean_text = clean_text[start:end+1]

    try:
        return json.loads(clean_text, strict=False)
    except Exception:
        # Fallback: Replace unescaped newlines inside quotes
        fixed_text = re.sub(r'(?<=: ")(.*?)(?=",\s*"|"\s*})', lambda m: m.group(1).replace('\n', '\\n').replace('\r', ''), clean_text, flags=re.DOTALL)
        try:
            return json.loads(fixed_text, strict=False)
        except Exception:
            return {}
