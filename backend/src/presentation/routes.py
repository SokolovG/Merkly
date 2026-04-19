"""Litestar application factory.

Usage (19-04 will wire the full DI container here):
    from backend.src.presentation.routes import create_app
    app = create_app()
"""

from litestar import Litestar

from backend.src.presentation.controllers.identity_controller import IdentityController
from backend.src.presentation.controllers.profile_controller import ProfileController
from backend.src.presentation.controllers.scheduler_controller import SchedulerController
from backend.src.presentation.controllers.session_controller import SessionController
from backend.src.presentation.controllers.vocab_controller import VocabController


def create_app() -> Litestar:
    return Litestar(
        route_handlers=[
            SessionController,
            IdentityController,
            VocabController,
            ProfileController,
            SchedulerController,
        ],
        # Auth middleware wired in 19-04:
        # middleware=[AuthMiddleware],
        # DI container wired in 19-04:
        # dependencies={...},
    )
