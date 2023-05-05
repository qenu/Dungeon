from .dungeon import Dungeon


async def setup(bot):
    await bot.add_cog(Dungeon(bot))
