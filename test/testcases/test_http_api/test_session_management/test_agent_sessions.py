
#
import pytest
import requests
from common import (
    create_agent,
    create_agent_session,
    delete_agent,
    delete_all_agent_sessions,
    delete_agent_sessions,
    list_agent_sessions,
    list_agents,
)
from configs import HOST_ADDRESS, VERSION

AGENT_TITLE = "test_agent_http"
MINIMAL_DSL = {
    "components": {
        "begin": {
            "obj": {"component_name": "Begin", "params": {}},
            "downstream": ["message"],
            "upstream": [],
        },
        "message": {
            "obj": {"component_name": "Message", "params": {"content": ["{sys.query}"]}},
            "downstream": [],
            "upstream": ["begin"],
        },
    },
    "history": [],
    "retrieval": [],
    "path": [],
    "globals": {
        "sys.query": "",
        "sys.user_id": "",
        "sys.conversation_turns": 0,
        "sys.files": [],
    },
    "variables": {},
}

@pytest.fixture(scope="function")
def agent_id(HttpApiAuth, request):
    res = list_agents(HttpApiAuth, {"page_size": 1000})
    assert res["code"] == 0, res
    for agent in res.get("data", []):
        if agent.get("title") == AGENT_TITLE:
            delete_agent(HttpApiAuth, agent["id"])

    res = create_agent(HttpApiAuth, {"title": AGENT_TITLE, "dsl": MINIMAL_DSL})
    assert res["code"] == 0, res
    res = list_agents(HttpApiAuth, {"title": AGENT_TITLE})
    assert res["code"] == 0, res
    assert res.get("data"), res
    agent_id = res["data"][0]["id"]

    def cleanup():
        delete_all_agent_sessions(HttpApiAuth, agent_id)
        delete_agent(HttpApiAuth, agent_id)

    request.addfinalizer(cleanup)
    return agent_id


class TestAgentSessions:
    @pytest.mark.p2
    def test_delete_agent_sessions_empty_ids_noop(self, HttpApiAuth, agent_id):
        res = create_agent_session(HttpApiAuth, agent_id, payload={})
        assert res["code"] == 0, res
        session_id = res["data"]["id"]

        res = delete_agent_sessions(HttpApiAuth, agent_id, {"ids": []})
        assert res["code"] == 0, res

        res = list_agent_sessions(HttpApiAuth, agent_id, params={"id": session_id})
        assert res["code"] == 0, res
        assert len(res["data"]) == 1, res

    @pytest.mark.p2
    def test_create_list_delete_agent_sessions(self, HttpApiAuth, agent_id):
        res = create_agent_session(HttpApiAuth, agent_id, payload={})
        assert res["code"] == 0, res
        session_id = res["data"]["id"]
        assert res["data"]["agent_id"] == agent_id, res

        res = list_agent_sessions(HttpApiAuth, agent_id, params={"id": session_id})
        assert res["code"] == 0, res
        assert len(res["data"]) == 1, res
        assert res["data"][0]["id"] == session_id, res

        res = delete_agent_sessions(HttpApiAuth, agent_id, {"ids": [session_id]})
        assert res["code"] == 0, res

    @pytest.mark.p2
    def test_agent_crud_validation_contract(self, HttpApiAuth, agent_id):
        res = list_agents(HttpApiAuth, {"id": "missing-agent-id", "title": "missing-agent-title"})
        assert res["code"] == 102, res
        assert "doesn't exist" in res["message"], res

        res = list_agents(HttpApiAuth, {"title": AGENT_TITLE, "desc": "true", "page_size": 1})
        assert res["code"] == 0, res

        res = create_agent(HttpApiAuth, {"title": "missing-dsl-agent"})
        assert res["code"] == 101, res
        assert "No DSL data in request" in res["message"], res

        res = create_agent(HttpApiAuth, {"dsl": MINIMAL_DSL})
        assert res["code"] == 101, res
        assert "No title in request" in res["message"], res

        res = create_agent(HttpApiAuth, {"title": AGENT_TITLE, "dsl": MINIMAL_DSL})
        assert res["code"] == 102, res
        assert "already exists" in res["message"], res

        update_url = f"{HOST_ADDRESS}/api/{VERSION}/agents/invalid-agent-id"
        res = requests.put(update_url, auth=HttpApiAuth, json={"title": "updated", "dsl": MINIMAL_DSL}).json()
        assert res["code"] == 103, res
        assert "Only owner of canvas authorized" in res["message"], res

        res = delete_agent(HttpApiAuth, "invalid-agent-id")
        assert res["code"] == 103, res
        assert "Only owner of canvas authorized" in res["message"], res
