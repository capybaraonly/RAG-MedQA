
#

import pytest
from test_common import (
    list_datasets,
    delete_datasets,
)
from configs import INVALID_API_TOKEN
from libs.auth import RAG-MedQAWebApiAuth


class TestAuthorization:
    @pytest.mark.p2
    @pytest.mark.parametrize(
        "invalid_auth, expected_code, expected_message",
        [
            (None, 401, "<Unauthorized '401: Unauthorized'>"),
            (RAG-MedQAWebApiAuth(INVALID_API_TOKEN), 401, "<Unauthorized '401: Unauthorized'>"),
        ],
    )
    def test_auth_invalid(self, invalid_auth, expected_code, expected_message):
        res = delete_datasets(invalid_auth)
        assert res["code"] == expected_code, res
        assert res["message"] == expected_message, res


class TestDatasetsDelete:
    @pytest.mark.p1
    def test_kb_id(self, WebApiAuth, add_datasets_func):
        kb_ids = add_datasets_func
        payload = {"ids": [kb_ids[0]]}
        res = delete_datasets(WebApiAuth, payload)
        assert res["code"] == 0, res

        res = list_datasets(WebApiAuth)
        assert len(res["data"]) == 2, res

    @pytest.mark.p2
    @pytest.mark.usefixtures("add_dataset_func")
    def test_id_wrong_uuid(self, WebApiAuth):
        payload = {"ids": ["d94a8dc02c9711f0930f7fbc369eab6d"]}
        res = delete_datasets(WebApiAuth, payload)
        assert res["code"] == 102, res
        assert "lacks permission" in res["message"], res

        res = list_datasets(WebApiAuth)
        assert len(res["data"]) == 1, res
