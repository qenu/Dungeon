"""Init file for dungeon cog."""
from .dungeon import Dungeon


async def setup(bot):
    """Illustrates Cog function to discord bot."""
    await bot.add_cog(Dungeon(bot))
