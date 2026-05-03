
import asyncio
import logging
import json
import os
import time
import uuid
from copy import deepcopy

from peewee import IntegrityError

from api.db.db_models import init_database_tables as init_web_db, LLMFactories, LLM
from api.db.services import UserService
from api.db.services.canvas_service import CanvasTemplateService
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.tenant_llm_service import LLMFactoriesService
from api.db.services.llm_service import LLMService, LLMBundle
from api.db.services.system_settings_service import SystemSettingsService
from api.db.joint_services.memory_message_service import init_message_id_sequence, init_memory_size_cache, fix_missing_tokenized_memory
from api.db.joint_services.tenant_model_service import get_tenant_default_model_by_type
from common.file_utils import get_project_base_directory
from common import settings
from api.common.base64 import encode_to_base64

DEFAULT_SUPERUSER_NICKNAME = os.getenv("DEFAULT_SUPERUSER_NICKNAME", "admin")
DEFAULT_SUPERUSER_EMAIL = os.getenv("DEFAULT_SUPERUSER_EMAIL", "admin@RAG-MedQA.io")
DEFAULT_SUPERUSER_PASSWORD = os.getenv("DEFAULT_SUPERUSER_PASSWORD", "admin")

def init_superuser(nickname=DEFAULT_SUPERUSER_NICKNAME, email=DEFAULT_SUPERUSER_EMAIL, password=DEFAULT_SUPERUSER_PASSWORD, role=None):
    if UserService.query(email=email):
        logging.info("User with email %s already exists, skipping initialization.", email)
        return

    user_info = {
        "id": uuid.uuid1().hex,
        "password": encode_to_base64(password),
        "nickname": nickname,
        "is_superuser": True,
        "email": email,
        "creator": "system",
        "status": "1",
    }

    try:
        if not UserService.save(**user_info):
            logging.error("can't init admin.")
            return
    except IntegrityError:
        logging.info("User with email %s already exists, skipping.", email)
        return
    logging.info(
        f"Super user initialized. email: {email}, A default password has been set; changing the password after login is strongly recommended.")

    # Verify global LLM config (env-based, no DB dependency)
    chat_model_config = get_tenant_default_model_by_type(LLMType.CHAT)
    chat_mdl = LLMBundle(chat_model_config)
    msg = asyncio.run(chat_mdl.async_chat(system="", history=[{"role": "user", "content": "Hello!"}], gen_conf={}))
    if msg.find("ERROR: ") == 0:
        logging.error("'{}' doesn't work. {}".format(settings.CHAT_MDL, msg))

    embd_model_config = get_tenant_default_model_by_type(LLMType.EMBEDDING)
    embd_mdl = LLMBundle(embd_model_config)
    v, c = embd_mdl.encode(["Hello!"])
    if c == 0:
        logging.error("'{}' doesn't work!".format(settings.EMBEDDING_MDL))


def init_llm_factory():
    LLMFactoriesService.filter_delete([1 == 1])
    factory_llm_infos = settings.FACTORY_LLM_INFOS
    for factory_llm_info in factory_llm_infos:
        info = deepcopy(factory_llm_info)
        llm_infos = info.pop("llm")
        try:
            LLMFactoriesService.save(**info)
        except Exception:
            pass
        LLMService.filter_delete([LLM.fid == factory_llm_info["name"]])
        for llm_info in llm_infos:
            llm_info["fid"] = factory_llm_info["name"]
            try:
                LLMService.save(**llm_info)
            except Exception:
                pass

    LLMFactoriesService.filter_delete([(LLMFactories.name == "Local") | (LLMFactories.name == "novita.ai")])
    LLMService.filter_delete([LLM.fid == "Local"])
    LLMService.filter_delete([LLM.llm_name == "qwen-vl-max"])
    LLMService.filter_delete([LLM.fid == "Moonshot", LLM.llm_name == "flag-embedding"])
    LLMFactoriesService.filter_delete([LLMFactoriesService.model.name == "QAnything"])
    LLMService.filter_delete([LLMService.model.fid == "QAnything"])
    doc_count = DocumentService.get_all_kb_doc_count()
    for kb_id in KnowledgebaseService.get_all_ids():
        KnowledgebaseService.update_document_number_in_init(kb_id=kb_id, doc_num=doc_count.get(kb_id, 0))



def add_graph_templates():
    dir = os.path.join(get_project_base_directory(), "agent", "templates")
    CanvasTemplateService.filter_delete([1 == 1])
    if not os.path.exists(dir):
        logging.warning("Missing agent templates!")
        return

    for fnm in os.listdir(dir):
        try:
            with open(os.path.join(dir, fnm), "r", encoding="utf-8") as f:
                cnvs = json.load(f)
            try:
                CanvasTemplateService.save(**cnvs)
            except Exception:
                CanvasTemplateService.update_by_id(cnvs["id"], cnvs)
        except Exception as e:
            logging.exception(f"Add agent templates error: {e}")


def init_web_data():
    start_time = time.time()

    init_table()

    init_llm_factory()
    # if not UserService.get_all().count():
    #    init_superuser()

    add_graph_templates()
    init_message_id_sequence()
    init_memory_size_cache()
    fix_missing_tokenized_memory()
    logging.info("init web data success:{}".format(time.time() - start_time))

def init_table():
    # init system_settings
    with open(os.path.join(get_project_base_directory(), "conf", "system_settings.json"), "r") as f:
        records_from_file = json.load(f)["system_settings"]

    record_index = {}
    records_from_db = SystemSettingsService.get_all()
    for index, record in enumerate(records_from_db):
        record_index[record.name] = index

    to_save = []
    for record in records_from_file:
        setting_name = record["name"]
        if setting_name not in record_index:
            to_save.append(record)

    len_to_save = len(to_save)
    if len_to_save > 0:
        # not initialized
        try:
            SystemSettingsService.insert_many(to_save, len_to_save)
        except Exception as e:
            logging.exception("System settings init error: {}".format(e))
            raise e


if __name__ == '__main__':
    init_web_db()
    init_web_data()
