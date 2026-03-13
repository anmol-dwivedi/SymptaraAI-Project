"""
consultation.py router
======================
Accepts timezone, local_time, and location from frontend.
Stores them on session conclusion for the medical report.
"""

import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from services.context_assembler import assemble_context
from services.triage_controller import run_triage
from services.memory_service import (
    create_session, save_message, get_history,
    conclude_session, supabase, reset_session,
    get_session_conclusion
)
from services.file_processor import process_file
from services.doctor_finder import find_nearby_doctors
from services.mcp_enrichment import enrich_conclusion
from services.report_assembler import assemble_report

log    = logging.getLogger("murphybot.consultation")
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
    is_post_conclusion:   bool = False
    timezone:             str | None = None   # e.g. "America/Chicago"
    local_time:           str | None = None   # e.g. "2026-03-13T15:45:00"


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
    Single endpoint for entire consultation flow including POST_CONCLUSION.
    Accepts location, timezone, and local_time from frontend on every turn.
    These are stored at conclusion time for the medical report.
    """

    # ── Session management ────────────────────────────────────────────────────
    if req.session_id:
        result = supabase.table("sessions") \
            .select("session_id, status") \
            .eq("session_id", req.session_id) \
            .execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        if result.data[0]["status"] == "reset":
            raise HTTPException(
                status_code=400,
                detail="Session has been reset. Please start a new session."
            )
        session_id = req.session_id
    else:
        session_id = create_session(req.user_id)

    # ── Save user message ─────────────────────────────────────────────────────
    save_message(
        session_id, "user", req.message,
        input_method=req.input_method
    )

    # ── Restore MCP enrichment for POST_CONCLUSION ────────────────────────────
    restored_mcp = {}
    if req.is_post_conclusion:
        conclusion_data = get_session_conclusion(session_id)
        restored_mcp    = conclusion_data.get("mcp_enrichment", {})

    # ── Run RAG pipeline ──────────────────────────────────────────────────────
    try:
        context = assemble_context(
            user_message=req.message,
            session_id=session_id,
            user_id=req.user_id,
            accumulated_symptoms=req.accumulated_symptoms,
            file_analysis=req.file_analysis,
            location_text=req.location_text,
            local_time=req.local_time,
            timezone=req.timezone
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context assembly failed: {str(e)}")

    # ── Run triage controller ─────────────────────────────────────────────────
    try:
        triage_result = run_triage(
            context,
            turn_count=req.turn_count,
            is_post_conclusion=req.is_post_conclusion,
            mcp_enrichment=restored_mcp
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Triage failed: {str(e)}")

    # ── Save assistant response ───────────────────────────────────────────────
    save_message(
        session_id, "assistant", triage_result["response"],
        symptoms=context["all_symptoms"],
        hpo_terms=context["hpo_ids"]
    )

    # ── Conclude session + fire enrichments ───────────────────────────────────
    doctors         = []
    urgency_level   = "routine"
    specialist_type = ""
    mcp_data        = {}

    if triage_result["is_conclusion"]:

        # MCP enrichment
        try:
            current_meds = (context["user_profile"] or {}).get("current_medications", [])
            mcp_data     = enrich_conclusion(
                diagnoses=context["graph_candidates"],
                symptoms=context["all_symptoms"],
                current_medications=current_meds,
                user_profile=context["user_profile"]
            )
        except Exception as e:
            log.warning(f"MCP enrichment failed: {e}")

        # Build location dict for storage
        location = {}
        if req.lat and req.lng:
            location = {"lat": req.lat, "lng": req.lng, "location_text": req.location_text}
        elif req.location_text:
            location = {"location_text": req.location_text}

        # Store conclusion with all context
        diagnoses = [
            {"disease": c["disease"], "score": c.get("match_ratio", 0)}
            for c in context["graph_candidates"]
        ]
        conclude_session(
            session_id,
            diagnoses,
            mcp_enrichment=mcp_data,
            location=location if location else None,
            timezone=req.timezone,
            local_time=req.local_time
        )

        # Doctor finder
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
            pass

    if req.is_post_conclusion and restored_mcp:
        mcp_data = restored_mcp

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


@router.post("/new-session")
async def new_session(user_id: str, current_session_id: str | None = None):
    """New Session button — resets current session and creates fresh one."""
    if current_session_id:
        try:
            reset_session(current_session_id)
        except Exception:
            pass
    new_sid = create_session(user_id)
    return {"session_id": new_sid, "message": "New session started."}


@router.get("/report/{session_id}")
async def get_report(session_id: str, user_id: str):
    """
    Generate full medical report for a concluded session.
    Called by the frontend Report Download button.
    Includes patient location, local time, and timezone.
    """
    result = supabase.table("sessions") \
        .select("session_id, status, user_id") \
        .eq("session_id", session_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    session = result.data[0]
    if session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    if session["status"] not in ("concluded", "reset"):
        raise HTTPException(
            status_code=400,
            detail="Report only available after consultation is concluded."
        )

    try:
        report = assemble_report(session_id=session_id, user_id=user_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve full session history."""
    result = supabase.table("sessions") \
        .select("*") \
        .eq("session_id", session_id) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    history = get_history(session_id)
    return {"session": result.data[0], "messages": history}


@router.post("/upload-file")
async def upload_file(
    session_id: str = Form(...),
    user_id:    str = Form(...),
    file:       UploadFile = File(...)
):
    MAX_SIZE   = 10 * 1024 * 1024
    file_bytes = await file.read()

    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum 10MB.")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    result = process_file(
        file_bytes=file_bytes,
        media_type=file.content_type or "",
        filename=file.filename or ""
    )

    if not result["success"]:
        raise HTTPException(status_code=422, detail=result["error"])

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
        "message":   "File analyzed and saved to session. Included in all future turns automatically."
    }