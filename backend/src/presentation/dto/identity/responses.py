import msgspec


class IdentityLookupResponse(msgspec.Struct):
    """Response for GET /identity/lookup."""

    user_id: str  # UUID as str
    platform: str
    platform_user_id: str
