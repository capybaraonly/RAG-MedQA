
#


import pytest
from common import bulk_upload_documents, delete_all_documents


@pytest.fixture(scope="function")
def add_document_func(request, HttpApiAuth, add_dataset, RAG-MedQA_tmp_dir):
    def cleanup():
        delete_all_documents(HttpApiAuth, dataset_id)

    request.addfinalizer(cleanup)

    dataset_id = add_dataset
    return dataset_id, bulk_upload_documents(HttpApiAuth, dataset_id, 1, RAG-MedQA_tmp_dir)[0]


@pytest.fixture(scope="class")
def add_documents(request, HttpApiAuth, add_dataset, RAG-MedQA_tmp_dir):
    def cleanup():
        delete_all_documents(HttpApiAuth, dataset_id)

    request.addfinalizer(cleanup)

    dataset_id = add_dataset
    return dataset_id, bulk_upload_documents(HttpApiAuth, dataset_id, 5, RAG-MedQA_tmp_dir)


@pytest.fixture(scope="function")
def add_documents_func(request, HttpApiAuth, add_dataset_func, RAG-MedQA_tmp_dir):
    def cleanup():
        delete_all_documents(HttpApiAuth, dataset_id)

    request.addfinalizer(cleanup)

    dataset_id = add_dataset_func
    return dataset_id, bulk_upload_documents(HttpApiAuth, dataset_id, 3, RAG-MedQA_tmp_dir)
