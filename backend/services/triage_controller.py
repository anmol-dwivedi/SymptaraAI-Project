import anthropic
from langsmith import traceable
from config import settings
from services.context_assembler import format_user_profile, format_graph_candidates

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ── State determination (Python controls this — not the LLM) ─────────────────
def determine_triage_state(
    all_symptoms: list[str],
    graph_candidates: list[dict],
    turn_count: int
) -> str:
    """
    Pure Python state machine. Claude executes each state,
    but Python decides which state we're in.

    GATHERING  → need more symptoms
    NARROWING  → have symptoms, many candidates, need to differentiate
    CONCLUSION → enough info to return diagnoses
    """
    if len(all_symptoms) < 3:
        return "GATHERING"
    if len(graph_candidates) > 5 and turn_count < 4:
        return "NARROWING"
    return "CONCLUSION"


# ── System prompts for each state ─────────────────────────────────────────────
def _build_gathering_prompt(context: dict) -> str:
    profile = format_user_profile(context["user_profile"])
    symptoms = context["all_symptoms"]
    negations = context["extraction_detail"].get("negations", [])
    duration = context["extraction_detail"].get("duration_notes", "")
    severity = context["extraction_detail"].get("severity_notes", "")

    neg_str = f"\nReported absent: {', '.join(negations)}" if negations else ""
    dur_str = f"\nDuration: {duration}" if duration else ""
    sev_str = f"\nSeverity: {severity}" if severity else ""

    return f"""You are MurphyBot, a careful medical triage assistant.

{profile}
Symptoms collected so far: {', '.join(symptoms) if symptoms else 'none yet'}{neg_str}{dur_str}{sev_str}

You need more information to narrow down the diagnosis.
Ask ONE specific, targeted clinical question. Do not speculate or list diagnoses yet.
Keep it conversational — like a doctor, not a form.
One question only. No bullet points. No preamble."""


def _build_narrowing_prompt(context: dict) -> str:
    profile = format_user_profile(context["user_profile"])
    symptoms = context["all_symptoms"]
    graph_str = format_graph_candidates(context["graph_candidates"])
    vector_ctx = context["vector_context"]

    return f"""You are MurphyBot, a careful medical triage assistant.

{profile}
Symptoms: {', '.join(symptoms)}

{graph_str}

Clinical reference:
{vector_ctx[:1500]}

You have several candidate conditions. Ask ONE question that best differentiates
between the top candidates. Focus on the symptom or sign that would most change
the ranking. One question only. No bullet points. No preamble."""


def _build_conclusion_prompt(context: dict) -> str:
    profile = format_user_profile(context["user_profile"])
    symptoms = context["all_symptoms"]
    negations = context["extraction_detail"].get("negations", [])
    duration = context["extraction_detail"].get("duration_notes", "")
    severity = context["extraction_detail"].get("severity_notes", "")
    graph_str = format_graph_candidates(context["graph_candidates"])
    vector_ctx = context["vector_context"]
    file_analysis = context.get("file_analysis", "")

    neg_str = f"\nReported absent: {', '.join(negations)}" if negations else ""
    dur_str = f"\nDuration: {duration}" if duration else ""
    sev_str = f"\nSeverity: {severity}" if severity else ""
    file_str = f"\nUploaded file analysis:\n{file_analysis}" if file_analysis else ""

    return f"""You are MurphyBot, a careful medical triage assistant.

{profile}
Symptoms: {', '.join(symptoms)}{neg_str}{dur_str}{sev_str}{file_str}

{graph_str}

Clinical reference:
{vector_ctx[:2000]}

Based on all gathered information, provide 2-4 ranked differential diagnoses.

For each diagnosis:
1. Condition name + confidence level (High / Medium / Low)
2. Key symptoms supporting this diagnosis
3. What makes it rank above or below others
4. Recommended next steps (tests, specialist type, urgency)
5. Red flag symptoms that would require emergency care

End your response with exactly this line:
"This is not a medical diagnosis. Please consult a qualified doctor."

Be clear, structured, and clinically precise."""


# ── Main controller ───────────────────────────────────────────────────────────
@traceable(name="triage-controller")
def run_triage(
    context: dict,
    turn_count: int
) -> dict:
    """
    Main triage controller. Determines state, builds prompt, calls Claude.

    Args:
        context:     Output from context_assembler.assemble_context()
        turn_count:  Number of turns completed so far in this session

    Returns:
        {
            "state":    "GATHERING" | "NARROWING" | "CONCLUSION",
            "response": str,   ← Claude's message to show the user
            "is_conclusion": bool
        }
    """
    all_symptoms    = context["all_symptoms"]
    graph_candidates = context["graph_candidates"]
    history         = context["conversation_history"]

    # Python decides state
    state = determine_triage_state(all_symptoms, graph_candidates, turn_count)

    # Build the right system prompt
    if state == "GATHERING":
        system_prompt = _build_gathering_prompt(context)
    elif state == "NARROWING":
        system_prompt = _build_narrowing_prompt(context)
    else:
        system_prompt = _build_conclusion_prompt(context)

    # Build messages — include conversation history for continuity
    messages = _build_messages(history, context["new_symptoms"])

    # Call Claude
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages
    )

    # Safety check — handle empty response
    if not response.content or not response.content[0].text.strip():
        reply = "I need a bit more information. Could you describe your symptoms in more detail?"
    else:
        reply = response.content[0].text.strip()

    # reply = response.content[0].text.strip()

    return {
        "state":         state,
        "response":      reply,
        "is_conclusion": state == "CONCLUSION"
    }


def _build_messages(history: list[dict], new_symptoms: list[str]) -> list[dict]:
    """
    Build the messages array for Claude from Supabase history.
    Caps at last 10 messages to avoid context bloat.
    Guarantees at least one valid user message.
    """
    messages = []

    for msg in history[-10:]:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        # Skip empty content or invalid roles
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Ensure no two consecutive same-role messages (Claude API requirement)
    deduped = []
    for msg in messages:
        if deduped and deduped[-1]["role"] == msg["role"]:
            # Merge into previous
            deduped[-1]["content"] += "\n" + msg["content"]
        else:
            deduped.append(msg)

    # Must start with user role
    if deduped and deduped[0]["role"] == "assistant":
        deduped.pop(0)

    # Must end with user role
    if deduped and deduped[-1]["role"] == "assistant":
        deduped.pop()

    # Final fallback — if still empty, create a fresh user message
    if not deduped:
        symptom_str = ", ".join(new_symptoms) if new_symptoms else "some symptoms"
        deduped = [{"role": "user", "content": f"I have {symptom_str}"}]

    return deduped