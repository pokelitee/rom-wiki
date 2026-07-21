class RomWikiError(Exception):
    """Base error for expected ROM Wiki failures."""


class InvalidRomError(RomWikiError):
    """Raised when an input is not a structurally valid supported ROM."""


class ProfileError(RomWikiError):
    """Raised when a game profile is invalid."""


class SiteError(RomWikiError):
    """Raised when a site configuration or build is invalid."""


class DataSourceError(RomWikiError):
    """Raised when an external structured-data source is invalid."""


class LocalConfigError(RomWikiError):
    """Raised when local game inputs are missing or invalid."""
