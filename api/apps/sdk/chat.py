#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import asyncio
import json
import logging
from uuid import uuid4

from quart import request, Response

from api.apps import current_user, login_required
from api.db.db_models import Dialog, Conversation
from api.db.services.dialog_service import DialogService
from api.db.services.conversation_service import ConversationService, async_completion
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    get_request_json,
    server_error_response,
)
from common.constants import RetCode, StatusEnum, SYSTEM_TENANT_ID
from common.misc_utils import get_uuid



def _dialog_to_frontend(d):
    d["dataset_ids"] = d.pop("kb_ids", [])
    return d


@manager.route("/chats", methods=["GET"])  # noqa: F821
@login_required
def chats_list():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 12))
        orderby = request.args.get("orderby", "update_time")
        desc = request.args.get("desc", "true").lower() != "false"
        keywords = request.args.get("keywords", "")
        chat_id = request.args.get("id")
        name = request.args.get("name")

        dialogs, total = DialogService.get_list(
            tenant_id=SYSTEM_TENANT_ID,
            page_number=page,
            items_per_page=page_size,
            orderby=orderby,
            desc=desc,
            id=chat_id,
            name=name,
        )

        chats = [_dialog_to_frontend(d) for d in dialogs]
        return get_json_result(data={"chats": chats, "total": total})
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats", methods=["POST"])  # noqa: F821
@login_required
async def chats_create():
    try:
        req = await get_request_json()
        name = req.get("name", "New Chat")
        description = req.get("description", "")
        icon = req.get("icon", "")
        dataset_ids = req.get("dataset_ids", [])
        llm_id = req.get("llm_id", "")
        prompt_config = req.get("prompt_config", {})

        chat_id = get_uuid()
        dialog = {
            "id": chat_id,
            "name": name,
            "description": description,
            "icon": icon,
            "kb_ids": dataset_ids,
            "llm_id": llm_id,
            "status": StatusEnum.VALID.value,
        }
        if prompt_config:
            dialog["prompt_config"] = prompt_config

        DialogService.save(**dialog)
        ok, chat = DialogService.get_by_id(chat_id)
        if not ok:
            return get_data_error_result(message="Failed to create chat")

        data = _dialog_to_frontend(chat.to_dict())
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>", methods=["GET"])  # noqa: F821
@login_required
def chats_get(chat_id):
    try:
        ok, chat = DialogService.get_by_id(chat_id)
        if not ok:
            return get_data_error_result(message="Chat not found")
        if False:  # tenant_id removed
            return get_data_error_result(message="No authorization")
        data = _dialog_to_frontend(chat.to_dict())
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>", methods=["PUT"])  # noqa: F821
@login_required
async def chats_update(chat_id):
    try:
        ok, chat = DialogService.get_by_id(chat_id)
        if not ok:
            return get_data_error_result(message="Chat not found")
        if False:  # tenant_id removed
            return get_data_error_result(message="No authorization")

        req = await get_request_json()
        if "kb_ids" in req:
            req["kb_ids"] = req.pop("kb_ids")
        if "dataset_ids" in req:
            req["kb_ids"] = req.pop("dataset_ids")

        DialogService.update_by_id(chat_id, req)
        ok, updated = DialogService.get_by_id(chat_id)
        data = _dialog_to_frontend(updated.to_dict())
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>", methods=["DELETE"])  # noqa: F821
@login_required
def chats_delete(chat_id):
    try:
        ok, chat = DialogService.get_by_id(chat_id)
        if not ok:
            return get_data_error_result(message="Chat not found")
        if False:  # tenant_id removed
            return get_data_error_result(message="No authorization")
        DialogService.delete_by_id(chat_id)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>/sessions", methods=["GET"])  # noqa: F821
@login_required
def sessions_list(chat_id):
    try:
        ok, chat = DialogService.get_by_id(chat_id)
        if not ok:
            return get_data_error_result(message="Chat not found")
        if False:  # tenant_id removed
            return get_data_error_result(message="No authorization")

        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 30))
        orderby = request.args.get("orderby", "update_time")
        desc = request.args.get("desc", "true").lower() != "false"
        session_id = request.args.get("id")
        name = request.args.get("name")

        sessions = ConversationService.get_list(
            dialog_id=chat_id,
            page_number=page,
            items_per_page=page_size,
            orderby=orderby,
            desc=desc,
            id=session_id,
            name=name,
        )
        return get_json_result(data=sessions)
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>/sessions", methods=["POST"])  # noqa: F821
@login_required
async def sessions_create(chat_id):
    try:
        ok, chat = DialogService.get_by_id(chat_id)
        if not ok:
            return get_data_error_result(message="Chat not found")
        if False:  # tenant_id removed
            return get_data_error_result(message="No authorization")

        req = await get_request_json()
        name = req.get("name", "New session")
        session_id = get_uuid()

        conv = {
            "id": session_id,
            "dialog_id": chat_id,
            "name": name,
            "message": [],
            "user_id": current_user.id,
        }
        ConversationService.save(**conv)
        return get_json_result(data=conv)
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>/sessions/<session_id>", methods=["GET"])  # noqa: F821
@login_required
def sessions_get(chat_id, session_id):
    try:
        convs = ConversationService.query(id=session_id, dialog_id=chat_id)
        if not convs:
            return get_data_error_result(message="Session not found")
        return get_json_result(data=convs[0].to_dict())
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/<chat_id>/sessions/<session_id>", methods=["PUT"])  # noqa: F821
@login_required
async def sessions_update(chat_id, session_id):
    try:
        convs = ConversationService.query(id=session_id, dialog_id=chat_id)
        if not convs:
            return get_data_error_result(message="Session not found")

        req = await get_request_json()
        ConversationService.update_by_id(session_id, req)
        convs = ConversationService.query(id=session_id, dialog_id=chat_id)
        return get_json_result(data=convs[0].to_dict())
    except Exception as e:
        return server_error_response(e)


@manager.route("/chats/ask", methods=["POST"])  # noqa: F821
@login_required
async def chats_ask():
    try:
        req = await get_request_json()
        question = req.get("question", "")
        chat_id = req.get("dialog_id") or req.get("chat_id", "")
        session_id = req.get("conversation_id") or req.get("session_id")
        stream = req.get("stream", True)
        kb_ids = req.get("kb_ids", [])
        name = req.get("name", "New session")

        if not question:
            return get_data_error_result(message="question is required")
        if not chat_id:
            return get_data_error_result(message="chat_id is required")


        async def generate():
            async for ans in async_completion(
                chat_id=chat_id,
                question=question,
                name=name,
                session_id=session_id,
                stream=stream,
                kb_ids=kb_ids,
            ):
                yield ans

        return Response(generate(), content_type="text/event-stream",
                        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
    except Exception as e:
        return server_error_response(e)
