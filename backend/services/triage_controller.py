"""
triage_controller.py
====================
4-state triage machine: GATHERING → NARROWING → CONCLUSION → POST_CONCLUSION

Key design principles:
- Python controls state transitions, never the LLM
- User profile is ALWAYS injected at system prompt level (anti-hallucination Layer 1)
- Negations explicitly listed in every prompt (anti-hallucination Layer 5)
- POST_CONCLUSION is strictly scoped — Claude explains THIS report only
- Graph-derived scores are presented as facts Claude cannot contradict (Layer 2)
- Location + local time injected into conclusion prompts for timing context
"""

import anthropic
from langsmith import traceable
from config import settings
from services.context_assembler import format_user_profile, format_graph_candidates

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ── State machine ─────────────────────────────────────────────────────────────
def determine_triage_state(
    all_symptoms:       list[str],
    graph_candidates:   list[dict],
    turn_count:         int,
    is_post_conclusion: bool = False
) -> str:
    """
    Pure Python state machine. Claude executes each state,
    but Python decides which state we're in.

    GATHERING       → need more symptoms (< 3 collected)
    NARROWING       → have symptoms, many candidates, need to differentiate
    CONCLUSION      → enough info to return ranked diagnoses
    POST_CONCLUSION → conclusion delivered, user asking follow-up questions
    """
    if is_post_conclusion:
        return "POST_CONCLUSION"
    if len(all_symptoms) < 3:
        return "GATHERING"
    if len(graph_candidates) > 5 and turn_count < 4:
        return "NARROWING"
    return "CONCLUSION"


# ── Profile block — injected into EVERY prompt ───────────────────────────────
def _profile_block(context: dict) -> str:
    """
    Builds the patient profile block injected into every system prompt.
    This is the primary anti-hallucination layer.
    Sex, age, conditions make Claude's reasoning patient-specific.
    """
    profile = context.get("user_profile")
    if not profile:
        return "⚠ Patient profile: not provided — reason conservatively."

    parts = []
    if profile.get("age"):
        parts.append(f"Age: {profile['age']}")
    if profile.get("sex"):
        parts.append(f"Sex: {profile['sex']}")
    if profile.get("blood_type"):
        parts.append(f"Blood type: {profile['blood_type']}")
    if profile.get("chronic_conditions"):
        parts.append(f"Chronic conditions: {', '.join(profile['chronic_conditions'])}")
    if profile.get("current_medications"):
        parts.append(f"Current medications: {', '.join(profile['current_medications'])}")
    if profile.get("allergies"):
        parts.append(f"Allergies: {', '.join(profile['allergies'])}")
    if profile.get("past_surgeries"):
        parts.append(f"Past surgeries: {', '.join(profile['past_surgeries'])}")

    profile_str = "\n".join(f"  {p}" for p in parts)
    return f"""PATIENT PROFILE (treat this as ground truth — do not contradict):
{profile_str}

CRITICAL: All reasoning must be consistent with this profile.
A male patient cannot have pregnancy-related conditions.
A patient on Warfarin has bleeding risk implications.
Allergies listed are absolute contraindications."""


def _symptom_block(context: dict) -> str:
    """Builds the symptom block with confirmed symptoms and explicit negations."""
    symptoms  = context["all_symptoms"]
    negations = context["extraction_detail"].get("negations", [])
    duration  = context["extraction_detail"].get("duration_notes", "")
    severity  = context["extraction_detail"].get("severity_notes", "")

    lines = [f"CONFIRMED SYMPTOMS: {', '.join(symptoms) if symptoms else 'none yet'}"]
    if negations:
        lines.append(f"EXPLICITLY DENIED (do NOT include in reasoning): {', '.join(negations)}")
    if duration:
        lines.append(f"Duration: {duration}")
    if severity:
        lines.append(f"Severity: {severity}")
    return "\n".join(lines)


def _location_time_block(context: dict) -> str:
    """
    Builds location + local time block injected into conclusion prompts.
    Helps Claude reason about symptom onset timing and geographic context.
    e.g. "chest pain started 2 hours ago" + local time = actual clock time for ER doctors.
    """
    lines = []
    if context.get("location_text"):
        lines.append(f"Patient location: {context['location_text']}")
    if context.get("local_time"):
        tz     = context.get("timezone", "")
        tz_str = f" ({tz})" if tz else ""
        lines.append(f"Consultation local time: {context['local_time']}{tz_str}")
    return "\n".join(lines) if lines else ""


# ── System prompts ─────────────────────────────────────────────────────────────
def _build_gathering_prompt(context: dict) -> str:
    return f"""You are MurphyBot, a careful medical triage assistant conducting a structured consultation.

{_profile_block(context)}

{_symptom_block(context)}

You need more information to begin differential diagnosis.
Ask ONE specific, targeted clinical question that will most help narrow the diagnosis.
Keep it conversational — like a doctor, not a form.
One question only. No bullet points. No preamble. No diagnosis speculation yet."""


def _build_narrowing_prompt(context: dict) -> str:
    graph_str  = format_graph_candidates(context["graph_candidates"])
    vector_ctx = context["vector_context"]

    return f"""You are MurphyBot, a careful medical triage assistant conducting a structured consultation.

{_profile_block(context)}

{_symptom_block(context)}

KNOWLEDGE GRAPH RESULTS (peer-reviewed PrimeKG data — treat as factual):
{graph_str}

CLINICAL REFERENCE:
{vector_ctx[:1500]}

You have several candidate conditions. Ask ONE question that best differentiates
between the top candidates. Focus on the symptom or sign that would most change
the ranking. Consider the patient profile above when choosing your question.
One question only. No bullet points. No preamble."""


def _build_conclusion_prompt(context: dict) -> str:
    graph_str     = format_graph_candidates(context["graph_candidates"])
    vector_ctx    = context["vector_context"]
    file_analysis = context.get("file_analysis", "")
    file_str      = f"\nUPLOADED FILE ANALYSIS:\n{file_analysis}" if file_analysis else ""
    loc_time_str  = _location_time_block(context)
    loc_str       = f"\nCONTEXT:\n{loc_time_str}" if loc_time_str else ""

    return f"""You are MurphyBot, a careful medical triage assistant delivering a consultation conclusion.

{_profile_block(context)}

{_symptom_block(context)}{file_str}{loc_str}

KNOWLEDGE GRAPH RESULTS (derived from peer-reviewed PrimeKG — these match ratios are factual scores, do not contradict them):
{graph_str}

CLINICAL REFERENCE:
{vector_ctx[:2000]}

Based on all gathered information, provide 2-4 ranked differential diagnoses.

For each diagnosis:
1. Condition name + confidence level derived from graph match ratio
2. Key symptoms from THIS patient supporting this diagnosis
3. Why it ranks above or below others given THIS patient's profile
4. Recommended next steps (tests, specialist, urgency)
5. Red flag symptoms requiring emergency care

IMPORTANT:
- All reasoning must respect the patient profile above
- Do not introduce conditions inconsistent with patient sex/age/history
- Denied symptoms listed above are NOT present — do not use them as evidence
- If local time is provided, factor symptom onset timing into urgency assessment
- Match ratios from the knowledge graph are ground truth scores

End with exactly: "This is not a medical diagnosis. Please consult a qualified doctor.\""""


def _build_post_conclusion_prompt(context: dict) -> str:
    """
    POST_CONCLUSION prompt — strictly scoped to explaining the report.
    Claude cannot introduce new diagnoses or speculate beyond the report.
    """
    graph_str     = format_graph_candidates(context["graph_candidates"])
    file_analysis = context.get("file_analysis", "")
    file_str      = f"\nUPLOADED FILE ANALYSIS:\n{file_analysis}" if file_analysis else ""
    loc_time_str  = _location_time_block(context)
    loc_str       = f"\nCONSULTATION CONTEXT:\n{loc_time_str}" if loc_time_str else ""
    mcp           = context.get("mcp_enrichment", {})

    mcp_lines = []
    if mcp.get("drugs"):
        drug_names = [d["name"] for d in mcp["drugs"] if d.get("name")]
        mcp_lines.append(f"Suggested medications: {', '.join(drug_names)}")
    if mcp.get("interactions"):
        for ix in mcp["interactions"]:
            mcp_lines.append(
                f"⚠ Drug interaction: {ix['drug_1']} + {ix['drug_2']} "
                f"[{ix['severity']}] — {ix['description']}"
            )
    if mcp.get("tests"):
        test_names = [t.get("test", "") for t in mcp["tests"][:3]]
        mcp_lines.append(f"Recommended tests: {', '.join(test_names)}")
    if mcp.get("guidelines", {}).get("guideline"):
        mcp_lines.append(
            f"Clinical guidelines ({mcp['guidelines']['source']}): "
            f"{mcp['guidelines']['guideline'][:300]}..."
        )

    mcp_str = "\n".join(mcp_lines) if mcp_lines else "MCP enrichment not available."

    return f"""You are MurphyBot, a medical consultation assistant in post-consultation mode.

{_profile_block(context)}

THIS CONSULTATION'S RESULTS:{loc_str}
{_symptom_block(context)}{file_str}

{graph_str}

ENRICHMENT DATA FROM THIS CONSULTATION:
{mcp_str}

The triage consultation is complete. The patient is asking follow-up questions
about their specific results above.

Your role now:
- Explain findings from THIS report in plain language
- Answer questions about the suggested medications, tests, or diagnoses above
- Help the patient understand what their results mean for THEM specifically
- Reference the patient profile and location/time context when relevant

STRICT BOUNDARIES:
- Do NOT introduce new diagnoses not in the report above
- Do NOT speculate beyond what the graph data and MCP enrichment shows
- Do NOT provide dosage instructions — direct to a doctor for that
- If asked something outside this report, say: "That's outside the scope of this consultation — please discuss with your doctor."
- Always remind that this is informational, not a clinical diagnosis

Be warm, clear, and patient. Use plain language, not jargon."""


# ── Main controller ───────────────────────────────────────────────────────────
@traceable(name="triage-controller")
def run_triage(
    context:            dict,
    turn_count:         int,
    is_post_conclusion: bool = False,
    mcp_enrichment:     dict = None
) -> dict:
    """
    Main triage controller.

    Args:
        context:            Output from context_assembler.assemble_context()
        turn_count:         Number of turns completed so far
        is_post_conclusion: True if conclusion already delivered this session
        mcp_enrichment:     MCP enrichment data to include in post-conclusion context

    Returns:
        {
            "state":         "GATHERING|NARROWING|CONCLUSION|POST_CONCLUSION",
            "response":      str,
            "is_conclusion": bool
        }
    """
    all_symptoms     = context["all_symptoms"]
    graph_candidates = context["graph_candidates"]
    history          = context["conversation_history"]

    if mcp_enrichment:
        context["mcp_enrichment"] = mcp_enrichment

    state = determine_triage_state(
        all_symptoms, graph_candidates, turn_count, is_post_conclusion
    )

    if state == "GATHERING":
        system_prompt = _build_gathering_prompt(context)
    elif state == "NARROWING":
        system_prompt = _build_narrowing_prompt(context)
    elif state == "CONCLUSION":
        system_prompt = _build_conclusion_prompt(context)
    else:
        system_prompt = _build_post_conclusion_prompt(context)

    messages = _build_messages(history, context["new_symptoms"])

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=messages
    )

    if not response.content or not response.content[0].text.strip():
        reply = "Could you tell me more about your symptoms?"
    else:
        reply = response.content[0].text.strip()

    return {
        "state":         state,
        "response":      reply,
        "is_conclusion": state == "CONCLUSION"
    }


def _build_messages(history: list[dict], new_symptoms: list[str]) -> list[dict]:
    """
    Build the messages array for Claude from Supabase history.
    Caps at last 10 messages. Guarantees valid user/assistant alternation.
    """
    messages = []
    for msg in history[-10:]:
        role    = msg.get("role", "")
        content = msg.get("content", "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    deduped = []
    for msg in messages:
        if deduped and deduped[-1]["role"] == msg["role"]:
            deduped[-1]["content"] += "\n" + msg["content"]
        else:
            deduped.append(msg)

    if deduped and deduped[0]["role"] == "assistant":
        deduped.pop(0)
    if deduped and deduped[-1]["role"] == "assistant":
        deduped.pop()
    if not deduped:
        symptom_str = ", ".join(new_symptoms) if new_symptoms else "some symptoms"
        deduped = [{"role": "user", "content": f"I have {symptom_str}"}]

    return deduped