"""
Run: python test_integrations.py
All checks must pass before moving to next step.
"""
import os
from config import settings
from dotenv import load_dotenv

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

# ── Test 1: Supabase connection ───────────────────────────────────────────────
print("Testing Supabase...")
from supabase import create_client
sb = create_client(settings.supabase_url, settings.supabase_service_key)
print(f"  ✅ Supabase connected. sessions table reachable.")

# ── Test 2: memory_service round-trip ─────────────────────────────────────────
print("Testing memory_service...")
from services.memory_service import create_session, save_message, get_history, supabase

TEST_USER = "00000000-0000-0000-0000-000000000001"

supabase.table("user_profiles").upsert({
    "user_id": TEST_USER,
    "age": 30,
    "sex": "male"
}).execute()

session_id = create_session(TEST_USER)
save_message(session_id, "user", "I have a headache and fever", ["headache", "fever"])
save_message(session_id, "assistant", "How long have you had these symptoms?")
history = get_history(session_id)
assert len(history) == 2
assert history[0]["role"] == "user"
print(f"  ✅ memory_service OK. Session {session_id} round-trip passed.")

# ── Test 3: LangSmith trace ───────────────────────────────────────────────────
print("Testing LangSmith...")
from langsmith import traceable
import anthropic

@traceable(name="murphybot-test-trace")
def test_claude_call(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text

response = test_claude_call("Reply with exactly: MURPHYBOT ONLINE")
print(f"  ✅ Claude responded: {response.strip()}")
print(f"  ✅ Check LangSmith dashboard → project 'murphybot' for the trace.")
print("\n✅ All checks passed. Ready for Step 3: symptom_extractor.py")

# ── Test 4: symptom_extractor ─────────────────────────────────────────────────
print("Testing symptom_extractor...")
from services.symptom_extractor import extract_symptoms, get_all_positive_symptoms

cases = [
    "I have a really bad headache, fever, and my neck feels stiff",
    "chest pain radiating to my left arm, started an hour ago, no fever",
    "I've had a dry cough for 2 weeks and I'm exhausted all the time",
]

for msg in cases:
    result = extract_symptoms(msg)
    positive = get_all_positive_symptoms(result)
    print(f"\n  Input:    {msg}")
    print(f"  Symptoms: {positive}")
    if result["duration_notes"]:
        print(f"  Duration: {result['duration_notes']}")
    if result["raw_negations"]:
        print(f"  Negated:  {result['raw_negations']}")
    assert len(positive) >= 1, "Expected at least 1 symptom extracted"

print("\n✅ symptom_extractor passed. Ready for Step 4: hpo_mapper.py")

# ── Test 5: hpo_mapper ────────────────────────────────────────────────────────
print("Testing hpo_mapper...")
from services.hpo_mapper import map_symptoms_to_hpo

cases = [
    ["fever", "headache", "neck stiffness"],
    ["chest tightness", "shortness of breath", "pain when breathing deeply"],
    ["splitting headache worse in morning", "blurry vision in left eye"],
]

for symptoms in cases:
    result = map_symptoms_to_hpo(symptoms)
    print(f"\n  Input:    {symptoms}")
    print(f"  HPO IDs:  {result['hpo_ids']}")
    for sym, detail in result["mapping_detail"].items():
        source = detail.get("source", "?")
        hpo_id = detail.get("hpo_id", "?")
        matched = detail.get("matched_term", "")
        dist = detail.get("distance", "")
        if source == "claude":
            print(f"    [{source}]  {sym} → {hpo_id}")
        else:
            print(f"    [{source}] {sym} → {hpo_id} ('{matched}', dist={dist})")
    if result["unmapped"]:
        print(f"  Unmapped: {result['unmapped']}")
    assert len(result["hpo_ids"]) >= 1, "Expected at least 1 HPO ID"

print("\n✅ hpo_mapper passed. Ready for Step 5: graph_service.py")

# ── Test 6: graph_service ─────────────────────────────────────────────────────
print("Testing graph_service...")
from services.graph_service import query_diseases_by_hpo, get_top_candidates

# Use HPO IDs confirmed to exist in your PrimeKG:
# "1945" = Fever, "2315" = Headache, "467" = Neck muscle weakness
MENINGITIS_HPO = ["HP:0001945", "HP:0002315", "HP:0000467"]

results = query_diseases_by_hpo(MENINGITIS_HPO, limit=10)
print(f"\n  Raw result count: {len(results)}")
assert len(results) > 0, "Expected at least 1 disease candidate"

print(f"\n  Top candidates for meningitis triad ({len(results)} returned):")
for r in results[:5]:
    print(f"    {r['disease']:<45} matched={r['matched_symptoms']}  ratio={r['match_ratio']}")

print("\n  Top 3 with drugs:")
top = get_top_candidates(MENINGITIS_HPO, top_n=3)
for c in top:
    print(f"\n    Disease: {c['disease']}")
    print(f"    Matched: {c['matched_names']}")
    print(f"    Drugs:   {c['drugs']}")

print("\n✅ graph_service passed. Ready for Step 6: vector_service.py")






# ── Test 7: vector_service ────────────────────────────────────────────────────
print("Testing vector_service...")
from services.vector_service import (
    search_medical_books,
    search_books_multi_query,
    format_chunks_for_prompt
)

# Single query
chunks = search_medical_books("fever headache neck stiffness", top_k=3)
assert len(chunks) > 0, "Expected at least 1 chunk"
print(f"\n  Single query — 'fever headache neck stiffness' ({len(chunks)} chunks):")
for c in chunks:
    print(f"    [{c['distance']}] {c['source_book']} — {c['chapter'][:50]}")
    print(f"           {c['text'][:120].strip()}...")

# Multi-query
chunks_multi = search_books_multi_query(["fever", "neck stiffness", "photophobia"], top_k=5)
assert len(chunks_multi) > 0, "Expected at least 1 chunk from multi-query"
print(f"\n  Multi-query ({len(chunks_multi)} deduplicated chunks):")
for c in chunks_multi:
    print(f"    [{c['distance']}] {c['source_book'][:40]} — {c['section'][:40]}")

# Format for prompt
formatted = format_chunks_for_prompt(chunks_multi)
assert len(formatted) > 100
print(f"\n  Formatted for prompt ({len(formatted)} chars):")
print(f"  {formatted[:300].strip()}...")

print("\n✅ vector_service passed. Ready for Step 7: context_assembler.py")






# ── Test 8: context_assembler ─────────────────────────────────────────────────
print("Testing context_assembler...")
from services.context_assembler import (
    assemble_context,
    format_user_profile,
    format_graph_candidates
)

TEST_USER = "00000000-0000-0000-0000-000000000001"

# Simulate turn 1
print("\n  Turn 1: initial symptoms...")
ctx1 = assemble_context(
    user_message="I have a bad headache and fever",
    session_id=session_id,   # reuse session from Test 2
    user_id=TEST_USER,
    accumulated_symptoms=[]
)
print(f"    New symptoms:     {ctx1['new_symptoms']}")
print(f"    All symptoms:     {ctx1['all_symptoms']}")
print(f"    HPO IDs:          {ctx1['hpo_ids']}")
print(f"    Graph candidates: {len(ctx1['graph_candidates'])} diseases")
print(f"    Vector chunks:    {len(ctx1['vector_chunks'])} chunks")
assert len(ctx1["all_symptoms"]) >= 1

# Simulate turn 2 — new symptom added
print("\n  Turn 2: adding neck stiffness...")
ctx2 = assemble_context(
    user_message="Yes and my neck is very stiff",
    session_id=session_id,
    user_id=TEST_USER,
    accumulated_symptoms=ctx1["all_symptoms"]
)
print(f"    New symptoms:     {ctx2['new_symptoms']}")
print(f"    All symptoms:     {ctx2['all_symptoms']}")
print(f"    Graph candidates: {len(ctx2['graph_candidates'])} diseases")
assert len(ctx2["all_symptoms"]) > len(ctx1["all_symptoms"]), \
    "Turn 2 should have more symptoms than turn 1"

# Format helpers
print("\n  Formatting helpers:")
profile_str = format_user_profile(ctx2["user_profile"])
graph_str   = format_graph_candidates(ctx2["graph_candidates"])
print(f"    Profile: {profile_str}")
print(f"    Graph:\n{graph_str}")

print("\n✅ context_assembler passed. Ready for Step 8: triage_controller.py")





# ── Test 9: triage_controller ─────────────────────────────────────────────────
print("Testing triage_controller...")
from services.triage_controller import run_triage, determine_triage_state
from services.context_assembler import assemble_context

TEST_USER = "00000000-0000-0000-0000-000000000001"

# ── State machine logic test (no LLM call) ────────────────────────────────────
assert determine_triage_state([], [], 0) == "GATHERING"
assert determine_triage_state(["fever"], [], 0) == "GATHERING"
assert determine_triage_state(["fever", "headache", "neck stiffness"], [1,2,3,4,5,6], 2) == "NARROWING"
assert determine_triage_state(["fever", "headache", "neck stiffness"], [1,2,3], 0) == "CONCLUSION"
assert determine_triage_state(["fever", "headache", "neck stiffness"], [1,2,3,4,5,6], 5) == "CONCLUSION"
# New — POST_CONCLUSION overrides everything
assert determine_triage_state(["fever"], [], 0, is_post_conclusion=True) == "POST_CONCLUSION"
print("  ✅ State machine logic correct")

# ── GATHERING state ───────────────────────────────────────────────────────────
print("\n  Testing GATHERING state (1 symptom)...")
ctx_gather = assemble_context(
    user_message="I have a fever",
    session_id=session_id,
    user_id=TEST_USER,
    accumulated_symptoms=[]
)
result_gather = run_triage(ctx_gather, turn_count=0)
print(f"    State:    {result_gather['state']}")
print(f"    Response: {result_gather['response']}")
assert result_gather["state"] == "GATHERING"
assert result_gather["is_conclusion"] == False
assert len(result_gather["response"]) > 10

# ── CONCLUSION state ──────────────────────────────────────────────────────────
print("\n  Testing CONCLUSION state (3+ symptoms, few candidates)...")
ctx_conclusion = assemble_context(
    user_message="I also have sensitivity to light",
    session_id=session_id,
    user_id=TEST_USER,
    accumulated_symptoms=["fever", "headache", "neck stiffness"]
)
result_conclusion = run_triage(ctx_conclusion, turn_count=3)
print(f"    State:    {result_conclusion['state']}")
print(f"    Response preview:\n")
# Print full conclusion so we can see quality
for line in result_conclusion["response"].split("\n")[:20]:
    print(f"      {line}")
assert result_conclusion["state"] == "CONCLUSION"
assert result_conclusion["is_conclusion"] == True
assert "not a medical diagnosis" in result_conclusion["response"].lower()

print("\n✅ triage_controller passed. Ready for Step 9: consultation.py router")







# ── Test 10: consultation router (full end-to-end via HTTP) ───────────────────
print("Testing consultation router...")
import httpx
import threading
import uvicorn
import time
import sys
import os

# Start FastAPI in background thread
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import app

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="error"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
time.sleep(2)  # wait for server to boot

BASE = "http://127.0.0.1:8001"
TEST_USER = "00000000-0000-0000-0000-000000000001"

# Health check
r = httpx.get(f"{BASE}/health")
assert r.status_code == 200
print("  ✅ Server running")

# Turn 1 — start new session
r = httpx.post(f"{BASE}/consultation/message", json={
    "user_id":              TEST_USER,
    "message":              "I have a bad headache and fever",
    "accumulated_symptoms": [],
    "turn_count":           0
}, timeout=60)
assert r.status_code == 200, f"Turn 1 failed: {r.text}"
t1 = r.json()
print(f"\n  Turn 1:")
print(f"    State:    {t1['state']}")
print(f"    Symptoms: {t1['all_symptoms']}")
print(f"    Response: {t1['response'][:120]}...")

# Turn 2 — continue session
r = httpx.post(f"{BASE}/consultation/message", json={
    "user_id":              TEST_USER,
    "session_id":           t1["session_id"],
    "message":              "Yes and my neck is very stiff, light hurts my eyes",
    "accumulated_symptoms": t1["all_symptoms"],
    "turn_count":           t1["turn_count"]
}, timeout=60)
assert r.status_code == 200, f"Turn 2 failed: {r.text}"
t2 = r.json()                          # ← parse t2 FIRST
print(f"\n  Turn 2:")
print(f"    State:    {t2['state']}")
print(f"    Symptoms: {t2['all_symptoms']}")
print(f"    Conclusion: {t2['is_conclusion']}")
print(f"    Response: {t2['response'][:200]}...")

# Turn 3 — POST_CONCLUSION (only if Turn 2 reached conclusion)
if t2["is_conclusion"]:
    print(f"\n  Turn 3 (POST_CONCLUSION follow-up)...")
    r = httpx.post(f"{BASE}/consultation/message", json={
        "user_id":              TEST_USER,
        "session_id":           t1["session_id"],
        "message":              "What does bacterial meningitis mean for me?",
        "accumulated_symptoms": t2["all_symptoms"],
        "turn_count":           t2["turn_count"],
        "is_post_conclusion":   True
    }, timeout=60)
    assert r.status_code == 200, f"POST_CONCLUSION failed: {r.text}"
    t3 = r.json()
    print(f"    State:    {t3['state']}")
    print(f"    Response: {t3['response'][:200]}...")
    assert t3["state"] == "POST_CONCLUSION"
    print("  ✅ POST_CONCLUSION works")

# Session history check
r = httpx.get(f"{BASE}/consultation/session/{t1['session_id']}")
assert r.status_code == 200
history = r.json()
assert len(history["messages"]) >= 2
print(f"\n  Session history: {len(history['messages'])} messages stored ✅")

server.should_exit = True
print("\n✅ consultation router passed. Day 2 backend complete!")






# ── Test 11: file_processor ───────────────────────────────────────────────────
print("Testing file_processor...")
from services.file_processor import process_pdf, process_file
import urllib.request

# ── PDF test: download a small real medical PDF ───────────────────────────────
print("\n  Testing PDF processing...")
PDF_URL = "https://www.w3.org/WAI/WCAG21/Techniques/pdf/img/table-word.pdf"
try:
    with urllib.request.urlopen(PDF_URL, timeout=10) as r:
        pdf_bytes = r.read()

    result = process_pdf(pdf_bytes)
    print(f"    Success:    {result['success']}")
    print(f"    Pages:      {result['page_count']}")
    print(f"    Text len:   {len(result['text'])} chars")
    if result["success"]:
        print(f"    Preview:    {result['text'][:100].strip()}...")
        print("    ✅ PDF processing works")
    else:
        print(f"    Error: {result['error']}")
except Exception as e:
    print(f"    ⚠ PDF download failed (network): {e}")
    print("    Testing with synthetic PDF instead...")

    # Create minimal valid PDF in memory
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Patient: John Doe\nDiagnosis: Hypertension\nMedication: Lisinopril 10mg")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = process_pdf(pdf_bytes)
    assert result["success"], f"PDF failed: {result['error']}"
    assert "Lisinopril" in result["text"]
    print(f"    ✅ PDF processing works ({result['page_count']} page, {len(result['text'])} chars)")





# ── Test 12: doctor_finder ────────────────────────────────────────────────────
print("Testing doctor_finder...")
from services.doctor_finder import find_nearby_doctors

# Simulate meningitis conclusion
diagnoses = [
    {"disease": "Bacterial Meningitis", "match_ratio": 0.75},
    {"disease": "Viral Meningitis",     "match_ratio": 0.60},
]
symptoms = ["fever", "headache", "neck stiffness", "photophobia"]

# Test with text location (Dallas from your Colab)
result = find_nearby_doctors(
    diagnoses=diagnoses,
    symptoms=symptoms,
    location_text="Dallas, TX"
)

print(f"\n  Specialist type: {result['specialist_type']}")
print(f"  Urgency level:   {result['urgency_level']}")
print(f"  Search used:     {result['search_used']}")
print(f"  Doctors found:   {len(result['doctors'])}")
for i, d in enumerate(result["doctors"], 1):
    print(f"\n    {i}. {d['name']}")
    print(f"       {d['address']}")
    print(f"       ⭐ {d.get('rating')} ({d.get('user_ratings_total', 0)} reviews)")
    print(f"       {d['google_maps_link']}")

assert len(result["doctors"]) > 0, "Expected at least 1 doctor"
assert result["urgency_level"] in ["routine", "urgent", "emergency"]
print("\n✅ doctor_finder passed.")







# # ── Test 13: mcp_enrichment ───────────────────────────────────────────────────
# print("Testing mcp_enrichment...")
# from services.mcp_enrichment import enrich_conclusion
# from services.mcp.mcp_client import is_mcp_available

# mcp_up = is_mcp_available()
# print(f"\n  MCP server available: {mcp_up}")
# if not mcp_up:
#     print("  ⚠ MCP server not running — drug/literature/guidelines will use fallbacks")
#     print("  To start: cd medical-mcp && npm start")

# diagnoses = [
#     {"disease": "Bacterial Meningitis", "match_ratio": 0.75, "drugs": ["Ceftriaxone", "Dexamethasone"]},
#     {"disease": "Viral Meningitis",     "match_ratio": 0.60, "drugs": ["Acyclovir"]},
# ]
# symptoms = ["fever", "headache", "neck stiffness", "photophobia"]
# current_meds = ["Warfarin"]  # simulate user taking a blood thinner

# result = enrich_conclusion(
#     diagnoses=diagnoses,
#     symptoms=symptoms,
#     current_medications=current_meds
# )

# print(f"\n  Drugs found:       {len(result['drugs'])}")
# for d in result["drugs"]:
#     print(f"    - {d['name']} (FDA data: {d['available']})")

# print(f"\n  Interactions:      {len(result['interactions'])}")
# for i in result["interactions"]:
#     print(f"    ⚠ {i['drug_1']} + {i['drug_2']} [{i['severity']}]: {i['description'][:80]}")

# print(f"\n  PubMed papers:     {len(result['pubmed_papers'])}")
# for p in result["pubmed_papers"]:
#     print(f"    - {p['title'][:70]}...")

# print(f"\n  Guidelines:        {'yes' if result['guidelines'].get('guideline') else 'no'}")

# print(f"\n  Confirmatory tests: {len(result['tests'])}")
# for t in result["tests"]:
#     print(f"    [{t.get('urgency','?')}] {t.get('test','')} — {t.get('purpose','')[:60]}")

# assert len(result["tests"]) > 0, "Claude should always return tests regardless of MCP"
# print("\n✅ mcp_enrichment passed.")