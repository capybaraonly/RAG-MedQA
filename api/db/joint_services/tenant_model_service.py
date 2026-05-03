#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import enum
from common import settings
from common.constants import LLMType
from api.db.services.llm_service import LLMService
from api.db.services.tenant_llm_service import TenantLLMService


def get_model_config_by_id(tenant_model_id: int) -> dict:
    found, model_config = TenantLLMService.get_by_id(tenant_model_id)
    if not found:
        raise LookupError(f"Tenant Model with id {tenant_model_id} not found")
    config_dict = model_config.to_dict()
    llm = LLMService.query(llm_name=config_dict["llm_name"])
    if llm:
        config_dict["is_tools"] = llm[0].is_tools
    return config_dict


def get_model_config_by_type_and_name(model_type: str, model_name: str):
    if not model_name:
        raise Exception("Model Name is required")
    model_type_val = model_type.value if hasattr(model_type, "value") else model_type
    pure_model_name, fid = TenantLLMService.split_model_name_and_factory(model_name)

    # 直接读 settings / env 全局配置，不查数据库
    from api.db.system_config import get_system_llm_config

    config_dict = get_system_llm_config(model_type_val)
    if not config_dict or not config_dict.get("model"):
        compose_profiles = os.getenv("COMPOSE_PROFILES", "")
        is_tei_builtin_embedding = (
            model_type_val == LLMType.EMBEDDING.value
            and "tei-" in compose_profiles
            and pure_model_name == os.getenv("TEI_MODEL", "")
            and (fid == "Builtin" or fid is None)
        )
        if is_tei_builtin_embedding:
            embedding_cfg = settings.EMBEDDING_CFG
            config_dict = {
                "llm_factory": "Builtin",
                "api_key": embedding_cfg["api_key"],
                "llm_name": pure_model_name,
                "api_base": embedding_cfg["base_url"],
                "model_type": LLMType.EMBEDDING.value,
            }
        else:
            raise LookupError(f"Model with name {model_name} and type {model_type_val} not found in global config")

    config_dict["llm_name"] = config_dict.get("llm_name", pure_model_name)
    config_dict["model_type"] = config_dict.get("model_type", model_type_val)
    config_dict["llm_factory"] = config_dict.get("llm_factory", fid or config_dict.get("factory", ""))
    config_dict["api_base"] = config_dict.get("api_base", config_dict.get("base_url", ""))

    llm = LLMService.query(llm_name=pure_model_name)
    if llm:
        config_dict["is_tools"] = llm[0].is_tools
    return config_dict


def get_tenant_default_model_by_type(model_type: str):
    model_type_val = model_type if isinstance(model_type, str) else model_type.value

    # 读全局设置，不再查 Tenant 表
    match model_type_val:
        case LLMType.EMBEDDING.value:
            model_name = settings.EMBEDDING_MDL
        case LLMType.SPEECH2TEXT.value:
            model_name = settings.ASR_MDL
        case LLMType.IMAGE2TEXT.value:
            model_name = settings.IMAGE2TEXT_MDL
        case LLMType.CHAT.value:
            model_name = settings.CHAT_MDL
        case LLMType.RERANK.value:
            model_name = settings.RERANK_MDL
        case LLMType.TTS.value:
            model_name = getattr(settings, "TTS_MDL", "")
        case LLMType.OCR.value:
            raise Exception("OCR model name is required")
        case _:
            raise Exception(f"Unknown model type {model_type}")

    if not model_name:
        raise Exception(f"No default {model_type} model is configured in settings.")

    return get_model_config_by_type_and_name(model_type, model_name)
