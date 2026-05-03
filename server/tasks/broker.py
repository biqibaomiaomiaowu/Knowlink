import dramatiq
from dramatiq.brokers.redis import RedisBroker
from server.config.settings import get_settings

settings = get_settings()

redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)


def list_registered_tasks() -> list[str]:
    return sorted(dramatiq.get_broker().actors.keys())