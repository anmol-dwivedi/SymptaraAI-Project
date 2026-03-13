"""
literature.py
=============
PubMed paper search via MCP search-medical-literature tool.
Returns top 3 papers relevant to the top diagnosis.
"""

import logging
from services.mcp.mcp_client import call_tool

log = logging.getLogger("murphybot.mcp.literature")


def search_pubmed(query: str, max_results: int = 3) -> list[dict]:
    """
    Search PubMed for papers related to a diagnosis.

    Args:
        query:       search query e.g. "Bacterial Meningitis diagnosis treatment"
        max_results: number of papers to return (default 3)

    Returns:
        [
            {
                "title":    "Bacterial meningitis in adults...",
                "authors":  "Smith J, Jones A",
                "journal":  "NEJM",
                "year":     "2023",
                "abstract": "...",
                "pmid":     "12345678",
                "url":      "https://pubmed.ncbi.nlm.nih.gov/12345678"
            },
            ...
        ]
    """
    result = call_tool("search-medical-literature", {
        "query":       query,
        "max_results": max_results
    })

    if "error" in result:
        log.warning(f"PubMed search failed: {result['error']}")
        return []

    articles = result.get("articles", result.get("results", []))
    if not articles:
        return []

    parsed = []
    for article in articles[:max_results]:
        pmid = str(article.get("pmid", article.get("id", "")))
        parsed.append({
            "title":    article.get("title", ""),
            "authors":  _format_authors(article.get("authors", [])),
            "journal":  article.get("journal", article.get("source", "")),
            "year":     str(article.get("pubdate", article.get("year", ""))),
            "abstract": _truncate(article.get("abstract", ""), 400),
            "pmid":     pmid,
            "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}" if pmid else ""
        })

    return parsed


def get_papers_for_diagnosis(diagnoses: list[dict]) -> list[dict]:
    """
    Get PubMed papers for the top diagnosis.
    Builds a targeted query from disease name + symptoms.

    Args:
        diagnoses: graph_candidates — uses top 1 disease

    Returns:
        List of up to 3 paper dicts
    """
    if not diagnoses:
        return []

    top_disease = diagnoses[0]["disease"]
    query       = f"{top_disease} diagnosis treatment clinical"

    papers = search_pubmed(query, max_results=3)

    # If top disease returns nothing, try broader query with top 2
    if not papers and len(diagnoses) > 1:
        second_disease = diagnoses[1]["disease"]
        query          = f"{top_disease} OR {second_disease} management"
        papers         = search_pubmed(query, max_results=3)

    return papers


def _format_authors(authors) -> str:
    """Format authors list into readable string."""
    if not authors:
        return ""
    if isinstance(authors, str):
        return authors
    if isinstance(authors, list):
        names = []
        for a in authors[:3]:  # max 3 authors
            if isinstance(a, dict):
                names.append(a.get("name", a.get("lastname", "")))
            elif isinstance(a, str):
                names.append(a)
        result = ", ".join(n for n in names if n)
        if len(authors) > 3:
            result += " et al."
        return result
    return ""


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text