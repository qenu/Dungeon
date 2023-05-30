from discord import Embed
from discord.ext import commands

from maki.cogs.utils.view import Confirm

from ..lib import Job
from ..utils.view import job_advancement


class DungeonPrivateCommands:
    """Commands executed in Discord Private Messages."""

    @commands.command(name="resetstats", aliases=["重置配點"])
    @commands.dm_only()
    async def resetstats(self, ctx: commands.Context) -> None:
        # if self.check_in_raid(ctx.author.id):
        #     await ctx.send("你正在副本中，無法重置配點")
        #     return
        player = await self.get_player(ctx.author)
        if player.dungeon is not None:
            return await ctx.reply("你正在副本中，請稍後再試！")
        if player.level < 10:
            return await ctx.send("超過10等才能使用此功能。")

        confirm = Confirm(ctx.author)
        await self
        ask = await ctx.send(
            "重置配點將會降低角色等級 10等，請確認是否同意。", view=confirm
        )
        await confirm.wait()
        if confirm.value:
            player.reset_ability_points()
            await self.set_player(ctx.author, player)
            await ctx.send("重置配點成功！")
        else:
            await ctx.send("取消重置配點。")

    @commands.command(name="jobadv", aliases=["轉職"])
    @commands.dm_only()
    async def jobadv(self, ctx: commands.Context) -> None:
        if self.check_in_raid(ctx.author.id):
            await ctx.send("你正在副本中，無法轉職")
            return
        player = await self.get_player(ctx.author)
        if player.level < 10:
            await ctx.send("你的經驗還不足以轉職，請再努力一下吧！")
            return
        if player.job != "novice":
            confirm = Confirm(ctx.author)
            ask = await ctx.send(
                "想要轉職成為其他職業，將會消耗10等級，請確認是否同意。", view=confirm
            )
            await confirm.wait()
            if confirm.value:
                player.reset_ability_points()
                await self.set_player(ctx.author, player)
            else:
                await ctx.send("取消轉職。")
                return

        advance_view = job_advancement()
        e = Embed(
            title="轉職",
            description="請選擇你想要成為的職業",
            color=self.bot.color,
        )
        for k, v in self.job.items():
            v: Job
            if k == "novice":
                continue
            e.add_field(
                name=v.name,
                value=f"```st\n{v.description}\n```",
                inline=False,
            )
        e.set_footer(text="請在60秒內選擇職業，超過時間將會自動取消。")
        ask = await ctx.send(embed=e, view=advance_view)
        await advance_view.wait()
        if advance_view.value in ["", None]:
            await ctx.send("取消轉職。")
        else:
            name = await self.set_job(ctx.author, advance_view.value)
            await self.reload_equipment_stats(ctx.author)
            await ctx.send(f"轉職成功！你現在是**{name}**了！")
        await ask.delete()

    @commands.command(name="addstats", aliases=["配點"])
    @commands.dm_only()
    async def addstats(self, ctx: commands.Context, stat: str, pts: int) -> None:
        if self.check_in_raid(ctx.author.id):
            await ctx.send("你正在副本中，無法配點")
            return
        if pts <= 0:
            await ctx.send("配點不能小於1。")
            return
        pts = min(max(pts, 0), 100)
        player = await self.get_player(ctx.author)
        if pts > player.remain_stats:
            await ctx.send("你沒有足夠的配點點數，請確認你的輸入是否正確。")
            return
        if stat not in ["力量", "敏捷", "智慧", "體質", "str", "dex", "con", "wis"]:
            await ctx.send("請輸入正確的配點項目。")
            return
        if stat in ["str", "力量"]:
            player.stats.str += pts
        elif stat in ["dex", "敏捷"]:
            player.stats.dex += pts
        elif stat in ["con", "體質"]:
            player.stats.con += pts
        elif stat in ["wis", "智慧"]:
            player.stats.wis += pts
        player.remain_stats -= pts

        await self.set_player(ctx.author, player)
        await ctx.send(f"配點成功！你的{stat}增加了{pts}點。")

    # @commands.command(name="soulforge", aliases=["靈魂轉換"])
    # @commands.dm_only()
    # async def soulForge(self, ctx: commands.Context):
    #     "將收集的靈魂碎片重新結合，根據時間會出現不同的物品。"
    #     if self.check_in_raid(ctx.author.id):
    #         await ctx.send("你正在副本中，無法使用靈魂轉換")
    #         return
    #     player = await self.get_player(ctx.author)
    #     if player.soulshard < 240:
    #         return
    #     date = datetime.now()

    #     legendaryItemList = list(self.legendary.keys())
    #     random.Random(int(date.month + date.day)).shuffle(legendaryItemList)
    #     offer = legendaryItemList[int(date.hour)]

    #     # Confirmation
    #     confirm = Confirm(ctx.author)
    #     item = self.legendary[offer]
    #     ask = await ctx.send(
    #         f"將靈魂碎片聚集在一起後浮現出{item.name}的模樣，請問要繼續轉換嗎?",
    #         view=confirm,
    #     )
    #     await confirm.wait()
    #     if confirm.value:
    #         if self.check_in_raid(ctx.author.id):
    #             await ctx.send("你正在副本中，靈魂轉換失敗。")
    #             return
    #         player.soulshard -= 240
    #         await self.set_player(ctx.author, player)
    #         await self.give_legendary_item(ctx.author, offer)
    #         await ctx.send(f"獲得了{item.name}！")
    #     await ask.delete()
