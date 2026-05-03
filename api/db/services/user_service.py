
import hashlib
from datetime import datetime
import logging

import peewee
from werkzeug.security import generate_password_hash, check_password_hash

from api.db import UserTenantRole
from api.db.db_models import DB
from api.db.db_models import User
from api.db.services.common_service import CommonService
from common.misc_utils import get_uuid
from common.time_utils import current_timestamp, datetime_format
from common.constants import StatusEnum
from common import settings


class UserService(CommonService):
    """Service class for managing user-related database operations.

    This class extends CommonService to provide specialized functionality for user management,
    including authentication, user creation, updates, and deletions.

    Attributes:
        model: The User model class for database operations.
    """
    model = User

    @classmethod
    @DB.connection_context()
    def query(cls, cols=None, reverse=None, order_by=None, **kwargs):
        if 'access_token' in kwargs:
            access_token = kwargs['access_token']

            # Reject empty, None, or whitespace-only access tokens
            if not access_token or not str(access_token).strip():
                logging.warning("UserService.query: Rejecting empty access_token query")
                return cls.model.select().where(cls.model.id == "INVALID_EMPTY_TOKEN")  # Returns empty result

            # Reject tokens that are too short (should be UUID, 32+ chars)
            if len(str(access_token).strip()) < 32:
                logging.warning(f"UserService.query: Rejecting short access_token query: {len(str(access_token))} chars")
                return cls.model.select().where(cls.model.id == "INVALID_SHORT_TOKEN")  # Returns empty result

            # Reject tokens that start with "INVALID_" (from logout)
            if str(access_token).startswith("INVALID_"):
                logging.warning("UserService.query: Rejecting invalidated access_token")
                return cls.model.select().where(cls.model.id == "INVALID_LOGOUT_TOKEN")  # Returns empty result

        # Call parent query method for valid requests
        return super().query(cols=cols, reverse=reverse, order_by=order_by, **kwargs)

    @classmethod
    @DB.connection_context()
    def filter_by_id(cls, user_id):
        """Retrieve a user by their ID.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            User object if found, None otherwise.
        """
        try:
            user = cls.model.select().where(cls.model.id == user_id).get()
            return user
        except peewee.DoesNotExist:
            return None

    @classmethod
    @DB.connection_context()
    def query_user(cls, email, password):
        """Authenticate a user with email and password.

        Args:
            email: User's email address.
            password: User's password in plain text.

        Returns:
            User object if authentication successful, None otherwise.
        """
        user = cls.model.select().where((cls.model.email == email),
                                        (cls.model.status == StatusEnum.VALID.value)).first()
        if user and check_password_hash(str(user.password), password):
            return user
        else:
            return None

    @classmethod
    @DB.connection_context()
    def query_user_by_email(cls, email):
        users = cls.model.select().where((cls.model.email == email))
        return list(users)

    @classmethod
    @DB.connection_context()
    def save(cls, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = get_uuid()
        if "password" in kwargs:
            kwargs["password"] = generate_password_hash(
                str(kwargs["password"]))

        current_ts = current_timestamp()
        current_date = datetime_format(datetime.now())

        kwargs["create_time"] = current_ts
        kwargs["create_date"] = current_date
        kwargs["update_time"] = current_ts
        kwargs["update_date"] = current_date
        obj = cls.model(**kwargs).save(force_insert=True)
        return obj

    @classmethod
    @DB.connection_context()
    def delete_user(cls, user_ids, update_user_dict):
        with DB.atomic():
            cls.model.update({"status": 0}).where(
                cls.model.id.in_(user_ids)).execute()

    @classmethod
    @DB.connection_context()
    def update_user(cls, user_id, user_dict):
        with DB.atomic():
            if user_dict:
                user_dict["update_time"] = current_timestamp()
                user_dict["update_date"] = datetime_format(datetime.now())
                cls.model.update(user_dict).where(
                    cls.model.id == user_id).execute()

    @classmethod
    @DB.connection_context()
    def update_user_password(cls, user_id, new_password):
        with DB.atomic():
            update_dict = {
                "password": generate_password_hash(str(new_password)),
                "update_time": current_timestamp(),
                "update_date": datetime_format(datetime.now())
            }
            cls.model.update(update_dict).where(cls.model.id == user_id).execute()

    @classmethod
    @DB.connection_context()
    def is_admin(cls, user_id):
        return cls.model.select().where(
            cls.model.id == user_id,
            cls.model.is_superuser == 1).count() > 0

    @classmethod
    @DB.connection_context()
    def get_all_users(cls):
        users = cls.model.select().order_by(cls.model.email)
        return list(users)


class TenantService:
    """Stub: Tenant table removed in tenant-less architecture."""

    @classmethod
    def get_info_by(cls, user_id):
        from common.constants import SYSTEM_TENANT_ID
        return [{"tenant_id": SYSTEM_TENANT_ID, "name": "Default", "role": "owner"}]

    @classmethod
    def get_joined_tenants_by_user_id(cls, user_id):
        from common.constants import SYSTEM_TENANT_ID
        return [{"tenant_id": SYSTEM_TENANT_ID}]

    @classmethod
    def decrease(cls, user_id, num):
        pass

    @classmethod
    def user_gateway(cls, tenant_id):
        import hashlib
        hash_obj = hashlib.sha256(tenant_id.encode("utf-8"))
        return int(hash_obj.hexdigest(), 16) % len(settings.MINIO) if settings.MINIO else 0

    @classmethod
    def get_null_tenant_model_id_rows(cls):
        return []

    @classmethod
    def get_by_id(cls, id):
        from common.constants import SYSTEM_TENANT_ID
        return True, type("TenantStub", (), {"id": SYSTEM_TENANT_ID, "embd_id": "", "asr_id": "", "img2txt_id": "", "llm_id": "", "rerank_id": "", "tts_id": ""})()

    @classmethod
    def insert(cls, **kwargs):
        pass

    @classmethod
    def delete_by_id(cls, id):
        pass

    @classmethod
    def update_by_id(cls, id, updates):
        pass

    @classmethod
    def filter_update(cls, conditions, updates):
        return 0


class UserTenantService:
    """Stub: UserTenant table removed in tenant-less architecture."""

    @classmethod
    def query(cls, **kwargs):
        return []

    @classmethod
    def get_tenants_by_user_id(cls, user_id):
        from common.constants import SYSTEM_TENANT_ID
        return [{"tenant_id": SYSTEM_TENANT_ID}]

    @classmethod
    def get_user_tenant_relation_by_user_id(cls, user_id):
        return []

    @classmethod
    def insert(cls, **kwargs):
        pass

    @classmethod
    def delete_by_id(cls, id):
        pass

    @classmethod
    def delete_by_ids(cls, ids):
        pass

    @classmethod
    def save(cls, **kwargs):
        pass

    @classmethod
    def filter_delete(cls, conditions):
        return 0

    @classmethod
    def filter_update(cls, conditions, updates):
        return 0
