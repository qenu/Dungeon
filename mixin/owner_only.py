from discord import Colour, Embed
from discord.ext import commands
from loguru import logger as log

from ..utils import get_embed


class DungeonOwnerCommandsMixin:
    # owner commands
    @commands.group(name="dungeon", hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def _dungeon(self, ctx: commands.Context) -> None:
        await ctx.send("缺少參數, `list`, `lock` 或是 `unlock`。")
        pass

    @_dungeon.command(name="lock", aliases=["unlock"])
    async def _instance_lockdown(self, ctx: commands.Context) -> None:
        """阻止/允許建立新的副本入口。"""
        self._lockdown = ctx.invoked_with == "lock"
        try:
            await ctx.message.delete()
        except Exception:
            pass
        e: Embed = get_embed(
            colour=Colour.red() if self._lockdown else Colour.green(),
            title=f"【系統通知】副本入口已{'關閉' if self._lockdown else '開啟'}。",
        )
        e.remove_author()

        await ctx.send(embed=e)
        log.critical(f"Dungeon lockdown is now {self._lockdown}.")

    @_dungeon.command(name="list")
    async def _list_instance(self, ctx: commands.Context) -> None:
        """顯示目前開啟的副本入口。"""
        if self.occupied_guild:
            content = "\n".join(
                f"{self.bot.get_guild(k)}: <t:{v[1]}:R>"
                for k, v in self.occupied_guild.items()[:10]
            )
            if len(self.occupied_guild) > 10:
                content += "\n..."
            await ctx.send(f"副本列表:\n{content}")
        else:
            await ctx.send("沒有開啟的副本。")
