
#
import pytest
from test_common import llm_factories, llm_list
from configs import INVALID_API_TOKEN
from libs.auth import RAG-MedQAWebApiAuth


INVALID_AUTH_CASES = [
    (None, 401, "<Unauthorized '401: Unauthorized'>"),
    (RAG-MedQAWebApiAuth(INVALID_API_TOKEN), 401, "<Unauthorized '401: Unauthorized'>"),
]


class TestAuthorization:
    @pytest.mark.p2
    @pytest.mark.parametrize("invalid_auth, expected_code, expected_message", INVALID_AUTH_CASES)
    def test_auth_invalid_factories(self, invalid_auth, expected_code, expected_message):
        res = llm_factories(invalid_auth)
        assert res["code"] == expected_code, res
        assert res["message"] == expected_message, res

    @pytest.mark.p2
    @pytest.mark.parametrize("invalid_auth, expected_code, expected_message", INVALID_AUTH_CASES)
    def test_auth_invalid_list(self, invalid_auth, expected_code, expected_message):
        res = llm_list(invalid_auth)
        assert res["code"] == expected_code, res
        assert res["message"] == expected_message, res


class TestLLMList:
    @pytest.mark.p1
    def test_factories(self, WebApiAuth):
        res = llm_factories(WebApiAuth)
        assert res["code"] == 0, res
        assert isinstance(res["data"], list), res

    @pytest.mark.p1
    def test_list(self, WebApiAuth):
        res = llm_list(WebApiAuth)
        assert res["code"] == 0, res
        assert isinstance(res["data"], dict), res
