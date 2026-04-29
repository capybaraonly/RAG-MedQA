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
import logging

from api.db import UserTenantRole
from api.db.db_models import UserTenant
from api.db.services.user_service import UserTenantService, UserService
from common.constants import RetCode, StatusEnum
from common.misc_utils import get_uuid
import datetime

from common.time_utils import delta_seconds
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    get_request_json,
    server_error_response,
)
from api.apps import login_required, current_user
from api.utils.web_utils import send_invite_email
from common import settings


@manager.route("/list", methods=["GET"])  # noqa: F821
@login_required
def tenant_list():
    """
    List all tenants for the current user.
    ---
    tags:
      - Tenant
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Tenant list retrieved successfully.
        schema:
          type: object
    """
    try:
        tenants = UserTenantService.get_tenants_by_user_id(current_user.id)
        for tenant in tenants:
            ud = tenant.get("update_date", "")
            if isinstance(ud, datetime.datetime):
                ud = ud.strftime("%Y-%m-%d %H:%M:%S")
            tenant["delta_seconds"] = delta_seconds(ud)
        return get_json_result(data=tenants)
    except Exception as e:
        return server_error_response(e)


@manager.route("/<tenant_id>/user/list", methods=["GET"])  # noqa: F821
@login_required
def user_list(tenant_id):
    """
    List all users in a tenant.
    ---
    tags:
      - Tenant
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: tenant_id
        type: string
        required: true
        description: Tenant ID.
    responses:
      200:
        description: User list retrieved successfully.
        schema:
          type: object
    """
    if current_user.id != tenant_id:
        return get_json_result(
            data=False,
            code=RetCode.AUTHENTICATION_ERROR,
            message="No authorization.",
        )
    try:
        users = UserTenantService.get_by_tenant_id(tenant_id)
        for u in users:
            ud = u.get("update_date", "")
            if isinstance(ud, datetime.datetime):
                ud = ud.strftime("%Y-%m-%d %H:%M:%S")
            u["delta_seconds"] = delta_seconds(ud)
        return get_json_result(data=users)
    except Exception as e:
        return server_error_response(e)


@manager.route("/<tenant_id>/user", methods=["POST"])  # noqa: F821
@login_required
async def create(tenant_id):
    """
    Invite a user to a tenant.
    ---
    tags:
      - Tenant
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: tenant_id
        type: string
        required: true
        description: Tenant ID.
      - in: body
        name: body
        description: Invitation details.
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              description: Email of the user to invite.
    responses:
      200:
        description: Invitation sent successfully.
        schema:
          type: object
    """
    if current_user.id != tenant_id:
        return get_json_result(
            data=False,
            code=RetCode.AUTHENTICATION_ERROR,
            message="No authorization.",
        )

    req = await get_request_json()
    email = req.get("email", "")

    invitees = UserService.query(email=email)
    if not invitees:
        return get_data_error_result(message="User not found.")

    invitee = invitees[0]
    user_tenants = UserTenantService.query(
        tenant_id=tenant_id, user_id=invitee.id
    )
    if user_tenants:
        role = user_tenants[0].role
        if role == UserTenantRole.NORMAL:
            return get_data_error_result(
                message=f"{email} already in the team."
            )
        if role == UserTenantRole.OWNER:
            return get_data_error_result(
                message=f"{email} is the owner of the team."
            )
        return get_data_error_result(
            message=f"User's role: {role} is invalid."
        )

    UserTenantService.save(
        id=get_uuid(),
        tenant_id=tenant_id,
        user_id=invitee.id,
        role=UserTenantRole.INVITE,
        invited_by=current_user.id,
    )

    ok, inviter = UserService.get_by_id(current_user.id)
    inviter_name = inviter.nickname if ok else ""

    invite_url = f"{settings.MAIL_FRONTEND_URL}/{tenant_id}"

    try:
        asyncio.create_task(
            send_invite_email(
                to_email=email,
                invite_url=invite_url,
                tenant_id=tenant_id,
                inviter=inviter_name,
            )
        )
    except Exception as e:
        logging.exception(e)
        return get_json_result(
            data=False,
            code=RetCode.SERVER_ERROR,
            message=f"Failed to send invite email. Error: {str(e)}",
        )

    data = invitee.to_dict()
    data.pop("password", None)
    return get_json_result(data=data)


@manager.route("/<tenant_id>/user/<user_id>", methods=["DELETE"])  # noqa: F821
@login_required
def rm(tenant_id, user_id):
    """
    Remove a user from a tenant.
    ---
    tags:
      - Tenant
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: tenant_id
        type: string
        required: true
        description: Tenant ID.
      - in: path
        name: user_id
        type: string
        required: true
        description: User ID to remove.
    responses:
      200:
        description: User removed successfully.
        schema:
          type: object
    """
    if current_user.id != tenant_id:
        return get_json_result(
            data=False,
            code=RetCode.AUTHENTICATION_ERROR,
            message="No authorization.",
        )
    try:
        UserTenantService.filter_delete(
            [
                UserTenant.tenant_id == tenant_id,
                UserTenant.user_id == user_id,
            ]
        )
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)


@manager.route("/agree/<tenant_id>", methods=["PUT"])  # noqa: F821
@login_required
def agree(tenant_id):
    """
    Agree to join a tenant.
    ---
    tags:
      - Tenant
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: tenant_id
        type: string
        required: true
        description: Tenant ID.
    responses:
      200:
        description: Tenant membership updated successfully.
        schema:
          type: object
    """
    try:
        UserTenantService.filter_update(
            [
                UserTenant.tenant_id == tenant_id,
                UserTenant.user_id == current_user.id,
            ],
            {"role": UserTenantRole.NORMAL},
        )
        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)
