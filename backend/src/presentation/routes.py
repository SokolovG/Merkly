"""Litestar application factory.

Usage (19-04 will wire the full DI container here):
    from backend.src.presentation.routes import create_app
    app = create_app()
"""

from litestar import Litestar, Router

from backend.src.presentation.controllers.identity_controller import IdentityController
from backend.src.presentation.controllers.profile_controller import ProfileController
from backend.src.presentation.controllers.scheduler_controller import SchedulerController
from backend.src.presentation.controllers.session_controller import SessionController
from backend.src.presentation.controllers.vocab_controller import VocabController

api_router = Router(
    path="/api",
    route_handlers=[
        SessionController,
        IdentityController,
        VocabController,
        ProfileController,
        SchedulerController,
    ],
)


def create_app() -> Litestar:
    return Litestar(
        route_handlers=[api_router],
        # Auth middleware wired in 19-06:
        # middleware=[AuthMiddleware],
        # DI container wired in 19-06:
        # dependencies={...},
    )
