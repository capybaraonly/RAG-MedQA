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

import logging

from quart import jsonify, request

from api.apps import current_user, login_required
from api.apps.services.file_api_service import (
    create_folder,
    delete_files,
    get_all_parent_folders,
    get_file_content,
    get_parent_folder,
    list_files,
    move_files,
    upload_file,
)
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    get_request_json,
    server_error_response,
)


@manager.route("/files", methods=["GET"])  # noqa: F821
@login_required
def files_list():
    try:
        args = {
            "parent_id": request.args.get("parent_id"),
            "keywords": request.args.get("keywords", ""),
            "page": request.args.get("page", 1),
            "page_size": request.args.get("page_size", 15),
            "orderby": request.args.get("orderby", "create_time"),
            "desc": request.args.get("desc", "true").lower() != "false",
        }
        ok, result = list_files(current_user.id, args)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


@manager.route("/files", methods=["POST"])  # noqa: F821
@login_required
async def files_upload():
    try:
        # Check if this is a folder creation or file upload
        content_type = request.content_type or ""
        if "multipart" in content_type:
            files = (await request.files).getlist("file")
            pf_id = (await request.form).get("parent_id", "")
            ok, result = await upload_file(current_user.id, pf_id, files)
        else:
            req = await get_request_json()
            name = req.get("name", "New Folder")
            pf_id = req.get("parent_id")
            file_type = req.get("type")
            ok, result = await create_folder(current_user.id, name, pf_id, file_type)

        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


@manager.route("/files", methods=["DELETE"])  # noqa: F821
@login_required
async def files_delete():
    try:
        req = await get_request_json()
        ids = req.get("ids", []) if req else []
        ok, result = await delete_files(current_user.id, ids)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


@manager.route("/files/<file_id>", methods=["GET"])  # noqa: F821
@login_required
def files_get(file_id):
    try:
        ok, result = get_file_content(current_user.id, file_id)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result.to_dict())
    except Exception as e:
        return server_error_response(e)


@manager.route("/files/move", methods=["POST"])  # noqa: F821
@login_required
async def files_move():
    try:
        req = await get_request_json()
        src_ids = req.get("src_file_ids", [])
        dest_id = req.get("dest_file_id")
        new_name = req.get("new_name")
        ok, result = await move_files(current_user.id, src_ids, dest_id, new_name)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)
