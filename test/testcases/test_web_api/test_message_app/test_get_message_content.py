
#
import random

import pytest
from test_common import get_message_content, get_recent_message
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
        res = get_message_content(invalid_auth, "empty_memory_id", 0)
        assert res["code"] == expected_code, res
        assert res["message"] == expected_message, res


@pytest.mark.usefixtures("add_memory_with_multiple_type_message_func")
class TestGetMessageContent:

    @pytest.mark.p1
    def test_get_message_content(self, WebApiAuth):
        memory_id = self.memory_id
        recent_messages = get_recent_message(WebApiAuth, {"memory_id": memory_id})
        assert len(recent_messages["data"]) > 0, recent_messages
        message = random.choice(recent_messages["data"])
        message_id = message["message_id"]
        content_res = get_message_content(WebApiAuth, memory_id, message_id)
        for field in ["content", "content_embed"]:
            assert field in content_res["data"]
            assert content_res["data"][field] is not None, content_res

    @pytest.mark.p2
    def test_get_message_content_invalid_memory_id(self, WebApiAuth):
        res = get_message_content(WebApiAuth, "missing_memory_id", 1)
        assert res["code"] == 404, res
        assert "not found" in res["message"].lower(), res

    @pytest.mark.p2
    def test_get_message_content_invalid_message_id(self, WebApiAuth):
        memory_id = self.memory_id
        res = get_message_content(WebApiAuth, memory_id, 999999999)
        assert res["code"] == 404, res
        assert "not found" in res["message"].lower(), res
