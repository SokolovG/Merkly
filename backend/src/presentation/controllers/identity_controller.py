"""Identity controller — platform identity resolution."""

from litestar import Controller, get
from litestar.params import Parameter

from backend.src.presentation.responses.base import SuccessResponse


class IdentityController(Controller):
    path = "/identity"

    @get("/lookup")
    async def lookup_identity(
        self,
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
    ) -> SuccessResponse:
        """Look up identity by (platform, platform_user_id) →
        return user_id for profile resolution.
        Returns 404 if not found."""
        raise NotImplementedError
