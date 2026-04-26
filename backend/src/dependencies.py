from collections.abc import AsyncGenerator, AsyncIterator

from dishka import Provider, Scope, make_async_container, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.src.application.agent.core import LessonAgent
from backend.src.application.article_refill_service import ArticleRefillService
from backend.src.application.background_refiller import BackgroundRefiller
from backend.src.application.listening_refill_service import ListeningRefillService
from backend.src.application.listening_service import ListeningAgent
from backend.src.application.ports.storage import Storage
from backend.src.application.use_cases.resolve_user import UserResolverUseCase
from backend.src.application.use_cases.start_session import StartSessionUseCase
from backend.src.application.use_cases.vocab_use_case import (
    CaptureWordUseCase,
    GenerateVocabUseCase,
)
from backend.src.application.use_cases.writing_use_case import WritingUseCase
from backend.src.application.vocab_refill_service import VocabRefillService
from backend.src.config import BackendSettings
from backend.src.domain.enums import CardBackend
from backend.src.domain.ports.listening_history_repo import IListeningHistoryRepository
from backend.src.domain.ports.listening_pool_repo import IListeningPoolRepository
from backend.src.domain.ports.session_history_repo import ISessionHistoryRepository
from backend.src.domain.ports.writing_theme_repo import IWritingThemeRepository
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
    WritingThemeRepository,
)
from backend.src.infrastructure.fetchers.podcast.router import PodcastFetcherRouter
from backend.src.infrastructure.fetchers.rss import NewsArticleFetcher
from backend.src.infrastructure.llm.client import LLMClient
from backend.src.infrastructure.memory_storage import InMemoryStorage
from backend.src.infrastructure.redis_storage import RedisStorage
from backend.src.infrastructure.session_store import RedisSessionStore
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

    @provide(scope=Scope.REQUEST)
    def session_history_repo(self, session: AsyncSession) -> ISessionHistoryRepository:
        return SessionHistoryRepository(session)

    @provide(scope=Scope.APP)
    def llm(self, settings: BackendSettings) -> LLMClient:
        return LLMClient(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY.get_secret_value(),
            model=settings.LLM_MODEL,
        )

    @provide(scope=Scope.APP)
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

    @provide(scope=Scope.APP)
    def background_refiller(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        agent: LessonAgent,
        listening_agent: ListeningAgent,
    ) -> BackgroundRefiller:
        return BackgroundRefiller(
            session_maker=session_maker,
            agent=agent,
            listening_agent=listening_agent,
        )

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

    @provide(scope=Scope.REQUEST)
    def listening_pool_repo(self, session: AsyncSession) -> IListeningPoolRepository:
        return ListeningPoolRepository(session)

    @provide(scope=Scope.REQUEST)
    def listening_history_repo(self, session: AsyncSession) -> IListeningHistoryRepository:
        return ListeningHistoryRepository(session)

    @provide(scope=Scope.REQUEST)
    def listening_refill_service(
        self,
        service: ListeningAgent,
        repo: IListeningPoolRepository,
    ) -> ListeningRefillService:
        return ListeningRefillService(service=service, repo=repo)

    @provide(scope=Scope.APP)
    async def get_redis_client(self, settings: BackendSettings) -> AsyncIterator[Redis]:
        client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
            max_connections=50,
            retry_on_timeout=True,
        )
        try:
            yield client
        finally:
            await client.aclose()

    @provide(scope=Scope.APP, provides=Storage)
    def get_storage(self, redis_client: Redis, settings: BackendSettings) -> Storage:
        if settings.STORAGE_PROVIDER == "memory":
            return InMemoryStorage()
        return RedisStorage(redis_client)

    @provide(scope=Scope.REQUEST)
    def session_store(self, storage: Storage) -> RedisSessionStore:
        return RedisSessionStore(storage)

    # ── Use Cases ────────────────────────────────────────────────────────────

    @provide(scope=Scope.REQUEST)
    def user_resolver(
        self,
        identity_repo: IdentityRepository,
        profile_repo: ProfileRepository,
    ) -> UserResolverUseCase:
        return UserResolverUseCase(identity_repo, profile_repo)

    @provide(scope=Scope.REQUEST)
    def start_session_uc(
        self,
        article_pool: ArticlePoolRepository,
        session_history: ISessionHistoryRepository,
        agent: LessonAgent,
        store: RedisSessionStore,
        listening_pool: IListeningPoolRepository,
        listening_agent: ListeningAgent,
        refiller: BackgroundRefiller,
    ) -> StartSessionUseCase:
        return StartSessionUseCase(
            article_pool=article_pool,
            session_history=session_history,
            agent=agent,
            store=store,
            listening_pool=listening_pool,
            listening_agent=listening_agent,
            refiller=refiller,
        )

    @provide(scope=Scope.REQUEST)
    def generate_vocab_uc(
        self,
        agent: LessonAgent,
        repo: VocabPoolRepository,
        refiller: BackgroundRefiller,
    ) -> GenerateVocabUseCase:
        return GenerateVocabUseCase(agent=agent, repo=repo, refiller=refiller)

    @provide(scope=Scope.REQUEST)
    def capture_word_uc(
        self,
        agent: LessonAgent,
        repo: VocabPoolRepository,
        card_gateway: AnkiClient | MochiClient,
    ) -> CaptureWordUseCase:
        return CaptureWordUseCase(agent=agent, repo=repo, card_gateway=card_gateway)

    @provide(scope=Scope.REQUEST)
    def writing_theme_repo(self, session: AsyncSession) -> IWritingThemeRepository:
        return WritingThemeRepository(session)

    @provide(scope=Scope.REQUEST)
    def writing_uc(
        self,
        agent: LessonAgent,
        store: RedisSessionStore,
        theme_repo: IWritingThemeRepository,
        refiller: BackgroundRefiller,
    ) -> WritingUseCase:
        return WritingUseCase(agent=agent, store=store, theme_repo=theme_repo, refiller=refiller)


def create_container():
    return make_async_container(AppProvider())
