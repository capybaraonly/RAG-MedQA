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

from quart import request

from api.apps import current_user, login_required
from api.db.services.search_service import SearchService
from api.db.services.user_service import TenantService, UserTenantService
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    get_request_json,
    server_error_response,
)
from common.constants import StatusEnum
from common.misc_utils import get_uuid


def _get_tenant_ids(user_id):
    tenants = TenantService.get_joined_tenants_by_user_id(user_id)
    return [m["tenant_id"] for m in tenants]


@manager.route("/searches", methods=["GET"])  # noqa: F821
@login_required
def searches_list():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 30))
        orderby = request.args.get("orderby", "update_time")
        desc = request.args.get("desc", "true").lower() != "false"
        keywords = request.args.get("keywords", "")

        joined_tenant_ids = _get_tenant_ids(current_user.id)
        searches, total = SearchService.get_by_tenant_ids(
            joined_tenant_ids=joined_tenant_ids,
            user_id=current_user.id,
            page_number=page,
            items_per_page=page_size,
            orderby=orderby,
            desc=desc,
            keywords=keywords,
        )
        return get_json_result(data={"searches": searches, "total": total})
    except Exception as e:
        return server_error_response(e)


@manager.route("/searches", methods=["POST"])  # noqa: F821
@login_required
async def searches_create():
    try:
        req = await get_request_json()
        search = {
            "id": get_uuid(),
            "tenant_id": current_user.id,
            "name": req.get("name", "New Search"),
            "description": req.get("description", ""),
            "avatar": req.get("avatar", ""),
            "created_by": current_user.id,
            "search_config": req.get("search_config", {}),
            "status": StatusEnum.VALID.value,
        }
        obj = SearchService.save(**search)
        return get_json_result(data=obj.to_dict())
    except Exception as e:
        return server_error_response(e)


@manager.route("/searches/<search_id>", methods=["GET"])  # noqa: F821
@login_required
def searches_get(search_id):
    try:
        detail = SearchService.get_detail(search_id)
        if not detail:
            return get_data_error_result(message="Search not found")
        return get_json_result(data=detail)
    except Exception as e:
        return server_error_response(e)


@manager.route("/searches/<search_id>", methods=["PUT"])  # noqa: F821
@login_required
async def searches_update(search_id):
    try:
        if not SearchService.accessible4deletion(search_id, current_user.id):
            return get_data_error_result(message="No authorization")
        req = await get_request_json()
        SearchService.update_by_id(search_id, req)
        detail = SearchService.get_detail(search_id)
        return get_json_result(data=detail)
    except Exception as e:
        return server_error_response(e)


@manager.route("/searches/<search_id>", methods=["DELETE"])  # noqa: F821
@login_required
def searches_delete(search_id):
    try:
        if not SearchService.accessible4deletion(search_id, current_user.id):
            return get_data_error_result(message="No authorization")
        SearchService.delete_by_id(search_id)
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)
