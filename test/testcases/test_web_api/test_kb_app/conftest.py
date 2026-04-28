
#
import pytest
from test_common import batch_create_datasets, list_datasets, delete_datasets
from libs.auth import RAG-MedQAWebApiAuth
from pytest import FixtureRequest
from RAG-MedQA_sdk import RAG-MedQA


@pytest.fixture(scope="class")
def add_datasets(request: FixtureRequest, client: RAG-MedQA, WebApiAuth: RAG-MedQAWebApiAuth) -> list[str]:
    dataset_ids = batch_create_datasets(WebApiAuth, 5)

    def cleanup():
        # Web KB cleanup cannot call SDK dataset bulk delete with empty ids; deletion must stay explicit.
        res = list_datasets(WebApiAuth, params={"page_size": 1000})
        existing_ids = {kb["id"] for kb in res["data"]}
        ids_to_delete = list({dataset_id for dataset_id in dataset_ids if dataset_id in existing_ids})
        delete_datasets(WebApiAuth, {"ids": ids_to_delete})

    request.addfinalizer(cleanup)
    return dataset_ids


@pytest.fixture(scope="function")
def add_datasets_func(request: FixtureRequest, client: RAG-MedQA, WebApiAuth: RAG-MedQAWebApiAuth) -> list[str]:
    dataset_ids = batch_create_datasets(WebApiAuth, 3)

    def cleanup():
        # Web KB cleanup cannot call SDK dataset bulk delete with empty ids; deletion must stay explicit.
        res = list_datasets(WebApiAuth, params={"page_size": 1000})
        existing_ids = {kb["id"] for kb in res["data"]}
        ids_to_delete = list({dataset_id for dataset_id in dataset_ids if dataset_id in existing_ids})
        delete_datasets(WebApiAuth, {"ids": ids_to_delete})

    request.addfinalizer(cleanup)
    return dataset_ids
