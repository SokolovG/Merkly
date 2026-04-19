"""Profile controller — user profile read and update."""

from litestar import Controller, get, patch

from backend.src.presentation.dto.profile.requests import UpdateProfileRequest
from backend.src.presentation.responses.base import SuccessResponse


class ProfileController(Controller):
    path = "/profiles"

    @get("/{user_id:str}")
    async def get_profile(self, user_id: str) -> SuccessResponse:
        """Fetch UserProfile by UUID → return as ProfileResponse.
        Returns 404 if not found."""
        raise NotImplementedError

    @patch("/{user_id:str}")
    async def update_profile(self, user_id: str, data: UpdateProfileRequest) -> SuccessResponse:
        """Apply partial update to UserProfile fields →
        recompute next_reminder_at if reminder fields changed →
        save → return updated ProfileResponse."""
        raise NotImplementedError
