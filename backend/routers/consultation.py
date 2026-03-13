from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from services.context_assembler import assemble_context
from services.triage_controller import run_triage
from services.memory_service import (
    create_session, save_message, get_history,
    conclude_session, supabase
)
from services.file_processor import process_file
from services.doctor_finder import find_nearby_doctors

# mcp imports
from services.mcp_enrichment import enrich_conclusion
import logging
log = logging.getLogger("murphybot.consultation")


router = APIRouter()


class ConsultationRequest(BaseModel):
    user_id:              str
    session_id:           str | None = None
    message:              str
    accumulated_symptoms: list[str] = []
    turn_count:           int = 0
    file_analysis:        str | None = None
    lat:                  float | None = None
    lng:                  float | None = None
    location_text:        str | None = None
    input_method:         str = "text" 


class ConsultationResponse(BaseModel):
    session_id:       str
    state:            str
    response:         str
    is_conclusion:    bool
    all_symptoms:     list[str]
    graph_candidates: list[dict]
    turn_count:       int
    doctors:          list[dict] = []
    urgency_level:    str = "routine"
    specialist_type:  str = ""
    mcp_enrichment:   dict = {}


@router.post("/message", response_model=ConsultationResponse)
async def consultation_message(req: ConsultationRequest):
    """
    Single endpoint for the entire consultation flow.

    Client sends message + accumulated state.
    Server returns response + updated state.
    Client stores accumulated_symptoms and turn_count between turns.
    On CONCLUSION: also returns nearby doctors + urgency level.
    """

    # ── Session management ────────────────────────────────────────────────────
    if req.session_id:
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
        session_id = create_session(req.user_id)

    # ── Save user message ─────────────────────────────────────────────────────
    save_message(session_id, "user", req.message, input_method=req.input_method)

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

    # ── Conclude session + find doctors if done ───────────────────────────────
    doctors         = []
    urgency_level   = "routine"
    specialist_type = ""
    mcp_data        = {}

    if triage_result["is_conclusion"]:
        diagnoses = [
            {"disease": c["disease"], "score": c.get("match_ratio", 0)}
            for c in context["graph_candidates"]
        ]
        conclude_session(session_id, diagnoses)

        # Fire doctor finder only on conclusion
        try:
            doctor_result   = find_nearby_doctors(
                diagnoses=context["graph_candidates"],
                symptoms=context["all_symptoms"],
                lat=req.lat,
                lng=req.lng,
                location_text=req.location_text
            )
            doctors         = doctor_result["doctors"]
            urgency_level   = doctor_result["urgency_level"]
            specialist_type = doctor_result["specialist_type"]
        except Exception:
            pass  # Non-blocking — don't fail the whole response if Maps fails
        
        # MCP enrichment
        try:
            current_meds = (context["user_profile"] or {}).get(
                "current_medications", []
            )
            mcp_data = enrich_conclusion(
                diagnoses=context["graph_candidates"],
                symptoms=context["all_symptoms"],
                current_medications=current_meds,
                user_profile=context["user_profile"]
            )
        except Exception as e:
            log.warning(f"MCP enrichment failed: {e}")


    return ConsultationResponse(
        session_id=session_id,
        state=triage_result["state"],
        response=triage_result["response"],
        is_conclusion=triage_result["is_conclusion"],
        all_symptoms=context["all_symptoms"],
        graph_candidates=context["graph_candidates"],
        turn_count=req.turn_count + 1,
        doctors=doctors,
        urgency_level=urgency_level,
        specialist_type=specialist_type,
        mcp_enrichment=mcp_data
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
        "session":  result.data[0],
        "messages": history
    }


@router.post("/upload-file")
async def upload_file(
    session_id: str = Form(...),
    user_id:    str = Form(...),
    file:       UploadFile = File(...)
):
    """
    Upload a medical file (PDF or image) attached to a consultation session.
    Returns Claude's analysis as text — frontend passes this as
    file_analysis in the next /consultation/message call.
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10MB

    file_bytes = await file.read()

    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 10MB."
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded."
        )

    result = process_file(
        file_bytes=file_bytes,
        media_type=file.content_type or "",
        filename=file.filename or ""
    )

    if not result["success"]:
        raise HTTPException(
            status_code=422,
            detail=result["error"]
        )

    # Store in Supabase session_files (non-blocking)
    try:
        supabase.table("session_files").insert({
            "session_id":      session_id,
            "file_type":       result["file_type"],
            "storage_path":    file.filename,
            "claude_analysis": result["analysis"]
        }).execute()
    except Exception:
        pass

    return {
        "success":   True,
        "file_type": result["file_type"],
        "filename":  file.filename,
        "analysis":  result["analysis"],
        "message":   "File analyzed successfully. This analysis will be "
                     "included in your next consultation message."
    }