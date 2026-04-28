
#

from datetime import datetime

import peewee

from api.db.db_models import DB, TenantLangfuse
from api.db.services.common_service import CommonService
from common.time_utils import current_timestamp, datetime_format


class TenantLangfuseService(CommonService):
    """
    All methods that modify the status should be enclosed within a DB.atomic() context to ensure atomicity
    and maintain data integrity in case of errors during execution.
    """

    model = TenantLangfuse

    @classmethod
    @DB.connection_context()
    def filter_by_tenant(cls, tenant_id):
        fields = [cls.model.tenant_id, cls.model.host, cls.model.secret_key, cls.model.public_key]
        try:
            keys = cls.model.select(*fields).where(cls.model.tenant_id == tenant_id).first()
            return keys
        except peewee.DoesNotExist:
            return None

    @classmethod
    @DB.connection_context()
    def filter_by_tenant_with_info(cls, tenant_id):
        fields = [cls.model.tenant_id, cls.model.host, cls.model.secret_key, cls.model.public_key]
        try:
            keys = cls.model.select(*fields).where(cls.model.tenant_id == tenant_id).dicts().first()
            return keys
        except peewee.DoesNotExist:
            return None

    @classmethod
    @DB.connection_context()
    def delete_ty_tenant_id(cls, tenant_id):
        return cls.model.delete().where(cls.model.tenant_id == tenant_id).execute()

    @classmethod
    def update_by_tenant(cls, tenant_id, langfuse_keys):
        langfuse_keys["update_time"] = current_timestamp()
        langfuse_keys["update_date"] = datetime_format(datetime.now())
        return cls.model.update(**langfuse_keys).where(cls.model.tenant_id == tenant_id).execute()

    @classmethod
    def save(cls, **kwargs):
        current_ts = current_timestamp()
        current_date = datetime_format(datetime.now())

        kwargs["create_time"] = current_ts
        kwargs["create_date"] = current_date
        kwargs["update_time"] = current_ts
        kwargs["update_date"] = current_date
        obj = cls.model.create(**kwargs)
        return obj

    @classmethod
    def delete_model(cls, langfuse_model):
        langfuse_model.delete_instance()
