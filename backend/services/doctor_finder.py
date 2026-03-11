import json
import googlemaps
import anthropic
from langsmith import traceable
from config import settings

gmaps  = googlemaps.Client(key=settings.google_maps_api_key)
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ── Specialist type inference ─────────────────────────────────────────────────
@traceable(name="doctor-finder-specialist-inference")
def infer_specialist_type(
    diagnoses: list[dict],
    symptoms: list[str]
) -> dict:
    """
    Given the triage conclusions, infer what specialist the user should see.
    Uses Claude instead of GPT-4o (no extra API key needed).

    Args:
        diagnoses: graph_candidates from context assembler
                   e.g. [{"disease": "Bacterial Meningitis", ...}]
        symptoms:  all_symptoms list

    Returns:
        {
            "specialist_type": "neurologist",
            "urgency_level":   "emergency" | "urgent" | "routine",
            "search_keyword":  "neurologist near me"
        }
    """
    top_diseases = [d["disease"] for d in diagnoses[:3]]
    symptom_str  = ", ".join(symptoms)
    disease_str  = ", ".join(top_diseases)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system="""You are a medical triage routing assistant.
Given symptoms and possible diagnoses, return the most appropriate specialist type.
Return ONLY a JSON object, no explanation, no markdown.
Output format:
{
  "specialist_type": "e.g. neurologist, cardiologist, general practitioner, urgent care",
  "urgency_level": "routine" | "urgent" | "emergency",
  "search_keyword": "e.g. neurologist, urgent care clinic, emergency room"
}""",
        messages=[{
            "role": "user",
            "content": f"Symptoms: {symptom_str}\nTop diagnoses: {disease_str}"
        }]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "specialist_type": "general practitioner",
            "urgency_level":   "routine",
            "search_keyword":  "doctor"
        }

    result.setdefault("specialist_type", "general practitioner")
    result.setdefault("urgency_level",   "routine")
    result.setdefault("search_keyword",  "doctor")
    return result


# ── Google Places search ──────────────────────────────────────────────────────
def _collect_places(results: dict, n: int) -> list[dict]:
    """Parse Google Places API response into clean doctor list."""
    doctors = []
    for r in results.get("results", [])[:n]:
        doctors.append({
            "name":                r.get("name"),
            "address":             r.get("vicinity") or r.get("formatted_address"),
            "rating":              r.get("rating"),
            "user_ratings_total":  r.get("user_ratings_total", 0),
            "google_maps_link":    f"https://www.google.com/maps/place/?q=place_id:{r['place_id']}",
            "place_id":            r.get("place_id")
        })
    return doctors


def find_doctors_by_coords(
    lat: float,
    lng: float,
    specialist_type: str = "doctor",
    n_results: int = 5
) -> list[dict]:
    """
    Find nearby doctors using device GPS coordinates.
    Ranks by distance — most accurate for mobile users.
    """
    try:
        results = gmaps.places_nearby(
            location=(lat, lng),
            rank_by="distance",
            type="doctor",
            keyword=specialist_type
        )
        return _collect_places(results, n_results)
    except Exception as e:
        return []


def find_doctors_by_location(
    location_text: str,
    specialist_type: str = "doctor",
    n_results: int = 5
) -> list[dict]:
    """
    Find nearby doctors using a text location string.
    Fallback when GPS coordinates are not available.
    """
    try:
        query   = f"{specialist_type} near {location_text}"
        results = gmaps.places(query=query, type="doctor")
        return _collect_places(results, n_results)
    except Exception as e:
        return []


# ── Main entry point ──────────────────────────────────────────────────────────
@traceable(name="doctor-finder")
def find_nearby_doctors(
    diagnoses:     list[dict],
    symptoms:      list[str],
    lat:           float | None = None,
    lng:           float | None = None,
    location_text: str | None = None,
    n_results:     int = 5
) -> dict:
    """
    Full doctor finder pipeline. Called only on CONCLUSION state.

    Step 1: Infer specialist type from diagnoses
    Step 2: Search Google Places by coords (preferred) or text
    Step 3: Return ranked list with Maps links

    Args:
        diagnoses:     graph_candidates from context assembler
        symptoms:      all_symptoms list
        lat/lng:       device GPS (preferred — most accurate)
        location_text: fallback text e.g. "Dallas, TX"
        n_results:     number of doctors to return (default 5)

    Returns:
        {
            "specialist_type": "neurologist",
            "urgency_level":   "emergency",
            "doctors": [
                {
                    "name":               "Dallas Neurology Associates",
                    "address":            "123 Main St, Dallas, TX",
                    "rating":             4.7,
                    "user_ratings_total": 312,
                    "google_maps_link":   "https://maps.google.com/..."
                },
                ...
            ],
            "search_used": "coords" | "text" | "none"
        }
    """
    # Step 1: Infer specialist type
    specialist_info = infer_specialist_type(diagnoses, symptoms)
    specialist_type = specialist_info["search_keyword"]
    urgency         = specialist_info["urgency_level"]

    # Step 2: Search Google Places
    doctors     = []
    search_used = "none"

    if lat is not None and lng is not None:
        doctors     = find_doctors_by_coords(lat, lng, specialist_type, n_results)
        search_used = "coords"

    if not doctors and location_text:
        doctors     = find_doctors_by_location(location_text, specialist_type, n_results)
        search_used = "text"

    return {
        "specialist_type": specialist_info["specialist_type"],
        "urgency_level":   urgency,
        "doctors":         doctors,
        "search_used":     search_used
    }