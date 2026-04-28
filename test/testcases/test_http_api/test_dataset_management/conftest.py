
#


import pytest
from common import batch_create_datasets, delete_all_datasets


@pytest.fixture(scope="class")
def add_datasets(HttpApiAuth, request):
    def cleanup():
        delete_all_datasets(HttpApiAuth)

    request.addfinalizer(cleanup)

    return batch_create_datasets(HttpApiAuth, 5)


@pytest.fixture(scope="function")
def add_datasets_func(HttpApiAuth, request):
    def cleanup():
        delete_all_datasets(HttpApiAuth)

    request.addfinalizer(cleanup)

    return batch_create_datasets(HttpApiAuth, 3)
