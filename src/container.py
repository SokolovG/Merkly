from pathlib import Path

from dishka import Provider, Scope, make_async_container, provide

from src.application.agent.core import CardBackend, LessonAgent
from src.config import Settings
from src.infrastructure.integrations.anki_client import AnkiClient
from src.infrastructure.integrations.dw_fetcher import DWArticleFetcher
from src.infrastructure.integrations.llm_client import LLMClient
from src.infrastructure.integrations.mochi_client import MochiClient
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository
from src.infrastructure.repositories.json_session_repo import JsonSessionRepository


class AppProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return Settings()  # ty : ignore

    @provide
    def data_dir(self, settings: Settings) -> Path:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        return settings.data_dir

    # Concrete types as return values — dishka resolves by these keys.
    # Handlers use FromDishka[JsonProfileRepository] etc., or we inject
    # concrete types directly. Protocol-based injection requires provide()
    # with explicit provides= parameter.

    @provide(provides=JsonProfileRepository)
    def profile_repo(self, data_dir: Path) -> JsonProfileRepository:
        return JsonProfileRepository(data_dir)

    @provide(provides=JsonSessionRepository)
    def session_repo(self, data_dir: Path) -> JsonSessionRepository:
        return JsonSessionRepository(data_dir)

    @provide(provides=LLMClient)
    def llm(self, settings: Settings) -> LLMClient:
        return LLMClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
        )

    @provide(provides=DWArticleFetcher)
    def article_fetcher(self) -> DWArticleFetcher:
        return DWArticleFetcher()

    @provide
    def card_gateway(self, settings: Settings) -> AnkiClient | MochiClient:
        match CardBackend(settings.card_backend):
            case CardBackend.ANKI:
                return AnkiClient(settings.anki_connect_url, deck=settings.anki_deck)
            case CardBackend.MOCHI:
                return MochiClient(
                    api_key=settings.mochi_api_key.get_secret_value(),
                    deck_id=settings.mochi_deck_id,
                )

    @provide
    def agent(
        self,
        llm: LLMClient,
        fetcher: DWArticleFetcher,
        card_gateway: AnkiClient | MochiClient,
    ) -> LessonAgent:
        return LessonAgent(llm=llm, fetcher=fetcher, anki=card_gateway)


def create_container():
    return make_async_container(AppProvider())
