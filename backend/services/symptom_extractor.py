import json
import anthropic
from langsmith import traceable
from config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a clinical symptom extraction engine.
Extract all symptoms and physical findings from the user's message.

Rules:
- Normalize to clean clinical terms (e.g. "my head is killing me" → "headache")
- Include duration and severity if mentioned (e.g. "severe headache for 3 days")
- Include negated symptoms prefixed with NO: (e.g. "no fever" → "NO:fever")
- Include body location when relevant (e.g. "pain in lower right abdomen")
- Ignore emotions, social context, and non-physical complaints
- Return ONLY a JSON object, no explanation, no markdown

Output format:
{
  "symptoms": ["symptom1", "symptom2"],
  "duration_notes": "e.g. symptoms started 2 days ago",
  "severity_notes": "e.g. pain rated 8/10",
  "raw_negations": ["NO:fever"]
}"""


@traceable(name="symptom-extractor")
def extract_symptoms(user_message: str, conversation_history: list = None) -> dict:
    """
    Extract structured symptoms from free-text user input.

    Args:
        user_message: The raw user input string.
        conversation_history: Optional list of prior messages for context.
                              Format: [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        {
            "symptoms": list[str],
            "duration_notes": str,
            "severity_notes": str,
            "raw_negations": list[str]
        }
    """
    messages = []

    # Include recent history for context (last 4 turns max)
    if conversation_history:
        messages.extend(conversation_history[-4:])

    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=messages
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if Claude wraps in ```json
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Graceful fallback — treat entire message as one symptom
        result = {
            "symptoms": [user_message[:100]],
            "duration_notes": "",
            "severity_notes": "",
            "raw_negations": []
        }

    # Guarantee all keys exist
    result.setdefault("symptoms", [])
    result.setdefault("duration_notes", "")
    result.setdefault("severity_notes", "")
    result.setdefault("raw_negations", [])

    return result


def get_all_positive_symptoms(extraction: dict) -> list[str]:
    """Return only the positive (non-negated) symptoms as a flat list."""
    return [s for s in extraction["symptoms"] if not s.startswith("NO:")]