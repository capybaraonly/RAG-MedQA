from common import settings
from common.constants import LLMType


def _safe_get(cfg, key, default=""):
    """安全读取配置，兼容 str/dict 两种类型。"""
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    if key == "model":
        return cfg if isinstance(cfg, str) and cfg else default
    return default


def get_system_llm_config(model_type: str) -> dict:
    """从全局配置返回 LLM 配置，替代 TenantLLM 表查询。"""
    cfg_map = {
        LLMType.CHAT: (lambda: settings.CHAT_MDL, lambda: settings.CHAT_CFG),
        LLMType.EMBEDDING: (lambda: settings.EMBEDDING_MDL, lambda: settings.EMBEDDING_CFG),
        LLMType.RERANK: (lambda: settings.RERANK_MDL, lambda: settings.RERANK_CFG),
        LLMType.SPEECH2TEXT: (lambda: settings.ASR_MDL, lambda: settings.ASR_CFG),
        LLMType.IMAGE2TEXT: (lambda: settings.IMAGE2TEXT_MDL, lambda: settings.IMAGE2TEXT_CFG),
    }

    pair = cfg_map.get(model_type)
    if pair:
        mdl_getter, cfg_getter = pair
        cfg = cfg_getter()
        return {
            "model": _safe_get(cfg, "model", mdl_getter()),
            "factory": _safe_get(cfg, "factory"),
            "api_key": _safe_get(cfg, "api_key") or settings.API_KEY or "",
            "base_url": _safe_get(cfg, "base_url") or settings.LLM_BASE_URL or "",
        }

    return {
        "model": "",
        "factory": "",
        "api_key": settings.API_KEY or "",
        "base_url": settings.LLM_BASE_URL or "",
    }
