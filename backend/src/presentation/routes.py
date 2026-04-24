from dishka.integrations.litestar import setup_dishka
from litestar import Litestar, Router
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler
from litestar.openapi import OpenAPIConfig
from litestar.openapi.spec import Contact

from backend.src.config import BackendSettings
from backend.src.dependencies import create_container
from backend.src.infrastructure.middleware import ErrorHandlerMiddleware
from backend.src.presentation.controllers.identity_controller import IdentityController
from backend.src.presentation.controllers.profile_controller import ProfileController
from backend.src.presentation.controllers.scheduler_controller import SchedulerController
from backend.src.presentation.controllers.session_controller import SessionController
from backend.src.presentation.controllers.vocab_controller import VocabController
from backend.src.presentation.responses.dto import SuccessResponseDTO

# Loaded once at module level — avoids re-reading .env on every request.
_settings = BackendSettings()
_expected_token = f"Bearer {_settings.BACKEND_API_KEY.get_secret_value()}"


async def api_key_guard(connection: ASGIConnection, handler: BaseRouteHandler) -> None:
    """Litestar guard: reject requests without a valid Bearer API key."""
    token = connection.headers.get("Authorization", "")
    if token != _expected_token:
        raise NotAuthorizedException("Invalid API key")


api_router = Router(
    path="/api",
    route_handlers=[
        SessionController,
        IdentityController,
        VocabController,
        ProfileController,
        SchedulerController,
    ],
    guards=[api_key_guard],
    return_dto=SuccessResponseDTO,
)


_openapi_config = OpenAPIConfig(
    title="Merkly API",
    version="0.1.0",
    description="Language learning backend — sessions, vocab, identity, scheduler.",
    contact=Contact(name="Merkly", email="admin@merkly.app"),
)


def create_app() -> Litestar:
    app = Litestar(
        route_handlers=[api_router],
        middleware=[ErrorHandlerMiddleware],
        openapi_config=_openapi_config,
    )
    container = create_container()
    setup_dishka(container, app)
    return app
