
#
import os
from time import sleep
from RAG-MedQA_sdk import RAG-MedQA
from configs import HOST_ADDRESS, VERSION
import pytest
from test_common import (
    batch_add_chunks,
    batch_create_datasets,
    bulk_upload_documents,
    delete_chunks,
    delete_chats,
    list_chunks,
    list_documents,
    list_datasets,
    parse_documents,
    delete_datasets,
)
from libs.auth import RAG-MedQAWebApiAuth
from pytest import FixtureRequest
from utils import wait_for
from utils.file_utils import (
    create_docx_file,
    create_eml_file,
    create_excel_file,
    create_html_file,
    create_image_file,
    create_json_file,
    create_md_file,
    create_pdf_file,
    create_ppt_file,
    create_txt_file,
)


@wait_for(30, 1, "Document parsing timeout")
def condition(_auth, _kb_id):
    res = list_documents(_auth, {"id": _kb_id})
    for doc in res["data"]["docs"]:
        if doc["run"] != "3":
            return False
    return True


@pytest.fixture
def generate_test_files(request: FixtureRequest, tmp_path):
    file_creators = {
        "docx": (tmp_path / "RAG-MedQA_test.docx", create_docx_file),
        "excel": (tmp_path / "RAG-MedQA_test.xlsx", create_excel_file),
        "ppt": (tmp_path / "RAG-MedQA_test.pptx", create_ppt_file),
        "image": (tmp_path / "RAG-MedQA_test.png", create_image_file),
        "pdf": (tmp_path / "RAG-MedQA_test.pdf", create_pdf_file),
        "txt": (tmp_path / "RAG-MedQA_test.txt", create_txt_file),
        "md": (tmp_path / "RAG-MedQA_test.md", create_md_file),
        "json": (tmp_path / "RAG-MedQA_test.json", create_json_file),
        "eml": (tmp_path / "RAG-MedQA_test.eml", create_eml_file),
        "html": (tmp_path / "RAG-MedQA_test.html", create_html_file),
    }

    files = {}
    for file_type, (file_path, creator_func) in file_creators.items():
        if request.param in ["", file_type]:
            creator_func(file_path)
            files[file_type] = file_path
    return files


@pytest.fixture(scope="class")
def RAG-MedQA_tmp_dir(request, tmp_path_factory):
    class_name = request.cls.__name__
    return tmp_path_factory.mktemp(class_name)
@pytest.fixture(scope="session")
def client(token: str) -> RAG-MedQA:
    return RAG-MedQA(api_key=token, base_url=HOST_ADDRESS, version=VERSION)

@pytest.fixture(scope="session")
def WebApiAuth(auth):
    return RAG-MedQAWebApiAuth(auth)


@pytest.fixture
def require_env_flag():
    def _require(flag, value="1"):
        if os.getenv(flag) != value:
            pytest.skip(f"Requires {flag}={value}")

    return _require


@pytest.fixture(scope="function")
def clear_datasets(request: FixtureRequest, WebApiAuth: RAG-MedQAWebApiAuth):
    def cleanup():
        res = list_datasets(WebApiAuth, params={"page_size": 1000})
        kb_ids = [kb["id"] for kb in res["data"]]
        delete_datasets(WebApiAuth, {"ids": kb_ids})

    request.addfinalizer(cleanup)


@pytest.fixture(scope="function")
def clear_chats(request, WebApiAuth):
    def cleanup():
        delete_chats(WebApiAuth)

    request.addfinalizer(cleanup)


@pytest.fixture(scope="class")
def add_dataset(request: FixtureRequest, WebApiAuth: RAG-MedQAWebApiAuth) -> str:
    def cleanup():
        res = list_datasets(WebApiAuth, params={"page_size": 1000})
        kb_ids = [kb["id"] for kb in res["data"]]
        delete_datasets(WebApiAuth, {"ids": kb_ids})

    request.addfinalizer(cleanup)
    return batch_create_datasets(WebApiAuth, 1)[0]


@pytest.fixture(scope="function")
def add_dataset_func(request: FixtureRequest, WebApiAuth: RAG-MedQAWebApiAuth) -> str:
    def cleanup():
        res = list_datasets(WebApiAuth, params={"page_size": 1000})
        kb_ids = [kb["id"] for kb in res["data"]]
        delete_datasets(WebApiAuth, {"ids": kb_ids})

    request.addfinalizer(cleanup)
    return batch_create_datasets(WebApiAuth, 1)[0]


@pytest.fixture(scope="class")
def add_document(request, WebApiAuth, add_dataset, RAG-MedQA_tmp_dir):
    #     def cleanup():
    #         res = list_documents(WebApiAuth, {"kb_id": dataset_id})
    #         for doc in res["data"]["docs"]:
    #             delete_document(WebApiAuth, {"doc_id": doc["id"]})

    #     request.addfinalizer(cleanup)

    dataset_id = add_dataset
    return dataset_id, bulk_upload_documents(WebApiAuth, dataset_id, 1, RAG-MedQA_tmp_dir)[0]


@pytest.fixture(scope="class")
def add_chunks(request, WebApiAuth, add_document):
    def cleanup():
        res = list_chunks(WebApiAuth, {"doc_id": document_id})
        if res["code"] == 0:
            chunk_ids = [chunk["chunk_id"] for chunk in res["data"]["chunks"]]
            delete_chunks(WebApiAuth, {"doc_id": document_id, "chunk_ids": chunk_ids})

    request.addfinalizer(cleanup)

    kb_id, document_id = add_document
    parse_documents(WebApiAuth, {"doc_ids": [document_id], "run": "1"})
    condition(WebApiAuth, kb_id)
    chunk_ids = batch_add_chunks(WebApiAuth, document_id, 4)
    # issues/6487
    sleep(1)
    return kb_id, document_id, chunk_ids
