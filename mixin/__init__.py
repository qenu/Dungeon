# mixin package for dungeon cog
# flake8: noqa


from ._dungeon import DungeonMixin
from .app_command import DungeonAppCommandsMixin
from .dm_only import DungeonPrivateCommands
from .loader import DungeonLoaderMixin
from .owner_only import DungeonOwnerCommandsMixin


class _DungeonMixin(
    DungeonMixin,
    DungeonAppCommandsMixin,
    DungeonPrivateCommands,
    DungeonLoaderMixin,
    DungeonOwnerCommandsMixin,
):
    pass
