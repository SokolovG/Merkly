"""Litestar application factory."""

from dishka.integrations.litestar import setup_dishka
from litestar import Litestar, Router
from litestar.connection import Request
from litestar.exceptions import NotAuthorizedException

from backend.src.config import BackendSettings
from backend.src.dependencies import create_container
from backend.src.presentation.controllers.identity_controller import IdentityController
from backend.src.presentation.controllers.profile_controller import ProfileController
from backend.src.presentation.controllers.scheduler_controller import SchedulerController
from backend.src.presentation.controllers.session_controller import SessionController
from backend.src.presentation.controllers.vocab_controller import VocabController
from backend.src.presentation.responses.dto import SuccessResponseDTO

# Load once at module level — avoids re-reading .env on every request.
_settings = BackendSettings()
_expected_token = f"Bearer {_settings.BACKEND_API_KEY.get_secret_value()}"


async def _auth_guard(request: Request) -> None:
    token = request.headers.get("Authorization", "")
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
    return_dto=SuccessResponseDTO,
)


def create_app() -> Litestar:
    app = Litestar(
        route_handlers=[api_router],
        before_request=_auth_guard,
    )
    container = create_container()
    setup_dishka(container, app)
    return app
