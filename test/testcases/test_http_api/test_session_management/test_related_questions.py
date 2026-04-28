
#
import pytest
from common import related_questions
from configs import INVALID_API_TOKEN
from libs.auth import RAG-MedQAHttpApiAuth


class TestRelatedQuestions:
    @pytest.mark.p3
    def test_related_questions_success(self, HttpApiAuth):
        res = related_questions(HttpApiAuth, {"question": "RAG-MedQA", "industry": "search"})
        assert res["code"] == 0, res
        assert isinstance(res.get("data"), list), res

    @pytest.mark.p2
    def test_related_questions_missing_question(self, HttpApiAuth):
        res = related_questions(HttpApiAuth, {"industry": "search"})
        assert res["code"] == 102, res
        assert "question" in res.get("message", ""), res

    @pytest.mark.p2
    def test_related_questions_invalid_auth(self):
        res = related_questions(RAG-MedQAHttpApiAuth(INVALID_API_TOKEN), {"question": "RAG-MedQA", "industry": "search"})
        assert res["code"] == 109, res
        assert "API key is invalid" in res.get("message", ""), res
