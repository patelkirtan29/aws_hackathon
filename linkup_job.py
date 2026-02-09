# linkup_job.py
import os
import re
import time
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


def linkup_search(query: str):
    """
    Robust call for SDKs that require: search(query, depth, output_type) POSITIONALLY.

    Linkup sometimes returns 500 ([DecimalError] Invalid argument: undefined) depending
    on depth/output_type. So we try multiple combinations and gracefully fall back.
    """
    safe_query = sanitize_query(query)

    # These are "likely" valid values; we try several to avoid the 500 bug.
    # Keep list short for speed; reorder if you find one that’s stable.
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
        }

    last_err = None

    for depth, output_type in candidates:
        try:
            # REQUIRED positional signature in your SDK:
            # search(query, depth, output_type)
            return client.search(safe_query, depth, output_type)
        except Exception as e:
            last_err = e
            # tiny backoff helps if API is flaky
            time.sleep(0.2)

    # Fallback so the agent never crashes
    return {
        "error": True,
        "message": f"All Linkup attempts failed. Last error: {last_err}",
        "query_used": safe_query,
        "answer": "",
        "sources": [],
    }


if __name__ == "__main__":
    # Optional test (safe — won't crash even if Linkup returns 500)
    res = linkup_search("Google AI latest updates last 30 days")
    print("✅ linkup_search output:")
    print(res)
