"""Identity controller — platform identity resolution."""

from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from backend.src.domain.enums import Platform
from backend.src.infrastructure.database.repositories.identity_repo import IdentityRepository
from backend.src.presentation.dto.identity.responses import IdentityLookupResponse
from backend.src.presentation.responses.base import SuccessResponse


class IdentityController(Controller):
    path = "/identity"

    @get("/lookup")
    @inject
    async def lookup_identity(
        self,
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
        *,
        repo: FromDishka[IdentityRepository],
    ) -> SuccessResponse:
        """Look up identity by (platform, platform_user_id).
        Returns user_id for profile resolution. Returns 404 if not found."""
        try:
            platform_enum = Platform(platform)
        except ValueError:
            raise NotFoundException(detail=f"Unknown platform: {platform!r}") from None

        identity = await repo.get_by_platform(platform_enum, contact_id)
        if identity is None:
            raise NotFoundException(detail=f"No identity for {platform}:{contact_id}") from None

        return SuccessResponse(
            data=IdentityLookupResponse(
                user_id=str(identity.user_id),
                platform=platform,
                platform_user_id=contact_id,
            ),
            message="Identity resolved",
        )
