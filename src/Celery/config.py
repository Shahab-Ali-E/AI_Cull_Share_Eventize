import os
from functools import lru_cache
from kombu import Queue
from config.settings import get_settings

settings = get_settings()


def route_task(name, args, kwargs, options, task=None, **kw):
    if ":" in name:
        queue, _ = name.split(":")
        return {"queue": queue}
    return {"queue": "celery"}


#defining base config for celery
class BaseConfig:
    CELERY_BROKER_URL: str = settings.CELERY_BROKER_URL
    result_backend: str = settings.CELERY_RESULT_BACKEND_URL

    CELERY_TASK_QUEUES: list = (
        # default queue
        Queue("celery"),
        # custom queue
        Queue("culling"),
        Queue("smart_sharing"),
    )

    CELERY_TASK_ROUTES = (route_task,)




class DevelopmentConfig(BaseConfig):
    pass


@lru_cache()
def get_settings():
    config_cls_dict = {
        "development": DevelopmentConfig,
    }
    config_name = settings.CELERY_WORKING_ENV_CONFIG
    config_cls = config_cls_dict[config_name]
    return config_cls()

