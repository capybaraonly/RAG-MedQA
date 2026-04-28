
class ReloadConfigBase:
    @classmethod
    def get_all(cls):
        configs = {}
        for k, v in cls.__dict__.items():
            if not callable(getattr(cls, k)) and not k.startswith(
                    "__") and not k.startswith("_"):
                configs[k] = v
        return configs

    @classmethod
    def get(cls, config_name):
        return getattr(cls, config_name) if hasattr(cls, config_name) else None
