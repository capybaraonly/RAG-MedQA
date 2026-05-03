
import os
import json
import logging
from langfuse import Langfuse
from common import settings
from common.constants import MINERU_DEFAULT_CONFIG, MINERU_ENV_KEYS, PADDLEOCR_DEFAULT_CONFIG, PADDLEOCR_ENV_KEYS, LLMType
from api.db.db_models import DB, LLMFactories
from api.db.services.common_service import CommonService
from rag.llm import ChatModel, CvModel, EmbeddingModel, OcrModel, RerankModel, Seq2txtModel, TTSModel


class LLMFactoriesService(CommonService):
    model = LLMFactories


class TenantLLMService:
    """TenantLLM service simplified for tenant-less architecture.

    DB-dependent methods (query, save, get_api_key, etc.) are removed
    since TenantLLM table no longer exists. Utility methods are kept.
    """

    @staticmethod
    def split_model_name_and_factory(model_name):
        arr = model_name.split("@")
        if len(arr) < 2:
            return model_name, None
        if len(arr) > 2:
            return "@".join(arr[0:-1]), arr[-1]

        try:
            model_factories = settings.FACTORY_LLM_INFOS
            model_providers = set([f["name"] for f in model_factories])
            if arr[-1] not in model_providers:
                return model_name, None
            return arr[0], arr[-1]
        except Exception as e:
            logging.exception(f"TenantLLMService.split_model_name_and_factory got exception: {e}")
        return model_name, None

    @classmethod
    def model_instance(cls, model_config: dict, lang="Chinese", **kwargs):
        if not model_config:
            raise LookupError("Model config is required")
        kwargs.update({"provider": model_config["llm_factory"]})
        if model_config["model_type"] == LLMType.EMBEDDING.value:
            if model_config["llm_factory"] not in EmbeddingModel:
                return None
            return EmbeddingModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], base_url=model_config["api_base"])

        elif model_config["model_type"] == LLMType.RERANK:
            if model_config["llm_factory"] not in RerankModel:
                return None
            return RerankModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], base_url=model_config["api_base"])

        elif model_config["model_type"] == LLMType.IMAGE2TEXT.value:
            if model_config["llm_factory"] not in CvModel:
                return None
            return CvModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], lang, base_url=model_config["api_base"], **kwargs)

        elif model_config["model_type"] == LLMType.CHAT.value:
            if model_config["llm_factory"] not in ChatModel:
                return None
            return ChatModel[model_config["llm_factory"]](model_config["api_key"], model_config["llm_name"], base_url=model_config["api_base"], **kwargs)

        elif model_config["model_type"] == LLMType.SPEECH2TEXT:
            if model_config["llm_factory"] not in Seq2txtModel:
                return None
            return Seq2txtModel[model_config["llm_factory"]](key=model_config["api_key"], model_name=model_config["llm_name"], lang=lang, base_url=model_config["api_base"])
        elif model_config["model_type"] == LLMType.TTS:
            if model_config["llm_factory"] not in TTSModel:
                return None
            return TTSModel[model_config["llm_factory"]](
                model_config["api_key"],
                model_config["llm_name"],
                base_url=model_config["api_base"],
            )

        elif model_config["model_type"] == LLMType.OCR:
            if model_config["llm_factory"] not in OcrModel:
                return None
            return OcrModel[model_config["llm_factory"]](
                key=model_config["api_key"],
                model_name=model_config["llm_name"],
                base_url=model_config.get("api_base", ""),
                **kwargs,
            )

        return None

    @classmethod
    def increase_usage_by_id(cls, tenant_model_id: int, used_tokens: int):
        """No-op: token usage tracking is handled at the LLM provider level."""
        return 1

    @staticmethod
    def llm_id2llm_type(llm_id: str) -> str | None:
        from api.db.services.llm_service import LLMService

        llm_id, *_ = TenantLLMService.split_model_name_and_factory(llm_id)
        llm_factories = settings.FACTORY_LLM_INFOS
        for llm_factory in llm_factories:
            for llm in llm_factory["llm"]:
                if llm_id == llm["llm_name"]:
                    return llm["model_type"].split(",")[-1]

        for llm in LLMService.query(llm_name=llm_id):
            return llm.model_type

        return None

    # ── Stubs for backward compatibility ──

    @classmethod
    def get_my_llms(cls, tenant_id):
        return []

    @classmethod
    def get_api_key(cls, tenant_id, model_name, model_type=None):
        return None

    @classmethod
    def ensure_mineru_from_env(cls, tenant_id: str) -> str | None:
        return None

    @classmethod
    def query(cls, **kwargs):
        return []

    @classmethod
    def get_or_none(cls, **kwargs):
        return None

    @classmethod
    def save(cls, **kwargs):
        pass

    @classmethod
    def insert_many(cls, rows):
        pass

    @classmethod
    def filter_update(cls, conditions, updates):
        return 0

    @classmethod
    def filter_delete(cls, conditions):
        return 0


class LLM4Tenant:
    def __init__(self, model_config: dict, lang="Chinese", **kwargs):
        self.llm_name = model_config["llm_name"]
        self.model_config = model_config
        self.mdl = TenantLLMService.model_instance(model_config, lang=lang, **kwargs)
        assert self.mdl, "Can't find model for {}/{}".format(model_config.get("llm_type", model_config.get("model_type", "?")), model_config["llm_name"])
        self.max_length = model_config.get("max_tokens", 8192)

        self.is_tools = model_config.get("is_tools", False)
        self.verbose_tool_use = kwargs.get("verbose_tool_use")

        self.langfuse = None
        langfuse_secret = os.environ.get("LANGFUSE_SECRET_KEY")
        langfuse_public = os.environ.get("LANGFUSE_PUBLIC_KEY")
        if langfuse_secret and langfuse_public:
            langfuse = Langfuse(public_key=langfuse_public, secret_key=langfuse_secret, host=os.environ.get("LANGFUSE_HOST"))
            try:
                if langfuse.auth_check():
                    self.langfuse = langfuse
                    trace_id = self.langfuse.create_trace_id()
                    self.trace_context = {"trace_id": trace_id}
            except Exception:
                pass
