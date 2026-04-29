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
from api.apps.services.dataset_api_service import (
    create_dataset,
    delete_datasets,
    list_datasets,
    update_dataset,
)
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    get_request_json,
    server_error_response,
)
from common.constants import RetCode


def _parse_list_args():
    args = {}
    for key in request.args:
        if key.startswith("ext["):
            inner_key = key[4:-1]
            args.setdefault("ext", {})[inner_key] = request.args.get(key)
        elif key in ("page", "page_size", "orderby", "desc", "id", "name"):
            args[key] = request.args.get(key)
    return args


@manager.route("/datasets", methods=["GET"])  # noqa: F821
@login_required
def datasets_list():
    try:
        args = _parse_list_args()
        ok, result = list_datasets(current_user.id, args)
        if not ok:
            return get_data_error_result(message=result)
        return jsonify({
            "code": 0,
            "message": "success",
            "data": result["data"],
            "total_datasets": result["total"],
        })
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets", methods=["POST"])  # noqa: F821
@login_required
async def datasets_create():
    try:
        req = await get_request_json()
        ok, result = await create_dataset(current_user.id, req)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets/<dataset_id>", methods=["PUT"])  # noqa: F821
@login_required
async def datasets_update(dataset_id):
    try:
        req = await get_request_json()
        ok, result = await update_dataset(current_user.id, dataset_id, req)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets", methods=["DELETE"])  # noqa: F821
@login_required
async def datasets_delete():
    try:
        req = await get_request_json()
        ids = req.get("ids", []) if req else []
        ok, result = await delete_datasets(current_user.id, ids)
        if not ok:
            return get_data_error_result(message=result)
        return get_json_result(data=result)
    except Exception as e:
        return server_error_response(e)
