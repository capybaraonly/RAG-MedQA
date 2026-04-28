
#
import pytest
from common import batch_create_chat_assistants, delete_all_chat_assistants, get_chat_assistant, list_documents, parse_documents
from utils import wait_for


@wait_for(30, 1, "Document parsing timeout")
def condition(_auth, _dataset_id):
    res = list_documents(_auth, _dataset_id)
    for doc in res["data"]["docs"]:
        if doc["run"] != "DONE":
            return False
    return True


@pytest.fixture(scope="function")
def add_chat_assistants_func(request, HttpApiAuth, add_document):
    def cleanup():
        delete_all_chat_assistants(HttpApiAuth)

    request.addfinalizer(cleanup)

    dataset_id, document_id = add_document
    parse_documents(HttpApiAuth, dataset_id, {"document_ids": [document_id]})
    condition(HttpApiAuth, dataset_id)
    return dataset_id, document_id, batch_create_chat_assistants(HttpApiAuth, 5)


@pytest.fixture(scope="function")
def chat_assistant_llm_model_type(HttpApiAuth, add_chat_assistants_func):
    _, _, chat_assistant_ids = add_chat_assistants_func
    res = get_chat_assistant(HttpApiAuth, chat_assistant_ids[0])
    if res.get("code") == 0 and res.get("data"):
        return res["data"].get("llm_setting", {}).get("model_type", "chat")
    return "chat"
