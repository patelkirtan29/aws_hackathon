# linkup_job.py
import os
import re
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from linkup import LinkupClient
except Exception:
    LinkupClient = None


def sanitize_query(text: str) -> str:
    """Privacy-first: remove emails, phone-like strings, and long IDs from queries."""
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[redacted_email]", text)
    text = re.sub(r"\b(\+?\d[\d\-\s]{7,}\d)\b", "[redacted_phone]", text)
    text = re.sub(r"\b\d{8,}\b", "[redacted_id]", text)
    return text.strip()


def get_client():
    api_key = os.getenv("LINKUP_API_KEY")
    if not api_key:
        raise RuntimeError("LINKUP_API_KEY is not set (put it in .env).")
    if not LinkupClient:
        raise RuntimeError("linkup-sdk not installed. Run: pip install linkup-sdk")
    return LinkupClient(api_key=api_key)


def _as_dict(obj: Any) -> Dict[str, Any]:
    """Convert SDK objects to dict if needed."""
    if isinstance(obj, dict):
        return obj
    # some SDKs return pydantic-like objects with .model_dump() or .dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    # fallback: try vars
    try:
        return dict(vars(obj))
    except Exception:
        return {"value": obj}


def normalize_linkup_response(raw: Any) -> Dict[str, Any]:
    """
    Force a consistent shape:
      {
        "error": bool,
        "message": str | None,
        "answer": str,
        "sources": [{"title": str, "url": str}],
        "raw": {...}   # for debugging
      }
    """
    data = _as_dict(raw)

    # Find answer text under common keys
    answer = ""
    for k in ["answer", "sourcedAnswer", "text", "output", "result"]:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            answer = v.strip()
            break

    # Find sources under common keys (sources, citations, references)
    sources_raw = None
    for k in ["sources", "citations", "references"]:
        if k in data and isinstance(data[k], list):
            sources_raw = data[k]
            break

    sources: List[Dict[str, str]] = []
    if isinstance(sources_raw, list):
        for s in sources_raw:
            sd = _as_dict(s)
            url = sd.get("url") or sd.get("link") or sd.get("source") or ""
            title = sd.get("title") or sd.get("name") or sd.get("label") or url
            if isinstance(url, str) and url.strip():
                sources.append({"title": str(title).strip(), "url": url.strip()})

    return {
        "error": bool(data.get("error", False)),
        "message": data.get("message"),
        "answer": answer,
        "sources": sources,
        "raw": data,  # keep for debug
    }


def linkup_search(query: str) -> Dict[str, Any]:
    """
    Calls LinkUp with multiple depth/output combos.
    Returns normalized result with stable keys: answer + sources.
    """
    safe_query = sanitize_query(query)

    candidates = [
        ("shallow", "sourcedAnswer"),
        ("standard", "sourcedAnswer"),
        ("deep", "sourcedAnswer"),
        ("shallow", "answer"),
        ("standard", "answer"),
        ("shallow", "text"),
    ]

    try:
        client = get_client()
    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "query_used": safe_query,
            "answer": "",
            "sources": [],
            "raw": {},
        }

    last_err: Optional[Exception] = None

    for depth, output_type in candidates:
        try:
            raw = client.search(safe_query, depth, output_type)  # positional signature
            normalized = normalize_linkup_response(raw)
            normalized["query_used"] = safe_query
            normalized["depth_used"] = depth
            normalized["output_type_used"] = output_type
            return normalized
        except Exception as e:
            last_err = e
            time.sleep(0.2)

    return {
        "error": True,
        "message": f"All Linkup attempts failed. Last error: {last_err}",
        "query_used": safe_query,
        "answer": "",
        "sources": [],
        "raw": {},
    }


if __name__ == "__main__":
    res = linkup_search("Google AI latest updates last 30 days")
    print("✅ linkup_search normalized output:")
    print("Answer:", (res.get("answer") or "")[:200])
    print("Sources:", res.get("sources"))
