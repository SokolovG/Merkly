from dishka import Provider, Scope, make_async_container, provide

from src.config.settings import TgSettings
from src.infrastructure.backend_client import BackendClient


class AppProvider(Provider):
    def __init__(self, settings: TgSettings) -> None:
        super().__init__()
        self._settings = settings

    @provide(scope=Scope.APP)
    def get_settings(self) -> TgSettings:
        return self._settings

    @provide(scope=Scope.APP)
    def get_backend_client(self, settings: TgSettings) -> BackendClient:
        return BackendClient(
            base_url=settings.BACKEND_URL,
            api_key=settings.BACKEND_API_KEY,
        )


def build_container(settings: TgSettings):
    return make_async_container(AppProvider(settings))
