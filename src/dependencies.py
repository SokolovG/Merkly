from collections.abc import AsyncGenerator

from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application.agent.core import CardBackend, LessonAgent
from src.config import Settings
from src.infrastructure.card_backends.anki import AnkiClient
from src.infrastructure.card_backends.mochi import MochiClient
from src.infrastructure.database.repositories import ProfileRepository, SessionRepository
from src.infrastructure.fetchers.german.dw import DWArticleFetcher
from src.infrastructure.llm.client import LLMClient


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def settings(self) -> Settings:
        return Settings()  # ty : ignore

    @provide(scope=Scope.APP)
    async def engine(self, settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
        engine = create_async_engine(settings.database_url, echo=False)
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def session_maker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def get_db_session(
        self, session_maker: async_sessionmaker[AsyncSession]
    ) -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    @provide(scope=Scope.REQUEST)
    def profile_repo(self, session: AsyncSession) -> ProfileRepository:
        return ProfileRepository(session)

    @provide(scope=Scope.REQUEST)
    def session_repo(self, session: AsyncSession) -> SessionRepository:
        return SessionRepository(session)

    @provide(scope=Scope.APP, provides=LLMClient)
    def llm(self, settings: Settings) -> LLMClient:
        return LLMClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
        )

    @provide(scope=Scope.APP, provides=DWArticleFetcher)
    def article_fetcher(self) -> DWArticleFetcher:
        return DWArticleFetcher()

    @provide(scope=Scope.APP)
    def card_gateway(self, settings: Settings) -> AnkiClient | MochiClient:
        match CardBackend(settings.card_backend):
            case CardBackend.ANKI:
                return AnkiClient(settings.anki_connect_url, deck=settings.anki_deck)
            case CardBackend.MOCHI:
                return MochiClient(
                    api_key=settings.mochi_api_key.get_secret_value(),
                    deck_id=settings.mochi_deck_id,
                )

    @provide(scope=Scope.APP)
    def agent(
        self,
        llm: LLMClient,
        fetcher: DWArticleFetcher,
        card_gateway: AnkiClient | MochiClient,
    ) -> LessonAgent:
        return LessonAgent(llm=llm, fetcher=fetcher, anki=card_gateway)


def create_container():
    return make_async_container(AppProvider())
