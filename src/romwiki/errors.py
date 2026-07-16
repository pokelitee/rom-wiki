class RomWikiError(Exception):
    """Base error for expected ROM Wiki failures."""


class InvalidRomError(RomWikiError):
    """Raised when an input is not a structurally valid supported ROM."""


class ProfileError(RomWikiError):
    """Raised when a game profile is invalid."""


class SiteError(RomWikiError):
    """Raised when a site configuration or build is invalid."""
