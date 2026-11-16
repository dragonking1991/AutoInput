from autoinput.domain import Profile
from autoinput.targets import dry_run as _dry_run  # noqa: F401 - register drivers
from autoinput.targets import mac as _mac  # noqa: F401
from autoinput.targets import uia as _uia  # noqa: F401
from autoinput.targets import web as _web  # noqa: F401
from autoinput.targets.base import Driver, driver_registry


def create_driver(profile: Profile, *, dry_run: bool = False) -> Driver:
    name = "dry_run" if dry_run else profile.driver
    return driver_registry.get(name)(profile)


__all__ = ["Driver", "create_driver", "driver_registry"]
