from dataclasses import dataclass

from backend.src.domain.entities import Identity, UserProfile
from backend.src.domain.enums import Platform
from backend.src.infrastructure.database.repositories.identity_repo import IdentityRepository
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.infrastructure.exceptions import NotFoundError


@dataclass(frozen=True)
class UserContext:
    identity: Identity
    profile: UserProfile


class UserResolverUseCase:
    def __init__(
        self,
        identity_repo: IdentityRepository,
        profile_repo: ProfileRepository,
    ) -> None:
        self._identity_repo = identity_repo
        self._profile_repo = profile_repo

    async def resolve(self, platform: Platform, contact_id: str) -> UserContext:
        identity = await self._identity_repo.get_by_platform(platform, contact_id)
        if identity is None:
            raise NotFoundError("Identity", f"{platform}:{contact_id}")

        profile = await self._profile_repo.get_by_id(identity.user_id)
        if profile is None:
            raise NotFoundError("Profile", str(identity.user_id))

        return UserContext(identity=identity, profile=profile)
