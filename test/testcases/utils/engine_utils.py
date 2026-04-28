
#
import os
import requests

_DOC_ENGINE_CACHE = None


def get_doc_engine(rag=None) -> str:
    """Return lower-cased doc_engine from env, or from /system/status if env is unset."""
    global _DOC_ENGINE_CACHE
    env = (os.getenv("DOC_ENGINE") or "").strip().lower()
    if env:
        _DOC_ENGINE_CACHE = env
        return env
    if _DOC_ENGINE_CACHE:
        return _DOC_ENGINE_CACHE
    if rag is None:
        return ""
    try:
        api_url = getattr(rag, "api_url", "")
        if "/api/" in api_url:
            base_url, version = api_url.rsplit("/api/", 1)
            status_url = f"{base_url}/{version}/system/status"
        else:
            status_url = f"{api_url}/system/status"
        headers = getattr(rag, "authorization_header", {})
        res = requests.get(status_url, headers=headers).json()
        engine = str(res.get("data", {}).get("doc_engine", {}).get("type", "")).lower()
        if engine:
            _DOC_ENGINE_CACHE = engine
        return engine
    except Exception:
        return ""
