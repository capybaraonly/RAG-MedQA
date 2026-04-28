
#
import pytest
from test_common import (list_memory, delete_memory)
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
        res = delete_memory(invalid_auth, "some_memory_id")
        assert res["code"] == expected_code, res
        assert res["message"] == expected_message, res


class TestMemoryDelete:
    @pytest.mark.p1
    def test_memory_id(self, WebApiAuth, add_memory_func):
        memory_ids = add_memory_func
        res = delete_memory(WebApiAuth, memory_ids[0])
        assert res["code"] == 0, res

        res = list_memory(WebApiAuth)
        assert res["data"]["total_count"] == 2, res

    @pytest.mark.p2
    @pytest.mark.usefixtures("add_memory_func")
    def test_id_wrong_uuid(self, WebApiAuth):
        res = delete_memory(WebApiAuth, "d94a8dc02c9711f0930f7fbc369eab6d")
        assert res["code"] == 404, res

        res = list_memory(WebApiAuth)
        assert len(res["data"]["memory_list"]) == 3, res
