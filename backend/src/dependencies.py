from collections.abc import AsyncGenerator

from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.src.application.agent.core import CardBackend, LessonAgent
from backend.src.application.article_refill_service import ArticleRefillService
from backend.src.application.listening_refill_service import ListeningRefillService
from backend.src.application.listening_service import ListeningAgent
from backend.src.application.vocab_refill_service import VocabRefillService
from backend.src.config import BackendSettings
from backend.src.domain.ports.listening_history_repo import IListeningHistoryRepository
from backend.src.domain.ports.listening_pool_repo import IListeningPoolRepository
from backend.src.domain.ports.session_history_repo import ISessionHistoryRepository
from backend.src.infrastructure.audio import AudioService
from backend.src.infrastructure.card_backends.anki import AnkiClient
from backend.src.infrastructure.card_backends.mochi import MochiClient
from backend.src.infrastructure.database.repositories import (
    ArticlePoolRepository,
    IdentityRepository,
    ListeningHistoryRepository,
    ListeningPoolRepository,
    ProfileRepository,
    SessionHistoryRepository,
    SessionRepository,
    VocabPoolRepository,
)
from backend.src.infrastructure.fetchers.podcast.router import PodcastFetcherRouter
from backend.src.infrastructure.fetchers.rss import NewsArticleFetcher
from backend.src.infrastructure.llm.client import LLMClient
from backend.src.infrastructure.whisper.client import WhisperClient


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def settings(self) -> BackendSettings:
        return BackendSettings()

    @provide(scope=Scope.APP)
    async def engine(self, settings: BackendSettings) -> AsyncGenerator[AsyncEngine, None]:
        engine = create_async_engine(settings.async_database_url, echo=False)
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
    def identity_repo(self, session: AsyncSession) -> IdentityRepository:
        return IdentityRepository(session)

    @provide(scope=Scope.REQUEST)
    def profile_repo(self, session: AsyncSession) -> ProfileRepository:
        return ProfileRepository(session)

    @provide(scope=Scope.REQUEST)
    def session_repo(self, session: AsyncSession) -> SessionRepository:
        return SessionRepository(session)

    @provide(scope=Scope.REQUEST)
    def vocab_pool_repo(self, session: AsyncSession) -> VocabPoolRepository:
        return VocabPoolRepository(session)

    @provide(scope=Scope.REQUEST, provides=ISessionHistoryRepository)
    def session_history_repo(self, session: AsyncSession) -> SessionHistoryRepository:
        return SessionHistoryRepository(session)

    @provide(scope=Scope.APP, provides=LLMClient)
    def llm(self, settings: BackendSettings) -> LLMClient:
        return LLMClient(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY.get_secret_value(),
            model=settings.LLM_MODEL,
        )

    @provide(scope=Scope.APP, provides=NewsArticleFetcher)
    def article_fetcher(self) -> NewsArticleFetcher:
        return NewsArticleFetcher()

    @provide(scope=Scope.APP)
    def card_gateway(self, settings: BackendSettings) -> AnkiClient | MochiClient:
        match CardBackend(settings.CARD_BACKEND):
            case CardBackend.ANKI:
                return AnkiClient(settings.ANKI_CONNECT_URL, deck=settings.ANKI_DECK)
            case CardBackend.MOCHI:
                return MochiClient(
                    api_key=settings.MOCHI_API_KEY.get_secret_value(),
                    deck_id=settings.MOCHI_DECK_ID,
                    base_url=settings.MOCHI_BASE_URL,
                )

    @provide(scope=Scope.APP)
    def agent(
        self,
        llm: LLMClient,
        fetcher: NewsArticleFetcher,
        card_gateway: AnkiClient | MochiClient,
    ) -> LessonAgent:
        return LessonAgent(llm=llm, fetcher=fetcher, card_gateway=card_gateway)

    # ── Podcast / Listening ───────────────────────────────────────────────────

    @provide(scope=Scope.APP)
    def podcast_fetcher(self, settings: BackendSettings) -> PodcastFetcherRouter:
        return PodcastFetcherRouter.build(
            podcast_index_api_key=settings.PODCAST_INDEX_API_KEY,
            podcast_index_api_secret=settings.PODCAST_INDEX_API_SECRET,
        )

    # ── Audio / Listening ─────────────────────────────────────────────────────

    @provide(scope=Scope.APP)
    async def audio_service(self) -> AsyncGenerator[AudioService, None]:
        service = AudioService()
        yield service
        await service.aclose()

    @provide(scope=Scope.APP)
    async def whisper_client(
        self, settings: BackendSettings
    ) -> AsyncGenerator[WhisperClient, None]:
        client = WhisperClient(base_url=settings.WHISPER_BASE_URL)
        yield client
        await client.aclose()

    @provide(scope=Scope.APP)
    def listening_service(
        self,
        podcast_fetcher: PodcastFetcherRouter,
        audio: AudioService,
        whisper: WhisperClient,
        llm: LLMClient,
    ) -> ListeningAgent:
        return ListeningAgent(podcast_fetcher, audio, whisper, llm)

    @provide(scope=Scope.REQUEST)
    def vocab_refill_service(
        self,
        agent: LessonAgent,
        repo: VocabPoolRepository,
    ) -> VocabRefillService:
        return VocabRefillService(agent=agent, repo=repo)

    @provide(scope=Scope.REQUEST)
    def article_pool_repo(self, session: AsyncSession) -> ArticlePoolRepository:
        return ArticlePoolRepository(session)

    @provide(scope=Scope.REQUEST)
    def article_refill_service(
        self,
        agent: LessonAgent,
        repo: ArticlePoolRepository,
    ) -> ArticleRefillService:
        return ArticleRefillService(agent=agent, repo=repo)

    @provide(scope=Scope.REQUEST, provides=IListeningPoolRepository)
    def listening_pool_repo(self, session: AsyncSession) -> ListeningPoolRepository:
        return ListeningPoolRepository(session)

    @provide(scope=Scope.REQUEST, provides=IListeningHistoryRepository)
    def listening_history_repo(self, session: AsyncSession) -> ListeningHistoryRepository:
        return ListeningHistoryRepository(session)

    @provide(scope=Scope.REQUEST)
    def listening_refill_service(
        self,
        service: ListeningAgent,
        repo: IListeningPoolRepository,
    ) -> ListeningRefillService:
        return ListeningRefillService(service=service, repo=repo)


def create_container():
    return make_async_container(AppProvider())
