"""
literature.py
=============
PubMed search via NCBI E-utilities API (direct, free, no key needed).
"""

import httpx
import logging
import xml.etree.ElementTree as ET

log     = logging.getLogger("murphybot.mcp.literature")
TIMEOUT = 15
NCBI    = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search_pubmed(query: str, max_results: int = 3) -> list[dict]:
    """Search PubMed directly via NCBI E-utilities."""
    try:
        # Step 1: Search for PMIDs
        search_r = httpx.get(
            f"{NCBI}/esearch.fcgi",
            params={
                "db":      "pubmed",
                "term":    query,
                "retmax":  max_results,
                "retmode": "json",
                "sort":    "relevance"
            },
            timeout=TIMEOUT
        )
        search_data = search_r.json()
        pmids = search_data.get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return []

        # Step 2: Fetch article details
        fetch_r = httpx.get(
            f"{NCBI}/efetch.fcgi",
            params={
                "db":      "pubmed",
                "id":      ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract"
            },
            timeout=TIMEOUT
        )

        return _parse_pubmed_xml(fetch_r.text, pmids)

    except Exception as e:
        log.warning(f"PubMed search failed: {e}")
        return []


def _parse_pubmed_xml(xml_text: str, pmids: list) -> list[dict]:
    """Parse PubMed XML response into clean dicts."""
    try:
        root     = ET.fromstring(xml_text)
        articles = []

        for article in root.findall(".//PubmedArticle"):
            try:
                medline  = article.find("MedlineCitation")
                art      = medline.find("Article")

                # Title
                title_el = art.find("ArticleTitle")
                title    = "".join(title_el.itertext()) if title_el is not None else ""

                # Abstract
                abstract_el = art.find("Abstract/AbstractText")
                abstract    = "".join(abstract_el.itertext()) if abstract_el is not None else ""
                if len(abstract) > 400:
                    abstract = abstract[:400] + "..."

                # Authors
                authors = []
                for author in art.findall("AuthorList/Author")[:3]:
                    last  = author.findtext("LastName", "")
                    first = author.findtext("ForeName", "")
                    if last:
                        authors.append(f"{last} {first}".strip())
                author_str = ", ".join(authors)
                if len(art.findall("AuthorList/Author")) > 3:
                    author_str += " et al."

                # Journal + Year
                journal = art.findtext("Journal/Title", "")
                year    = art.findtext(
                    "Journal/JournalIssue/PubDate/Year", ""
                ) or art.findtext("Journal/JournalIssue/PubDate/MedlineDate", "")[:4]

                # PMID
                pmid_el = medline.find("PMID")
                pmid    = pmid_el.text if pmid_el is not None else ""

                articles.append({
                    "title":    title,
                    "authors":  author_str,
                    "journal":  journal,
                    "year":     year,
                    "abstract": abstract,
                    "pmid":     pmid,
                    "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}" if pmid else ""
                })
            except Exception:
                continue

        return articles

    except ET.ParseError as e:
        log.warning(f"PubMed XML parse failed: {e}")
        return []


def get_papers_for_diagnosis(diagnoses: list[dict]) -> list[dict]:
    """Get top 3 PubMed papers for the top diagnosis."""
    if not diagnoses:
        return []

    top_disease = diagnoses[0]["disease"]
    papers      = search_pubmed(
        f"{top_disease} diagnosis treatment", max_results=3
    )

    if not papers and len(diagnoses) > 1:
        papers = search_pubmed(
            f"{diagnoses[1]['disease']} management", max_results=3
        )

    return papers