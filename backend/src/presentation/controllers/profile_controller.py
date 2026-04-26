"""Profile controller — user profile read and update."""

import uuid

import msgspec
from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get, patch
from litestar.exceptions import NotFoundException

from backend.src.domain.entities import UserProfile
from backend.src.domain.utils import compute_next_reminder_at
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.presentation.converters import profile_to_response
from backend.src.presentation.dto.profile.requests import UpdateProfileRequest
from backend.src.presentation.responses.base import SuccessResponse


def _apply_update(profile: UserProfile, data: UpdateProfileRequest) -> UserProfile:
    overrides = {
        f.name: getattr(data, f.name)
        for f in msgspec.structs.fields(data)
        if getattr(data, f.name) is not None
    }
    updated = msgspec.structs.replace(profile, **overrides)
    # Recompute next_reminder_at when reminder settings change
    reminder_fields = {"reminder_enabled", "reminder_time", "utc_offset"}
    if reminder_fields & overrides.keys():
        if updated.reminder_enabled:
            updated = msgspec.structs.replace(
                updated,
                next_reminder_at=compute_next_reminder_at(
                    updated.reminder_time, updated.utc_offset
                ),
            )
        else:
            updated = msgspec.structs.replace(updated, next_reminder_at=None)
    return updated


class ProfileController(Controller):
    path = "/profiles"

    @get("/{user_id:str}")
    @inject
    async def get_profile(
        self,
        user_id: str,
        repo: FromDishka[ProfileRepository],
    ) -> SuccessResponse:
        """Fetch UserProfile by UUID. Returns 404 if not found."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {user_id!r}") from None

        profile = await repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {user_id}") from None

        return SuccessResponse(data=profile_to_response(profile), message="Profile fetched")

    @patch("/{user_id:str}")
    @inject
    async def update_profile(
        self,
        user_id: str,
        data: UpdateProfileRequest,
        repo: FromDishka[ProfileRepository],
    ) -> SuccessResponse:
        """Apply partial update to UserProfile fields, then save and return updated profile."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {user_id!r}") from None

        profile = await repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {user_id}") from None

        updated = _apply_update(profile, data)
        await repo.save(updated)
        return SuccessResponse(data=profile_to_response(updated), message="Profile updated")
