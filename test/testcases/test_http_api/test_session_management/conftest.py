
#
import pytest
from common import batch_add_sessions_with_chat_assistant, delete_all_sessions_with_chat_assistant


@pytest.fixture(scope="class")
def add_sessions_with_chat_assistant(request, HttpApiAuth, add_chat_assistants):
    def cleanup():
        for chat_assistant_id in chat_assistant_ids:
            delete_all_sessions_with_chat_assistant(HttpApiAuth, chat_assistant_id)

    request.addfinalizer(cleanup)

    _, _, chat_assistant_ids = add_chat_assistants
    return chat_assistant_ids[0], batch_add_sessions_with_chat_assistant(HttpApiAuth, chat_assistant_ids[0], 5)


@pytest.fixture(scope="function")
def add_sessions_with_chat_assistant_func(request, HttpApiAuth, add_chat_assistants):
    def cleanup():
        for chat_assistant_id in chat_assistant_ids:
            delete_all_sessions_with_chat_assistant(HttpApiAuth, chat_assistant_id)

    request.addfinalizer(cleanup)

    _, _, chat_assistant_ids = add_chat_assistants
    return chat_assistant_ids[0], batch_add_sessions_with_chat_assistant(HttpApiAuth, chat_assistant_ids[0], 5)
