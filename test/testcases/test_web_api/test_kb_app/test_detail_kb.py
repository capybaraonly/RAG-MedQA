
#
import pytest
from test_common import (
    detail_kb,
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
        res = detail_kb(invalid_auth)
        assert res["code"] == expected_code, res
        assert res["message"] == expected_message, res


class TestDatasetsDetail:
    @pytest.mark.p1
    def test_kb_id(self, WebApiAuth, add_dataset):
        kb_id = add_dataset
        payload = {"kb_id": kb_id}
        res = detail_kb(WebApiAuth, payload)
        assert res["code"] == 0, res
        assert res["data"]["name"] == "kb_0"

    @pytest.mark.p2
    def test_id_wrong_uuid(self, WebApiAuth):
        payload = {"kb_id": "d94a8dc02c9711f0930f7fbc369eab6d"}
        res = detail_kb(WebApiAuth, payload)
        assert res["code"] == 103, res
        assert "Only owner of dataset authorized for this operation." in res["message"], res
