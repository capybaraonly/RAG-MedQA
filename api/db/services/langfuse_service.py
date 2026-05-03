from common import settings


class TenantLangfuseService:
    """Stub: TenantLangfuse table removed. Langfuse now configured via env vars."""

    @classmethod
    def filter_by_tenant(cls, tenant_id):
        return None

    @classmethod
    def filter_by_tenant_with_info(cls, tenant_id):
        return None

    @classmethod
    def delete_ty_tenant_id(cls, tenant_id):
        return 0

    @classmethod
    def update_by_tenant(cls, tenant_id, langfuse_keys):
        return 0

    @classmethod
    def save(cls, **kwargs):
        pass

    @classmethod
    def delete_model(cls, langfuse_model):
        pass
