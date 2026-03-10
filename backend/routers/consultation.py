# from fastapi import APIRouter

# router = APIRouter()

# @router.get("/profile/health")
# def profile_health():
#     return {"status": "profile router health"}


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.context_assembler import assemble_context
from services.triage_controller import run_triage
from services.memory_service import (
    create_session, save_message, get_history,
    conclude_session, supabase
)

router = APIRouter()


class ConsultationRequest(BaseModel):
    user_id:              str
    session_id:           str | None = None   # None = start new session
    message:              str
    accumulated_symptoms: list[str] = []
    turn_count:           int = 0
    file_analysis:        str | None = None   # Claude vision output if file uploaded


class ConsultationResponse(BaseModel):
    session_id:           str
    state:                str                 # GATHERING | NARROWING | CONCLUSION
    response:             str
    is_conclusion:        bool
    all_symptoms:         list[str]
    graph_candidates:     list[dict]
    turn_count:           int


@router.post("/message", response_model=ConsultationResponse)
async def consultation_message(req: ConsultationRequest):
    """
    Single endpoint for the entire consultation flow.

    Client sends message + accumulated state.
    Server returns response + updated state.
    Client stores accumulated_symptoms and turn_count between turns.
    """

    # ── Session management ────────────────────────────────────────────────────
    if req.session_id:
        # Verify session exists
        result = supabase.table("sessions") \
            .select("session_id, status") \
            .eq("session_id", req.session_id) \
            .execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        if result.data[0]["status"] == "concluded":
            raise HTTPException(status_code=400, detail="Session already concluded")
        session_id = req.session_id
    else:
        # Start new session
        session_id = create_session(req.user_id)

    # ── Save user message ─────────────────────────────────────────────────────
    save_message(session_id, "user", req.message)

    # ── Run full RAG pipeline ─────────────────────────────────────────────────
    try:
        context = assemble_context(
            user_message=req.message,
            session_id=session_id,
            user_id=req.user_id,
            accumulated_symptoms=req.accumulated_symptoms,
            file_analysis=req.file_analysis
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context assembly failed: {str(e)}")

    # ── Run triage controller ─────────────────────────────────────────────────
    try:
        triage_result = run_triage(context, turn_count=req.turn_count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Triage failed: {str(e)}")

    # ── Save assistant response ───────────────────────────────────────────────
    save_message(
        session_id,
        "assistant",
        triage_result["response"],
        symptoms=context["all_symptoms"],
        hpo_terms=context["hpo_ids"]
    )

    # ── Conclude session if done ──────────────────────────────────────────────
    if triage_result["is_conclusion"]:
        diagnoses = [
            {"disease": c["disease"], "score": c.get("match_ratio", 0)}
            for c in context["graph_candidates"]
        ]
        conclude_session(session_id, diagnoses)

    return ConsultationResponse(
        session_id=session_id,
        state=triage_result["state"],
        response=triage_result["response"],
        is_conclusion=triage_result["is_conclusion"],
        all_symptoms=context["all_symptoms"],
        graph_candidates=context["graph_candidates"],
        turn_count=req.turn_count + 1
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve full session history. Used by frontend to restore a chat."""
    result = supabase.table("sessions") \
        .select("*") \
        .eq("session_id", session_id) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    history = get_history(session_id)
    return {
        "session": result.data[0],
        "messages": history
    }