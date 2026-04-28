
#
import pytest
from common import delete_knowledge_graph, knowledge_graph
from configs import INVALID_API_TOKEN
from libs.auth import RAG-MedQAHttpApiAuth


@pytest.mark.p2
class TestAuthorization:
    @pytest.mark.parametrize(
        "invalid_auth, expected_code, expected_message",
        [
            (None, 401, "<Unauthorized '401: Unauthorized'>"),
            (RAG-MedQAHttpApiAuth(INVALID_API_TOKEN), 401, "<Unauthorized '401: Unauthorized'>"),
        ],
    )
    def test_invalid_auth(self, invalid_auth, expected_code, expected_message):
        res = knowledge_graph(invalid_auth, "dataset_id")
        assert res["code"] == expected_code
        assert expected_message in res.get("message", "")


class TestKnowledgeGraph:
    @pytest.mark.p2
    def test_get_knowledge_graph_empty(self, HttpApiAuth, add_dataset_func):
        dataset_id = add_dataset_func
        res = knowledge_graph(HttpApiAuth, dataset_id)
        assert res["code"] == 0, res
        assert "graph" in res["data"], res
        assert "mind_map" in res["data"], res
        assert isinstance(res["data"]["graph"], dict), res
        assert isinstance(res["data"]["mind_map"], dict), res

    @pytest.mark.p2
    def test_delete_knowledge_graph(self, HttpApiAuth, add_dataset_func):
        dataset_id = add_dataset_func
        res = delete_knowledge_graph(HttpApiAuth, dataset_id)
        assert res["code"] == 0, res
        assert res["data"] is True, res
