import asyncio
import copy
import io
import pathlib
import random
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Union

import discord
import orjson
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks
from loguru import logger as log

from ...cogs.utils.config import Config
from ...cogs.utils.view import Confirm
from .data.conf import DEV, EXP_MULTIPLIER, FIBONACCI, LEGENDARY_SETS
from .mixins.loader import DungeonLoaderMixin
from .utils.dataclass import Character, Item, Job, Mob, RaidHandler, ServerWorld
from .utils.view import (
    equip_view,
    info_base_view,
    inventory_view,
    job_advancement,
    leaderboard_view,
    raid_init_view,
    stats_view,
)


class Dungeon(commands.Cog, DungeonLoaderMixin):
    __version__ = "3.4.alpha_0.1"

    def __init__(self, bot):
        self.bot: commands.AutoShardedBot = bot
        self.global_raid_lock = False
        self.user_data = Config("dungeon_player.json", loop=bot.loop)
        self.user_inventory = Config("dungeon_inventory.json", loop=bot.loop)
        self.world_data = Config("dungeon_guild.json", loop=bot.loop)
        self.world_raid_lock = {}  # type: dict[int, list(discord.TextChannel.id, int)]
        self.char_raid_lock = {}  # type: dict[int, list(discord.TextChannel.id, int)]
        self.load_dungeon()
        self.auto_check.start()

        # load context menu
        self.ctx_menu = app_commands.ContextMenu(
            name="角色資訊",
            callback=self.checkusercontext,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.auto_check.cancel()
        await super().cog_unload()

    @commands.Cog.listener(name="on_guild_join")
    async def on_guild_join(self, guild: discord.Guild) -> None:
        required_perms = discord.Permissions(permissions=432248712256)
        bot_member: discord.Member = guild.get_member(self.bot.user.id)
        if bot_member.guild_permissions < required_perms:
            log.info(f"Missing permissions, leaving guild({guild.name} | {guild.id}).")
            await guild.leave()

    @tasks.loop(minutes=10)
    async def auto_check(self) -> None:
        """Auto check."""
        log.info("Checking for unremoved locks.")
        removal_list = []
        for k, v in self.world_raid_lock.items():
            if v[1] <= time.time() - 180:
                removal_list.append(k)
        if removal_list:
            log.info("Removed %d world raid locks.", len(removal_list))
            for k in removal_list:
                self.world_raid_lock.pop(k)
        removal_list = []
        for k, v in self.char_raid_lock.items():
            if v[1] <= time.time() - 180:
                removal_list.append(k)
        if removal_list:
            log.info("Removed %d character raid locks.", len(removal_list))
            for k in removal_list:
                self.char_raid_lock.pop(k)

    # owner commands
    @commands.command(name="lock")
    @commands.is_owner()
    async def lock_raid(self, ctx: commands.Context) -> None:
        """Lock all raid."""
        self.global_raid_lock = not self.global_raid_lock
        await ctx.send(f"Raid lock is currently {self.global_raid_lock}.")
        log.critical(f"Raid lock is currently {self.global_raid_lock}.")

    @commands.command(name="raids")
    @commands.is_owner()
    async def list_raids(self, ctx: commands.Context) -> None:
        """List all existing raids."""
        if self.world_raid_lock:
            await ctx.send(
                "Existing raids:\n"
                + "\n".join(
                    f"{self.bot.get_guild(k)}: <t:{v[1]}:R>"
                    for k, v in self.world_raid_lock.items()
                )
            )
        else:
            await ctx.send("No existing guild raids.")

    # cog commands
    @app_commands.command(name="info", description="檢視相關資訊")
    @app_commands.rename(subject="關於")
    @app_commands.choices(
        subject=[
            Choice(name="角色", value="character"),
            Choice(name="世界", value="guild"),
        ]
    )
    async def info(
        self,
        interaction: discord.Interaction,
        subject: str,
    ) -> None:
        if subject == "character":
            await self.send_base_view(interaction)

        elif subject == "guild":
            await self.send_world_view(interaction)
        else:
            await interaction.response.send_message("Unknown subject.")

    # https://github.com/Rapptz/discord.py/issues/7823#issuecomment-1086830458
    # @app_commands.context_menu(name="角色資訊")
    async def checkusercontext(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        embed = await self.user_baseinfo(user)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set", description="設定遊戲相關資訊")
    @app_commands.choices(
        subject=[
            Choice(name="角色狀態", value="set_status"),
            Choice(name="遊戲顏色", value="set_colour"),
        ],
    )
    @app_commands.rename(subject="設定", content="內容")
    @app_commands.describe(
        subject="角色狀態會顯示在角色資訊，遊戲顏色為顯示框顏色", content="狀態可以直接輸入，顏色請輸入顏色代碼"
    )
    async def _set(
        self,
        interaction: discord.Interaction,
        subject: str,
        content: str,
    ):
        """"""
        player = await self.get_player(interaction.user)

        if not (player.rebirth or player.level >= 5):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="角色需要5等才能變更狀態", colour=discord.Colour.red()
                ),
                ephemeral=True,
            )
            return

        if subject == "set_status":
            await self.set_status(interaction, player, content)

        elif subject == "set_colour":
            await self.set_colour(interaction, player, content)

    async def set_status(
        self, interaction: discord.Interaction, player: Character, status: str
    ) -> None:
        player.status = status
        await self.user_data.put(interaction.user.id, player.__dict__())
        await interaction.response.send_message(
            embed=discord.Embed(
                description="個人狀態已更改為: `{}`".format(status),
                colour=discord.Colour.green(),
            ),
            ephemeral=True,
        )

    async def set_colour(
        self, interaction: discord.Interaction, player: Character, colour: str
    ) -> None:
        try:
            colour = discord.Colour.from_str(colour)
        except ValueError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="顏色格式錯誤，請輸入色碼", colour=discord.Colour.red()
                ),
                ephemeral=True,
            )
            return
        player.colour = colour
        await self.user_data.put(interaction.user.id, player.__dict__())
        await interaction.response.send_message(
            embed=discord.Embed(
                description="個人顏色已更改",
                colour=colour,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="worldset", description="設定世界內容")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(
        subject=[
            Choice(name="名稱", value="set_world_name"),
            Choice(name="狀態", value="set_world_status"),
            Choice(name="顏色", value="set_world_colour"),
        ],
    )
    @app_commands.rename(subject="設定", content="內容")
    @app_commands.describe(subject="更改伺服器世界的名稱，狀態，以及專屬顏色", content="名稱與狀態請輸入文字，顏色請輸入色碼")
    async def _worldset(
        self,
        interaction: discord.Interaction,
        subject: str,
        content: str,
    ):
        world = await self.get_world(interaction.guild)
        if not world.level:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="世界需要1等才能更改名稱", colour=discord.Colour.red()
                ),
                ephemeral=True,
            )
            return
        if subject == "set_world_name":
            await self.set_world_name(interaction, world, content)

        elif subject == "set_world_status":
            await self.set_world_status(interaction, world, content)

        elif subject == "set_world_colour":
            await self.set_world_colour(interaction, world, content)

    async def set_world_name(
        self, interaction: discord.Interaction, world: ServerWorld, content: str
    ) -> None:
        world.name = content
        await self.world_data.put(interaction.guild.id, world.__dict__())
        await interaction.response.send_message(
            embed=discord.Embed(
                description="世界名稱已更改為: `{}`".format(content),
                colour=discord.Colour.green(),
            )
        )

    async def set_world_status(
        self, interaction: discord.Interaction, world: ServerWorld, content: str
    ) -> None:
        world.status = content
        await self.world_data.put(interaction.guild.id, world.__dict__())
        await interaction.response.send_message(
            embed=discord.Embed(
                description="世界狀態已更改為: `{}`".format(content),
                colour=discord.Colour.green(),
            )
        )

    async def set_world_colour(
        self, interaction: discord.Interaction, world: ServerWorld, content: str
    ) -> None:
        try:
            colour = discord.Colour.from_str(content)
        except ValueError:
            await interaction.response.send_message("顏色格式錯誤，請輸入色碼")
            return
        world.colour = colour
        await self.world_data.put(interaction.guild.id, world.__dict__())
        await interaction.response.send_message(
            embed=discord.Embed(description="世界顏色已更改", colour=colour)
        )

    @_worldset.error
    async def _worldset_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, discord.errors.Forbidden):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="權限不足，需要管理員權限",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        elif isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="權限不足，需要管理員權限",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
        else:
            log.error(error)

    @app_commands.command(name="backpack", description="查看物品欄位")
    async def player_inventoy(self, interaction: discord.Interaction):
        inventory_embeds = await self.build_inventory_embeds(interaction)
        await interaction.response.defer(thinking=True)
        await self.inven_view(interaction, inventory_embeds)

    @app_commands.command(name="transfer", description="轉贈物品於其他玩家")
    @app_commands.rename(item_id="物品", user="玩家")
    @app_commands.describe(item_id="請輸入物品代碼，可以從/backpack 找到物品代碼", user="請選擇玩家")
    async def transfer_item(
        self,
        interaction: discord.Interaction,
        item_id: str,
        user: discord.User,
    ):
        # await interaction.response.defer(thinking=True)
        result: Item = self.get_user_item(interaction.user, item_id)  # type: ignore
        player = await self.get_player(interaction.user)
        target_player = await self.get_player(user)
        if player.level < 5 or target_player.level < 5:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="雙方需要5等才能轉贈物品",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if not result:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品轉贈失敗，請確認物品代碼是否正確",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if self.in_player_equips(player, item_id):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品轉贈失敗，裝備目前使用中",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if len(target_player.inventory) >= target_player.allowed_inventory:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品轉贈失敗，對方物品欄位已滿",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if result.set in ["Behemoth", "Leviathan", "Tiamat"]:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品轉贈失敗，傳說物品無法被轉贈",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if interaction.user.id in self.char_raid_lock or user.id in self.char_raid_lock:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品轉贈失敗，請等待雙方副本結束",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        await self.remove_item(interaction.user, item_id)
        await self.give_item(user, result)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"物品轉贈成功，{user.mention}已獲得{result.name}",
                colour=discord.Colour.green(),
            )
        )

    @app_commands.command(name="chest", description="開啟補給箱")
    async def open_chest(self, interaction: discord.Interaction):
        if self.check_in_raid(interaction.user.id):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="目前無法使用補給箱，請等待副本結束",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        player = await self.get_player(interaction.user)
        if player.level < 5:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="需要5等才能開啟補給箱",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if player.chest < 20:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="還沒有獲得補給箱喔，試著多多參加討伐吧！",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        if player.allowed_inventory <= len(player.inventory):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品欄位已滿，請先清理物品欄位",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        player.chest -= 20
        await self.set_player(interaction.user, player)
        if 0.05 > random.random():
            player.soulshard += 1
            await self.set_player(interaction.user, player)
            embed = discord.Embed(
                description="開啟補給箱後發現了一片靈魂碎片",
                colour=discord.Colour.dark_purple(),
            )
            embed.set_footer(text=f"剩餘補給箱數量: {player.chest/20:.0f}")
            await interaction.response.send_message(embed=embed)
        else:
            if interaction.guild is None:
                item = self.create_item(
                    random.choice(list(self.item.values())), min(player.level, 10)
                )
            else:
                world = await self.get_world(interaction.guild)
                item = self.create_item(
                    random.choice(list(self.item.values())),
                    min(player.level, world.level * 10),
                )
            item_id = await self.give_item(interaction.user, item)
            embed = discord.Embed(
                description=f"補給箱已開啟，獲得{item.name}\n代碼: {item_id}",
                colour=discord.Colour.green(),
            )
            embed.set_footer(text=f"剩餘補給箱數量：{int(player.chest/20):.0f}")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reinforce", description="強化裝備")
    @app_commands.rename(item_id="物品")
    @app_commands.describe(item_id="請輸入物品代碼，可以從/backpack 找到物品代碼")
    async def reinforce(self, interaction: discord.Interaction, item_id: str):
        if self.check_in_raid(interaction.user.id):
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="目前無法強化裝備，請等待副本結束",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        player = await self.get_player(interaction.user)
        if player.soulshard < 1:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="靈魂碎片不足，請在獲得碎片後再回來。",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        item = self.get_user_item(interaction.user, item_id)
        if item is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="物品不存在，請確認物品代碼是否正確",
                    colour=discord.Colour.red(),
                ),
                ephemeral=True,
            )
            return
        item_name = item.name.split(" ")[2]
        confirm = Confirm(interaction.user)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"確定要強化{item.name}嗎?", color=self.bot.color
            ),
            view=confirm,
        )
        await confirm.wait()
        if not confirm.value:
            await interaction.edit_original_response(
                embed=discord.Embed(description="已取消強化裝備。", color=self.bot.color),
                view=None,
            )
            return
        if self.check_in_raid(interaction.user.id):
            await interaction.edit_original_response(
                embed=discord.Embed(
                    description="目前無法強化裝備，請等待副本結束",
                    colour=discord.Colour.red(),
                ),
                view=None,
            )
            log.info(f"{interaction.user} is in raid, while trying to reinforce item.")
            return
        # else
        result = await self.reinforce_item(interaction.user, item_id)

        item = self.get_user_item(interaction.user, item_id)

        if result is None:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    description=f"{item_name}吸收了靈魂碎片之後化為粉塵，你把能找到的靈魂碎片收進了背包。",
                    color=discord.Colour.dark_gray(),
                ),
                view=None,
            )
        elif result is False:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    description=(
                        f"{item_name}與靈魂碎片融合失敗。"
                        f" \n獲得了{item.name} {self.int2Roman(item.reinforced)}。"
                    ),
                    color=discord.Colour.light_gray(),
                ),
                view=None,
            )
        elif result is True:
            await interaction.edit_original_response(
                embed=discord.Embed(
                    description=(
                        f"{item_name}碰觸靈魂碎片時，閃耀出了新的光芒。\n獲得了{item.name} {self.int2Roman(item.reinforced)}。"
                    ),
                    color=discord.Colour.gold(),
                ),
                view=None,
            )

    @app_commands.command(name="deletemydata", description="刪除關於我的資料")
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def _clearmydata(self, interaction: discord.Interaction):
        view = Confirm(interaction.user)
        await interaction.response.send_message(
            embed=discord.Embed(description="確定要清除你的資料嗎?", color=self.bot.color),
            view=view,
        )
        await view.wait()
        if view.value:
            await self.user_data.remove(interaction.user.id)
            await self.user_inventory.remove(interaction.user.id)
            await interaction.edit_original_response(
                embed=discord.Embed(description="資料已清除", color=self.bot.color),
                view=None,
            )
        else:
            await interaction.edit_original_response(
                embed=discord.Embed(description="已取消", color=self.bot.color),
                view=None,
            )

    @app_commands.command(name="leaderboard", description="排行榜")
    async def _leaderboard(self, interaction: discord.Interaction):
        data = self.user_data.all()
        data = {
            k: v
            for k, v in sorted(
                data.items(),
                key=lambda d: (d[1]["rebirth"], d[1]["level"], d[1]["exp"]),
                reverse=True,
            )
            if int(k) not in DEV
        }
        data = {k: data[k] for k in list(data)[:50]}
        player_list = []
        for i, (k, v) in enumerate(data.items(), start=1):
            p_info = {}
            user = self.bot.get_user(int(k))
            name = f"{user.name}#{user.discriminator}" if user else "Unknown User"
            p_info["name"] = name
            p_info["rebirth"] = v["rebirth"]
            p_info["level"] = v["level"]
            p_info["uuid"] = k
            p_info["rank"] = i
            p_info["exp"] = v["exp"]
            player_list.append(p_info)
        leaderboard_embeds = []
        for _ in range(0, 50, 5):
            leaderboard_embed = discord.Embed(
                title="Dungeon 排行榜", colour=self.bot.color
            )
            leaderboard_embed.set_thumbnail(url=self.bot.user.avatar.url)
            for player in player_list[_ : _ + 5]:  # noqa: E203
                leaderboard_embed.add_field(
                    name=f"No. {int(player['rank']):03d} - {player['name']}",
                    value=(
                        f"`UUID: {player['uuid']}`\nLv. {player['level']:,} exp."
                        f" {player['exp']:,}"
                    ),
                    inline=False,
                )
            self.stamp_footer(leaderboard_embed)
            leaderboard_embeds.append(leaderboard_embed)

        lb_view = leaderboard_view(interaction.user, leaderboard_embeds)
        await interaction.response.send_message(
            embed=leaderboard_embeds[0], view=lb_view
        )

        result = await lb_view.wait()
        if lb_view.index == "close":
            await interaction.delete_original_response()
        elif isinstance(result, bool):
            await interaction.edit_original_response(
                embed=leaderboard_embeds[lb_view.index],
                view=None,
            )

    @app_commands.command(name="dungeon", description="開啟副本")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 120, key=lambda i: i.guild.id)
    async def _dungeon_start(self, interaction: discord.Interaction) -> None:
        """Start a raid."""
        if self.global_raid_lock:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="錯誤訊息",
                    description="副本入口關閉中，請稍後再試",
                    colour=discord.Colour.red(),
                )
            )
            return
        world = await self.get_world(interaction.guild)
        if interaction.guild_id in self.world_raid_lock.keys():
            e = discord.Embed(
                title="這個世界已經有正在進行中的副本。",
                description=(
                    f"副本位置: <#{self.world_raid_lock[interaction.guild_id][0]}>\n"
                ),
                colour=world.colour,
            )
            self.stamp_footer(e)
            await interaction.response.send_message(
                embed=e,
                ephemeral=True,
            )
            return

        raid = RaidHandler(
            interaction, world.mob_level, random.choice(list(self.mob.values()))
        )

        self.world_raid_lock[interaction.guild_id] = [
            interaction.channel_id,
            int(time.time() + raid.preptime),
        ]  # LOCK THAT SHIT

        init_view = raid_init_view(self.bot, raid.preptime)
        embed = discord.Embed(
            title="有冒險者發起了副本!", description=raid.hint, colour=world.colour
        )
        self.stamp_footer(embed)
        embed.add_field(
            name="世界等級", value=f"```st\nLv. {world.level}\n```", inline=True
        )
        embed.add_field(
            name="剩餘參加時間",
            value=f"<t:{int(time.time()+raid.preptime)}:R>",
            inline=True,
        )
        try:
            await interaction.response.send_message(
                embed=embed,
                view=init_view,
            )
        except Exception as e:
            log.info("Dungeon init failed: %s", e)
            self.world_raid_lock.pop(interaction.guild_id)
            return

        await asyncio.sleep(raid.preptime)  # im fucking retarded

        init_view.join_raid.disabled = True
        embed.clear_fields()
        embed.add_field(
            name="世界等級", value=f"```st\nLv. {world.level}\n```", inline=True
        )
        embed.add_field(
            name="剩餘參加時間",
            value="```diff\n- 參加時間截止 -\n```",
            inline=True,
        )
        await interaction.edit_original_response(
            embed=embed,
            view=init_view,
        )

        await asyncio.sleep(1)  # ensure everyone joined

        if len(init_view.value) == 0:
            self.world_raid_lock.pop(interaction.guild_id)
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title="由於沒有人敢挑戰副本，副本已關閉",
                    colour=world.colour,
                ),
                view=None,
            )
        else:
            self.world_raid_lock.pop(interaction.guild_id)

            await self.start_raid(interaction, raid, list(init_view.value))

    @_dungeon_start.error
    async def _dungeon_start_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """Handle raid command error."""
        if isinstance(error, commands.CheckFailure):
            await interaction.channel.send("CheckFailure")
        elif isinstance(error, commands.CommandOnCooldown):
            await interaction.channel.send("CommandOnCooldown")
        elif isinstance(error, app_commands.errors.CommandOnCooldown):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="副本冷卻中！",
                    description=f"請稍後再試，大約<t:{int(time.time()+error.retry_after)}:R>",
                    color=self.bot.color,
                ),
                ephemeral=True,
            )
        elif isinstance(error, discord.errors.NotFound):
            await interaction.channel.send("Discord 連結失敗。")
        else:
            await interaction.channel.send("Unknown error")
            log.error("Unknown error in raid command", exc_info=error)

    @commands.command(name="resetstats", aliases=["重置配點"])
    @commands.dm_only()
    async def resetstats(self, ctx: commands.Context) -> None:
        if self.check_in_raid(ctx.author.id):
            await ctx.send("你正在副本中，無法重置配點")
            return
        player = await self.get_player(ctx.author)
        if player.level < 15:
            await ctx.send("重置配點需要至少等級15！")
            return
        confirm = Confirm(ctx.author)
        ask = await ctx.send("重置配點將會降低角色等級 10等，請確認是否同意。", view=confirm)
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
            ask = await ctx.send("想要轉職成為其他職業，將會消耗10等級，請確認是否同意。", view=confirm)
            await confirm.wait()
            if confirm.value:
                player.reset_ability_points()
                await self.set_player(ctx.author, player)
            else:
                await ctx.send("取消轉職。")
                return

        advance_view = job_advancement()
        e = discord.Embed(
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

    @commands.command(name="soulforge", aliases=["靈魂轉換"])
    @commands.dm_only()
    async def soulForge(self, ctx: commands.Context):
        "將收集的靈魂碎片重新結合，根據時間會出現不同的物品。"
        if self.check_in_raid(ctx.author.id):
            await ctx.send("你正在副本中，無法使用靈魂轉換")
            return
        player = await self.get_player(ctx.author)
        if player.soulshard < 240:
            return
        date = datetime.now()

        legendaryItemList = list(self.legendary.keys())
        random.Random(int(date.month + date.day)).shuffle(legendaryItemList)
        offer = legendaryItemList[int(date.hour)]

        # Confirmation
        confirm = Confirm(ctx.author)
        item = self.legendary[offer]
        ask = await ctx.send(f"將靈魂碎片聚集在一起後浮現出{item.name}的模樣，請問要繼續轉換嗎?", view=confirm)
        await confirm.wait()
        if confirm.value:
            if self.check_in_raid(ctx.author.id):
                await ctx.send("你正在副本中，靈魂轉換失敗。")
                return
            player.soulshard -= 240
            await self.set_player(ctx.author, player)
            await self.give_legendary_item(ctx.author, offer)
            await ctx.send(f"獲得了{item.name}！")
        await ask.delete()

    # command functions
    def fib_index(self, n: int) -> int:
        for i, v in enumerate(FIBONACCI):
            if v > n:
                return max(i, 1)
        return len(FIBONACCI)

    def stamp_footer(self, e: discord.Embed) -> None:
        e.set_footer(text=f"{self.__class__.__name__} version: {self.__version__}")
        e.timestamp = datetime.now()

    async def send_base_view(self, interaction: discord.Interaction) -> None:
        """Send base view."""
        base_view: discord.ui.View = info_base_view(interaction.user)
        base_embed = await self.user_baseinfo(interaction.user)
        try:
            await interaction.response.send_message(embed=base_embed, view=base_view)
        except discord.errors.InteractionResponded:
            await interaction.edit_original_response(embed=base_embed, view=base_view)
        except Exception as e:
            log.error(e)

        result = await base_view.wait()

        if base_view.value == "statsrecord":
            await self.statsrec_view(
                interaction, await self.user_statsrecord(interaction.user)
            )
        elif base_view.value == "equipments":
            await self.equipment_view(
                interaction, await self.user_equipments(interaction.user)
            )
        elif isinstance(result, bool):
            await interaction.edit_original_response(embed=base_embed, view=None)

    async def statsrec_view(
        self, interaction: discord.Interaction, embed: discord.Embed
    ) -> None:
        """Send stat view."""
        player = await self.get_player(interaction.user)
        sub_view = stats_view(interaction.user, player.remain_stats)

        await interaction.edit_original_response(embed=embed, view=sub_view)
        result = await sub_view.wait()
        if sub_view.value == "ret":
            return await self.send_base_view(interaction)
        elif sub_view.value == "str":
            player.stats.str += 1
            player.remain_stats -= 1
        elif sub_view.value == "dex":
            player.stats.dex += 1
            player.remain_stats -= 1
        elif sub_view.value == "con":
            player.stats.con += 1
            player.remain_stats -= 1
        elif sub_view.value == "wis":
            player.stats.wis += 1
            player.remain_stats -= 1
        elif isinstance(result, bool):
            return await interaction.edit_original_response(embed=embed, view=None)

        await self.set_player(interaction.user, player)
        await self.statsrec_view(
            interaction, await self.user_statsrecord(interaction.user)
        )

    async def equipment_view(
        self, interaction: discord.Interaction, embed: discord.Embed
    ) -> None:
        """Send equip view."""
        sub_view = equip_view(interaction.user)
        await interaction.edit_original_response(embed=embed, view=sub_view)
        result = await sub_view.wait()
        if sub_view.value == "ret":
            await self.send_base_view(interaction)
        elif isinstance(result, bool):
            await interaction.edit_original_response(embed=embed, view=None)

    def int2Roman(self, num: int):
        values = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        numerals = [
            "M",
            "CM",
            "D",
            "CD",
            "C",
            "XC",
            "L",
            "XL",
            "X",
            "IX",
            "V",
            "IV",
            "I",
        ]
        result, i = "", 0
        while num:
            result += (num // values[i]) * numerals[i]
            num %= values[i]
            i += 1
        return result

    async def build_inventory_embeds(
        self, interaction: discord.Interaction
    ) -> Dict[str, discord.Embed]:
        player = await self.get_player(interaction.user)
        player_inventory: List = player.inventory
        inventory_embed = {}
        missing_items = []
        for it, item_id in enumerate(player_inventory, start=1):
            item: Item = self.get_user_item(interaction.user, item_id)
            if item is None:
                missing_items.append(item_id)
                continue
            t = item.name
            if item.reinforced:
                t += f" {self.int2Roman(item.reinforced)}"

            if item_id in [
                player.head,
                player.necklace,
                player.body,
                player.pants,
                player.gloves,
                player.boots,
                player.weapon,
                player.ring,
            ]:
                t += " (已裝備)"

            e = discord.Embed(
                title=t, description=item.description, colour=player.colour
            )
            e.set_author(name=f"物品欄 ({it}/{len(player_inventory)})")
            category_text = ""
            if item.category == "head":
                category_text = "頭部"
            elif item.category == "necklace":
                category_text = "項鍊"
            elif item.category == "body":
                category_text = "上衣"
            elif item.category == "pants":
                category_text = "褲子"
            elif item.category == "gloves":
                category_text = "手套"
            elif item.category == "boots":
                category_text = "靴子"
            elif item.category == "weapon":
                category_text = "武器"
            elif item.category == "ring":
                category_text = "戒指"
            e.add_field(
                name="裝備類別",
                value=category_text,
                inline=True,
            )
            if item.reinforced:
                stars = ""
                rein = item.reinforced
                stars += ":sparkles:" * int(rein / 10)
                rein = rein % 10
                stars += ":star2:" * int(rein / 5)
                rein = rein % 5
                stars += ":star:" * rein
                e.add_field(
                    name="強化等級",
                    value=stars,
                    inline=True,
                )
            itemstats = [
                (
                    f"力量 {item.str:+}"
                    + (
                        f"({item.reinforced_stats.str:+})\n"
                        if item.reinforced
                        else "\n"
                    )
                )
                if item.str
                else "",
                (
                    f"敏捷 {item.dex:+}"
                    + (
                        f"({item.reinforced_stats.dex:+})\n"
                        if item.reinforced
                        else "\n"
                    )
                )
                if item.dex
                else "",
                (
                    f"體質 {item.con:+}"
                    + (
                        f"({item.reinforced_stats.con:+})\n"
                        if item.reinforced
                        else "\n"
                    )
                )
                if item.con
                else "",
                (
                    f"智慧 {item.wis:+}"
                    + (
                        f"({item.reinforced_stats.wis:+})\n"
                        if item.reinforced
                        else "\n"
                    )
                )
                if item.wis
                else "",
                f"幸運 {item.luk:+}\n" if item.luk else "",
            ]
            itemstats = "".join(itemstats)
            e.add_field(
                name="屬性加成",
                value="無" if len(itemstats) == 0 else itemstats,
                inline=False,
            )
            e.set_footer(
                text=(
                    "物品代碼:"
                    f" {item_id}{(f'{chr(10)}包含碎片: {item.reinforce_attempts}') if item.reinforced else ''}"
                )
            )
            inventory_embed[item_id] = e
        # fuck this shit
        if len(missing_items) > 0:
            for item_id in missing_items:
                player_inventory.remove(item_id)
            await self.set_player(interaction.user, player)
        return inventory_embed

    async def inven_view(
        self,
        interaction: discord.Interaction,
        embeds: Dict[str, discord.Embed],
    ):
        """Send inventory view."""
        if len(embeds) == 0:
            await interaction.edit_original_response(
                embed=discord.Embed(description="你的物品欄是空的", color=discord.Color.red()),
                view=None,
            )
            return
        view = inventory_view(interaction.user, embeds)
        await interaction.edit_original_response(
            embed=embeds[list(embeds.keys())[0]], view=view
        )
        result = await view.wait()
        if view.value == "equip":
            player = await self.get_player(interaction.user)
            if self.in_player_equips(player, view.selection):
                await self.unequip_item(interaction.user, view.selection)
            else:
                await self.equip_item(interaction.user, view.selection)

        elif view.value == "drop":
            result = await self.remove_item(interaction.user, view.selection)
            if not result:
                await interaction.followup.send(
                    embed=discord.Embed(
                        description="裝備中的物品無法丟棄", color=discord.Color.red()
                    ),
                    ephemeral=True,
                )

        elif isinstance(result, bool):
            return await interaction.edit_original_response(
                embed=embeds[view.selection], view=None
            )
        inventory_embeds = await self.build_inventory_embeds(interaction)
        await self.inven_view(interaction, inventory_embeds)

    def create_item(self, item_ptr: Item, item_level: int = 1) -> Item:
        """Create item."""
        item = item_ptr.__copy__()
        item.level = item_level
        item.name = f"Lv. {item.level} {item.name}"
        item.stats_adjustment()
        return item

    # player related functions
    def get_user_item(self, user: discord.User, item_id: str) -> Optional[Item]:
        """Get specific user item."""
        inventory = self.user_inventory.get(user.id, None)
        if not inventory:
            log.info(f"can't find inventory, user: {user.name} | item: {item_id}")
            return None
        item = inventory.get(item_id, None)
        if not item:
            log.info(f"can't find item, user: {user.name} | item: {item_id}")
            return None
        return Item(data=item)

    async def reinforce_item(
        self, user: discord.User, item_id: str, rigged=False
    ) -> bool:
        """Reinforce item."""
        item = self.get_user_item(user, item_id)
        user_inventory: dict = self.user_inventory.get(user.id, None)

        player: Character = await self.get_player(user)
        player.soulshard -= 1
        result = item._reinforce()
        if result is None and not rigged:
            for parts in [
                player.head,
                player.necklace,
                player.body,
                player.pants,
                player.gloves,
                player.boots,
                player.weapon,
                player.ring,
            ]:
                if parts == item_id:
                    parts = ""
                    break
            player.inventory.remove(item_id)
            user_inventory.pop(item_id, None)
            if item.set in LEGENDARY_SETS:
                player.soulshard += item.reinforce_attempts
                player.soulshard += 210
            else:
                player.soulshard += item.reinforce_attempts
        else:
            item._reinforce_adjustment()
            user_inventory.update({item_id: item.__dict__()})

        await self.user_inventory.put(user.id, user_inventory)
        await self.set_player(user, player)
        await self.reload_equipment_stats(user)
        return result

    async def give_item(self, user: discord.User, item: Item) -> Union[bool, str]:
        """Give an item to a player."""
        item_id = str(uuid.uuid4())

        user_inventory: dict = self.user_inventory.get(user.id, {})
        user_data: dict = self.user_data.get(user.id, None)

        if len(user_inventory) >= user_data["allowed_inventory"]:
            return False

        user_inventory[item_id] = copy.copy(item.__dict__())
        await self.user_inventory.put(user.id, user_inventory)

        user_data["inventory"].append(item_id)
        await self.user_data.put(user.id, user_data)

        return item_id

    async def give_legendary_item(
        self, user: discord.User, item_name: str, reinforce: int = 0
    ) -> Union[bool, str]:
        """Give a legendary item to a player."""
        item_id = str(uuid.uuid4())

        user_inventory = self.user_inventory.get(user.id, {})
        user_data: dict = self.user_data.get(user.id, None)

        if len(user_inventory) >= user_data["allowed_inventory"]:
            return False

        item: Item = self.legendary[item_name].__copy__()
        item.name = f"Lv. {item.level} {item.name}"
        item.reinforced = reinforce
        item._reinforce_adjustment()
        user_inventory[item_id] = copy.copy(item.__dict__())
        await self.user_inventory.put(user.id, user_inventory)

        user_data["inventory"].append(item_id)
        await self.user_data.put(user.id, user_data)

        return item_id

    async def set_job(self, user: discord.User, job_name: str) -> Union[bool, str]:
        """Set a player's job."""
        player: Character = await self.get_player(user)
        job: Job = self.job[job_name]
        if not job:
            return False
        player.job = job_name
        player.str_mod = job.str_mod
        player.dex_mod = job.dex_mod
        player.con_mod = job.con_mod
        player.wis_mod = job.wis_mod
        player.luk_mod = job.luk_mod
        await self.set_player(user, player)
        return job.name

    async def base_player(self) -> Character:
        data: Character = Character()
        data.level = 1
        data.stats.str = 3
        data.stats.dex = 3
        data.stats.con = 3
        data.stats.wis = 3
        data.stats.luk = 5
        data.job = "novice"
        data.allowed_inventory = 20
        data.last_seen = int(datetime.timestamp(datetime.now()))
        return data

    async def get_player(self, user: discord.User, create: bool = True) -> Character:
        """Get player from user."""
        data: dict = self.user_data.get(user.id, None)

        if data is None and create:  # create new player
            new_player = await self.base_player()
            await self.user_data.put(user.id, new_player.__dict__())
            item = self.create_item(self.item["wood_stick"], 1)
            item_id = await self.give_item(user, item)
            await self.equip_item(user, item_id)
            await self.set_job(user, "novice")
            data: dict = self.user_data.get(user.id, None)
        elif data is None:
            data = await self.base_player()
            data = data.__dict__()

        return Character(data=data)

    async def set_player(self, user: discord.User, player: Character) -> None:
        """Put player to user."""
        await self.user_data.put(user.id, player.__dict__())

    async def user_baseinfo(self, user: discord.User) -> discord.Embed:
        """Get player info."""
        player = await self.get_player(user, False)
        if player is None:
            player = await self.base_player()
        exp = player.exp
        required = player.exp_required(player.level)
        job = self.job[player.job]
        e = discord.Embed(
            title=f"{user.name}#{user.discriminator}",
            description=player.status,
            colour=player.colour,
        )
        e.set_author(name="角色資訊")
        e.add_field(
            name="\a",
            value=(
                "物品欄空間:"
                f" {len(player.inventory)}/{player.allowed_inventory}\n```fix\n生命數值:"
                f" {player.health:>20,}\n{'物理' if player.damage_type else '魔法'}傷害:"
                f" {f'{player.low_damage:,}~{player.high_damage:,}':>20}\n```"
            ),
            inline=False,
        )
        e.add_field(
            name="• 職業 " + "-" * 15,
            value=f"```fix\n{job.name}```",
            inline=True,
        )
        e.add_field(
            name="• 等級 " + "-" * 15,
            value=(
                "```st\n"
                f"Lv. {player.level}\n"
                f"{f'Re. {player.rebirth:,}' if player.rebirth else ''}"
                "```"
            ),
            inline=True,
        )
        if player.blessing:
            blessings = "\n".join(player.blessing)
            e.add_field(
                name="• 首領的祝福 " + "-" * 30,
                value=f"```fix\n{blessings}\n```",
                inline=False,
            )
        prc_str = f"{(exp/required*100):,.2f}%"
        exp_str = f"{exp:,} / {required:,}"
        nxt_str = f"{required - exp:,}"
        e.add_field(
            name="• 經驗 " + "-" * 40,
            value=(
                "```asciidoc\n"
                f"- 百分比: {prc_str:>20}\n"
                f"- 經驗值: {exp_str:>20}\n"
                f"- 離升等: {nxt_str:>20}\n"
                "```"
            ),
            inline=False,
        )
        if (
            player.remain_stats
            or int(player.chest / 20) > 0
            or len(player.legendary_chest) > 0
            or player.soulshard > 0
        ):
            content_str = ""
            if player.remain_stats:
                content_str += f"剩餘點數: {player.remain_stats:>20,}\n"
            if int(player.chest / 20) > 0:
                content_str += f"補給木箱: {int(player.chest/20):>20,}\n"
            if len(player.legendary_chest) > 0:
                content_str += f"征戰獎勵: {len(player.legendary_chest):>20,}\n"
            if player.soulshard > 0:
                content_str += f"靈魂碎片: {player.soulshard:>20,}\n"
            e.add_field(
                name="• 提醒" + "-" * 40,
                value=f"```fix\n{content_str}\n```",
                inline=False,
            )
        self.stamp_footer(e)
        return e

    async def user_statsrecord(self, user: discord.User) -> discord.Embed:
        """Get player stats and raid record"""
        player: Character = await self.get_player(user)
        e = discord.Embed(
            title=f"{user.name}#{user.discriminator}",
            description=f"**剩餘點數: {player.remain_stats:,}**",
            colour=player.colour,
        )
        e.set_author(name="角色屬性&討伐紀錄")
        e.add_field(
            name="• 角色屬性",
            value=(
                "```st\n"
                f"力量: {player._strength:>5,}{'' if not any([player.equipment_stats.str, player.potential.str]) else f'({player.stats.str:,}{player.equipment_stats.str+player.potential.str:+,})'}\n"
                f"敏捷: {player._dexterity:>5,}{'' if not any([player.equipment_stats.dex, player.potential.dex]) else f'({player.stats.dex:,}{player.equipment_stats.dex+player.potential.dex:+,})'}\n"
                f"體質: {player._constitution:>5,}{'' if not any([player.equipment_stats.con, player.potential.con]) else f'({player.stats.con:,}{player.equipment_stats.con+player.potential.con:+,})'}\n"
                f"智慧: {player._wisdom:>5,}{'' if not any([player.equipment_stats.wis, player.potential.wis]) else f'({player.stats.wis:,}{player.equipment_stats.wis+player.potential.wis:+,})'}\n"
                "```"
            ),
            inline=False,
        )
        e.add_field(
            name="• 討伐紀錄",
            value=(
                "```st\n"
                f"一般怪物: {player.killed_mobs:,}\n"
                f"首領怪物: {player.killed_bosses:,}\n"
                f"最高輸出: {player.max_damage:,}\n"
                f"總輸出: {player.total_damage:,}\n"
                "```"
            ),
            inline=False,
        )
        self.stamp_footer(e)
        return e

    async def user_equipments(self, user: discord.User) -> discord.Embed:
        """Get player raid record."""
        player: Character = await self.get_player(user)
        e = discord.Embed(
            title=f"{user.name}#{user.discriminator}",
            description=player.status,
            colour=player.colour,
        )
        e.set_author(name="角色配戴裝備欄位")
        if player.head:
            item = self.get_user_item(user, player.head)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 頭部", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.necklace:
            item = self.get_user_item(user, player.necklace)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 項鍊", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.body:
            item = self.get_user_item(user, player.body)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 上衣", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.pants:
            item = self.get_user_item(user, player.pants)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 褲子", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.gloves:
            item = self.get_user_item(user, player.gloves)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 手套", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.boots:
            item = self.get_user_item(user, player.boots)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 靴子", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.weapon:
            item = self.get_user_item(user, player.weapon)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 武器", value="\n".join(["```st", item_name, "```"]), inline=False
            )
        if player.ring:
            item = self.get_user_item(user, player.ring)
            item_name = f"{item.name} {self.int2Roman(item.reinforced)}"
            e.add_field(
                name="▹ 戒指", value="\n".join(["```st", item_name, "```"]), inline=False
            )

        self.stamp_footer(e)
        return e

    async def reload_equipment_stats(self, user: discord.User):
        """Reload player equipment stats"""
        player: dict = self.user_data.get(user.id, None)
        if not player:
            raise ValueError("Player not found")
        equipped = [
            player["head"],
            player["necklace"],
            player["body"],
            player["pants"],
            player["gloves"],
            player["boots"],
            player["weapon"],
            player["ring"],
        ]
        player["equipment_stats"]["str"] = 0
        player["equipment_stats"]["dex"] = 0
        player["equipment_stats"]["con"] = 0
        player["equipment_stats"]["wis"] = 0
        player["equipment_stats"]["luk"] = 0
        player["range_adjustment"] = 0

        Behemoth = 0
        Leviathan = 0
        Tiamat = 0

        for item_id in equipped:
            if not item_id:
                continue
            item = self.get_user_item(user, item_id)
            if item is None:
                continue
            player["equipment_stats"]["str"] += item.str
            player["equipment_stats"]["str"] += item.reinforced_stats.str
            player["equipment_stats"]["dex"] += item.dex
            player["equipment_stats"]["dex"] += item.reinforced_stats.dex
            player["equipment_stats"]["con"] += item.con
            player["equipment_stats"]["con"] += item.reinforced_stats.con
            player["equipment_stats"]["wis"] += item.wis
            player["equipment_stats"]["wis"] += item.reinforced_stats.wis
            player["equipment_stats"]["luk"] += item.luk
            player["range_adjustment"] += item.range_adjustment

            if item.set == "Behemoth":
                Behemoth += 1
            if item.set == "Leviathan":
                Leviathan += 1
            if item.set == "Tiamat":
                Tiamat += 1

        blessing = []
        if Behemoth >= 3:
            player["equipment_stats"]["str"] += 200
            player["equipment_stats"]["str"] = int(
                player["equipment_stats"]["str"] * 1.6
            )
            bless = "I"
            if Behemoth >= 6:
                player["equipment_stats"]["dex"] += 300
                bless = "II"
                if Behemoth >= 8:
                    player["equipment_stats"]["dex"] = int(
                        player["equipment_stats"]["dex"] * 2.5
                    )
                    bless = "III"
            blessing.append("貝西摩斯的猖狂 " + bless)
        if Leviathan >= 3:
            player["equipment_stats"]["con"] += 200
            player["equipment_stats"]["con"] = int(
                player["equipment_stats"]["con"] * 1.1
            )
            bless = "I"
            if Leviathan >= 6:
                player["equipment_stats"]["wis"] += 300
                bless = "II"
                if Leviathan >= 8:
                    player["equipment_stats"]["wis"] = int(
                        player["equipment_stats"]["wis"] * 2.1
                    )
                    bless = "III"
            blessing.append("利維坦的傲慢 " + bless)
        if Tiamat >= 3:
            player["equipment_stats"]["str"] += 200
            player["equipment_stats"]["str"] = int(
                player["equipment_stats"]["str"] * 1.9
            )
            bless = "I"
            if Tiamat >= 6:
                player["equipment_stats"]["con"] += 300
                bless = "II"
                if Tiamat >= 8:
                    player["equipment_stats"]["con"] = int(
                        player["equipment_stats"]["con"] * 1.9
                    )
                    bless = "III"
            blessing.append("提亞馬特的狂妄 " + bless)

        player["blessing"] = blessing

        return await self.user_data.put(user.id, player)

    async def equip_item(self, user: discord.User, item_id: str):
        player: dict = self.user_data.get(user.id, None)
        if not player:
            raise ValueError("Player not found")
        if item_id in [
            player["head"],
            player["necklace"],
            player["body"],
            player["pants"],
            player["gloves"],
            player["boots"],
            player["weapon"],
            player["ring"],
        ]:
            return
        item = self.get_user_item(user, item_id)
        if item.level > player["level"] + max(player["rebirth"], 10):
            return
        if not item:
            raise ValueError("Item not found")
        if item.category == "head":
            slot = "head"
        elif item.category == "necklace":
            slot = "necklace"
        elif item.category == "body":
            slot = "body"
        elif item.category == "pants":
            slot = "pants"
        elif item.category == "gloves":
            slot = "gloves"
        elif item.category == "boots":
            slot = "boots"
        elif item.category == "weapon":
            slot = "weapon"
        elif item.category == "ring":
            slot = "ring"
        else:
            raise ValueError("Invalid item category")
        player[slot] = item_id
        await self.user_data.put(user.id, player)
        await self.reload_equipment_stats(user)

    async def unequip_item(self, user: discord.User, item_id: str):
        player: dict = self.user_data.get(user.id, None)
        if not player:
            raise ValueError("Player not found")
        for part in [
            "head",
            "necklace",
            "body",
            "pants",
            "gloves",
            "boots",
            "weapon",
            "ring",
        ]:
            if item_id == player[part]:
                player[part] = ""
                break

        await self.user_data.put(user.id, player)
        await self.reload_equipment_stats(user)

    def in_player_equips(self, player: Character, item_id: str):
        return item_id in [
            player.head,
            player.necklace,
            player.body,
            player.pants,
            player.gloves,
            player.boots,
            player.weapon,
            player.ring,
        ]

    async def remove_item(self, user: discord.User, item_id: str) -> bool:
        player: Character = await self.get_player(user)
        if self.in_player_equips(player, item_id):
            return False
        if not player:
            raise ValueError("Player not found")
        item = self.get_user_item(user, item_id)
        if not item:
            raise ValueError("Item not found")
        player.inventory.remove(item_id)
        await self.set_player(user, player)

        user_inventory = self.user_inventory.get(user.id, None)
        user_inventory.pop(item_id, None)
        await self.user_inventory.put(user.id, user_inventory)
        return True

    # world related functions
    async def get_world(self, guild: discord.Guild) -> ServerWorld:
        """Get world from guild."""
        data = self.world_data.get(guild.id, None)
        if data is None:
            data = ServerWorld()
            data.name = guild.name
            await self.set_world(guild, data)
        else:
            data = ServerWorld(data=data)
        return data

    async def set_world(self, guild: discord.Guild, world: ServerWorld) -> None:
        """Set world for guild."""
        await self.world_data.put(guild.id, world.__dict__())

    async def world_baseinfo(self, guild: discord.Guild) -> discord.Embed:
        """Get world info."""
        world = await self.get_world(guild)
        e = discord.Embed(
            title=f"{guild.name}",
            description=world.status,
            colour=world.colour,
        )
        e.set_author(name="世界資訊")
        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)
        if guild.premium_subscription_count > 1:
            e.add_field(
                name="• 世界增幅",
                value=(
                    f"```fix\n加成等級: {guild.premium_tier}\n經驗加成:"
                    f" {guild.premium_tier*5}%\n```"
                ),
                inline=False,
            )
        e.add_field(
            name="• 世界等級",
            value=f"```st\nLv. {world.level}```",
            inline=True,
        )
        e.add_field(
            name="• 世界主人",
            value=f"```fix\n{guild.owner.name}#{guild.owner.discriminator}```",
            inline=True,
        )
        e.add_field(
            name="• 世界數據",
            value=(
                "```asciidoc\n"
                f"- 擊殺首領: {world.killed_bosses:>40,}\n"
                f"- 擊殺怪物: {world.killed_mobs:>40,}\n"
                "```"
            ),
            inline=False,
        )
        required = world.exp_required(world.level)
        prc_str = f"{(world.exp/required*100):,.2f}%"
        exp_str = f"{world.exp:,} / {required:,}"
        nxt_str = f"{required - world.exp:,}"
        e.add_field(
            name="• 世界經驗值",
            value=(
                "```asciidoc\n"
                f"- 百分比: {prc_str:>40}\n"
                f"- 經驗值: {exp_str:>40}\n"
                f"- 離升等: {nxt_str:>40}\n"
                "```"
            ),
            inline=False,
        )
        self.stamp_footer(e)
        return e

    async def send_world_view(self, interaction: discord.Interaction):
        """Send world view."""
        e = await self.world_baseinfo(interaction.guild)
        await interaction.response.send_message(embed=e)

    def check_in_raid(self, user_id):
        if user_id in self.char_raid_lock.keys():
            return True
        return False

    # raid related functions
    async def start_raid(
        self,
        interaction: discord.Interaction,
        raidhandler: RaidHandler,
        participants: List[str],
    ):
        """Start a raid."""
        mob: Character = raidhandler.mob
        log_info = (
            f"In: {interaction.guild_id} | Part: {len(participants)} | Lv. {mob.level}"
        )
        sti = time.time()

        mob_level_org = mob.level
        p_cache = {}
        health_point = {}
        username = {}
        player_damage_dealt = {}
        world = await self.get_world(interaction.guild)

        for user_id in participants:
            user: discord.User = self.bot.get_user(int(user_id))
            if not user:
                log.error(f"User not found: {user_id}")
                self.char_raid_lock.pop(int(user_id), None)
            else:
                member = interaction.guild.get_member(user.id)
                if not isinstance(member, discord.Member):
                    log.error(f"Member not found: {user_id}")
                    self.char_raid_lock.pop(int(user_id), None)
                else:
                    username[user_id] = member.display_name.split()[0][:10]
                    player: Character = await self.get_player(user)
                    p_cache[user_id] = player
                    health_point[user_id] = int(player.health)
                    player_damage_dealt[user_id] = []

        p_cache["mob"] = mob
        if raidhandler.is_elite:
            monster_health = FIBONACCI[int(mob.level / 10) + 1] + mob.health
        else:
            monster_health = FIBONACCI[int(mob.level / 10)] + mob.health
        m_health = monster_health
        parts = {
            k: v
            for k, v in sorted(
                p_cache.items(), key=lambda item: item[1].agility, reverse=True
            )
        }

        combat_log = ""
        combat_finished = False
        killer = None
        round_cnt = 0

        mob_agility = mob.agility

        while not combat_finished:
            if sum(health_point.values()) <= 0:
                combat_log += f"**{raidhandler.mob_name}** 擊敗了所有的冒險者！\n"
                break

            round_cnt += 1
            combat_log += f"--- Round {round_cnt}" + "-" * 20 + "\n"
            for user_id in parts:
                if monster_health <= 0:
                    break
                if user_id != "mob":
                    berserker = False
                    wizard = False
                    rogue = False
                    bishop = False
                    paladin = False
                    if health_point[user_id] <= 0:
                        continue
                    health_perc = health_point[user_id] / parts[user_id].health
                    if parts[user_id].agility / mob_agility <= random.random():
                        if parts[user_id].job == "bishop":
                            pass
                        # rogue
                        elif parts[user_id].job == "rogue" and random.random() <= max(
                            0.5, (0.3 + 1000 / (parts[user_id].agility + 1000))
                        ):
                            pass
                        elif parts[user_id].job == "berserker" and random.random() <= (
                            0.3 + ((1 - health_perc) * 0.5)
                        ):
                            berserker = True
                        else:
                            combat_log += f"{username[user_id]} 的攻擊沒有命中！\n"
                            continue
                    crit_ratio = (
                        (1.8 if parts[user_id].job == "rogue" else 1.5)
                        if random.random() * 100 < parts[user_id].critical_chance
                        else 1
                    )

                    damage_dealt = max(
                        int((parts[user_id].damage * crit_ratio) - mob.tenacity), 0
                    )
                    # rogue
                    if parts[user_id].job == "rogue" and random.random() <= 0.3:
                        # crit_ratio = 1.5
                        # damage_dealt = int(
                        #     parts[user_id].damage
                        #     * crit_ratio
                        #     * parts[user_id].level
                        #     / mob.level
                        # )
                        damage_dealt = int(
                            (damage_dealt / 3.8) + (m_health - monster_health) * 0.01
                        )
                        att_cnt = int(
                            self.fib_index(random.random() * parts[user_id].dexterity)
                        )
                        damage_dealt *= att_cnt
                        rogue = True

                    # berserker
                    elif berserker or (
                        parts[user_id].job == "berserker"
                        and random.random() <= (0.3 + ((1 - health_perc) * 0.5))
                        and damage_dealt != 0
                    ):
                        damage_dealt = parts[user_id].high_damage
                        damage_dealt *= 5.28 * (1 - health_perc)
                        damage_dealt *= 2.69
                        damage_dealt = int(damage_dealt)
                        health_point[user_id] = max(int(health_point[user_id] / 2), 1)
                        berserker = True

                    # wizard
                    elif (
                        parts[user_id].job == "wizard"
                        and random.random() <= 0.5
                        and damage_dealt != 0
                    ):
                        damage_dealt = int(damage_dealt * 3.14)
                        damage_dealt += max(int(monster_health * 0.08), 1)
                        wizard = True

                    # paladin
                    # elif (
                    #     parts[user_id].job == "paladin" and random.random() <= 0.3
                    # ) or paladin:
                    #     damage_dealt = int((m_health - monster_health) * 0.10)
                    #     paladin = True

                    # bishop
                    elif parts[user_id].job == "bishop":
                        damage_dealt = 1
                        bishop = True
                    else:
                        pass
                    monster_health -= damage_dealt
                    player_damage_dealt[user_id].append(damage_dealt)

                    if damage_dealt == 0:
                        combat_log += f"{username[user_id]} 的攻擊沒有任何效果...\n"
                    elif rogue:
                        # combat_log += f"{username[user_id]} 從陰影中現身，突襲了{raidhandler.mob_name}，造成{damage_dealt:,}點致命傷害！\n"
                        combat_log += (
                            f"{username[user_id]} 偷襲了{raidhandler.mob_name}，攻擊了{att_cnt}下後，總共造成{damage_dealt:,}點傷害！\n"
                        )
                    elif berserker:
                        combat_log += (
                            f"{username[user_id]} 捨命狂擊，消耗自身生命對{raidhandler.mob_name}造成{damage_dealt:,}點傷害！\n"
                        )
                    elif wizard:
                        combat_log += (
                            f"{username[user_id]} 感受到了元素的波動，對{raidhandler.mob_name}造成{damage_dealt:,}點傷害！\n"
                        )
                    elif paladin:
                        combat_log += (
                            f"{username[user_id]} 對{raidhandler.mob_name}進行制裁，造成{damage_dealt:,}點傷害！\n"
                        )
                    elif bishop:
                        if random.random() < 0.2 + parts[user_id].remain_stats / 200:
                            if random.random() < 0.01:
                                combat_log += f"隨著{username[user_id]}的虔誠禱告，遠方響起了號角的聲響。雲隙間閃爍著光芒，降下了神明的怒火。\n造成了{monster_health}點審判傷害。\n"
                                player_damage_dealt[user_id].append(monster_health - 1)
                                monster_health = 0
                                killer = user_id
                                break

                            heal_amount = (
                                int(
                                    parts[user_id].wisdom
                                    * parts[user_id].level
                                    / len(
                                        [k for k, v in health_point.items() if v != 0]
                                    )
                                    / 5
                                )
                                - 1
                            )
                            player_damage_dealt[user_id].append(int(heal_amount / 2))
                            for k, v in health_point.items():
                                if v != 0:
                                    health_point[k] += min(
                                        heal_amount, parts[k].health - v
                                    )
                            combat_log += (
                                f"{username[user_id]} 的祈禱觸發了神蹟，為現場隊友回復{heal_amount:,}生命值。\n"
                            )

                        else:
                            combat_log += f"{username[user_id]} 拼命的禱告，然而並沒有得到回應...\n"
                            player_damage_dealt[user_id].append(-1)
                    elif crit_ratio != 1:
                        combat_log += (
                            f"{username[user_id]} 瞄準了弱點，造成了{damage_dealt:,}點爆擊傷害！\n"
                        )
                    elif not parts[user_id].damage_type:
                        combat_log += f"{username[user_id]} 造成了{damage_dealt:,}點魔法傷害！\n"
                    else:
                        combat_log += f"{username[user_id]} 造成了{damage_dealt:,}點傷害！\n"
                    if monster_health <= 0:
                        killer = user_id
                        break
                else:
                    combat_log += f"*** {raidhandler.mob_name}即將對冒險者發起攻擊！\n"
                    for target_id in parts.keys():
                        paladin = False
                        berserker = False
                        if monster_health <= 0:
                            continue
                        if target_id == "mob":
                            continue
                        if health_point[target_id] <= 0:
                            continue
                        if not parts[target_id].damage_type and (
                            min(mob.agility / parts[target_id].agility, 0.75)
                            <= random.random()
                        ):
                            combat_log += f"{username[target_id]}躲避了攻擊！\n"
                            continue
                        elif (
                            mob.agility / parts[target_id].agility
                        ) <= random.random():  # and round_cnt < 6:
                            combat_log += f"{username[target_id]}躲避了攻擊！\n"
                            continue
                        # rogue
                        if parts[target_id].job == "rogue" and random.random() <= max(
                            0.5, (0.3 + 1000 / (parts[user_id].agility + 1000))
                        ):
                            combat_log += f"{username[target_id]}沉入陰影，躲避了攻擊！\n"
                            continue
                        if parts[target_id].job == "bishop" and random.random() < min(
                            0.2 + parts[target_id].remain_stats / 500, 0.8
                        ):
                            combat_log += f"一股神秘力量保護了{username[target_id]}免於受到傷害。\n"
                            continue
                        crit_ratio = (
                            1.5 if random.random() * 100 < mob.critical_chance else 1
                        )
                        damage_dealt = max(
                            int((mob.damage * crit_ratio) - parts[target_id].tenacity),
                            0,
                        )
                        # paladin
                        if parts[target_id].job == "paladin":
                            paladin = True
                        # berserker
                        if (
                            parts[target_id].job == "berserker"
                            and damage_dealt != 0
                            and random.random() <= 0.8
                        ):
                            if (
                                health_point[target_id] != 1
                                and damage_dealt > health_point[target_id]
                            ):
                                damage_dealt = health_point[target_id] - 1
                                berserker = True
                            else:
                                damage_dealt = int(damage_dealt * 2.5)

                        health_point[target_id] -= min(
                            damage_dealt, health_point[target_id]
                        )
                        if damage_dealt == 0:
                            combat_log += f"{username[target_id]}無視了攻擊的傷害！\n"
                        elif paladin:
                            thornmail = int(damage_dealt * 0.27) + int(
                                parts[target_id].constitution
                            )
                            damage_deflect = int(
                                min(thornmail * 2.4, health_point[target_id])
                            )
                            health_point[target_id] -= min(
                                damage_deflect, health_point[target_id]
                            )
                            combat_log += (
                                f"{username[target_id]} 抵擋了{raidhandler.mob_name}的攻擊，承受了{damage_deflect+damage_dealt:,}的傷害！\n"
                            )

                            if random.random() < 0.7:
                                monster_health -= min(thornmail, monster_health)
                                combat_log += f"{username[target_id]}使出盾擊！對{raidhandler.mob_name}造成了{thornmail:,}點相應傷害！\n"
                                player_damage_dealt[target_id].append(thornmail)
                        elif berserker:
                            combat_log += f"{username[target_id]} 受到了致命傷害，但是他忍住了！\n"
                        elif crit_ratio != 1:
                            combat_log += (
                                f"{username[target_id]} 被抓住弱點，受到了{damage_dealt:,}點爆擊傷害！\n"
                            )
                        elif not mob.damage_type:
                            combat_log += (
                                f"{username[target_id]} 受到了{damage_dealt:,}點魔法傷害！\n"
                            )
                        else:
                            combat_log += (
                                f"{username[target_id]} 受到了{damage_dealt:,}點傷害！\n"
                            )
                        if health_point[target_id] <= 0:
                            combat_log += f"{username[target_id]} 已死亡！\n"
                        if monster_health <= 0:
                            killer = target_id
                            break

            if monster_health <= 0:
                combat_log += f"{raidhandler.mob_name} 已死亡！\n"
                combat_finished = True

            else:
                mob.str_mod += 0.8 * round_cnt
                mob.dex_mod += 0.4 * round_cnt
                mob.wis_mod += 0.8 * round_cnt
                mob.con_mod += 0.6 * round_cnt

        monster_health = max(monster_health, 0)

        total_dmg_dealt = sum([sum(v) for v in player_damage_dealt.values()])

        player_damage_dealt = {
            k: v for k, v in player_damage_dealt.items() if k != "mob" and sum(v) > 0
        }
        player_damage_dealt = dict(
            list(
                dict(
                    sorted(
                        player_damage_dealt.items(),
                        key=lambda x: sum(x[1]),
                        reverse=True,
                    )
                ).items()
            )[:10]
        )
        combat_result = ""

        if sum(health_point.values()) <= 0:
            raid_result = False
            result = discord.Embed(
                title=f"{world.name} | 副本結算",
                color=world.colour,
            )
            if len(player_damage_dealt) > 0:
                result.add_field(
                    name=f"• 總傷害輸出: {total_dmg_dealt:,}",
                    value="\n".join(
                        [
                            f"{self.job[parts[k].job].name} **{username[k]}**"
                            for k, v in player_damage_dealt.items()
                        ]
                    ),
                    inline=True,
                )
                result.add_field(
                    name="\a",
                    value="\n".join(
                        [f"{sum(v):,}" for k, v in player_damage_dealt.items()]
                    ),
                    inline=True,
                )
            result.add_field(
                name="所有的冒險者都被擊敗了！",
                value=f"```st\n怪物剩餘血量: {monster_health:,}/{m_health:,}\n```",
                inline=False,
            )

        else:
            raid_result = True
            world.killed_mobs += 1
            player_result = ""
            world_result = ""
            total_exp = int(
                m_health
                # * max(len(parts) * 0.8, 1)
                * EXP_MULTIPLIER
            )
            guild_bonus = 1 + interaction.guild.premium_tier * 0.05
            base_exp = max(int(total_exp * 0.6), 1)
            part_exp = total_exp - base_exp
            base_exp *= guild_bonus
            part_exp = int(part_exp / len(parts))

            for user_id in parts.keys():
                if user_id == "mob":
                    continue
                player: Character = parts[user_id]
                player.chest += 1
                player.total_damage += sum(player_damage_dealt.get(user_id, [0]))
                player.max_damage = max(
                    player.max_damage,
                    max(player_damage_dealt.get(user_id, [0]), default=0),
                )
                exp_gain = int(base_exp * (100 + player.luck) / 100) + max(
                    int(
                        part_exp
                        * sum(player_damage_dealt.get(user_id, [0]))
                        / total_dmg_dealt
                    ),
                    1,
                )
                if user_id == killer:
                    exp_gain = int(exp_gain + total_exp * 0.08)
                    player.add_exp(exp_gain)
                    if player.check_levelup():
                        player_result += (
                            f"**{username[user_id]}**"
                            f" 擊殺了**{raidhandler.mob_name}**，等級獲得提升！\n"
                        )
                        combat_result += (
                            f"{username[user_id]} 擊殺了 {raidhandler.mob_name}，等級獲得提升！\n"
                        )
                    else:
                        player_result += (
                            f"**{username[user_id]}**"
                            f" 擊殺了**{raidhandler.mob_name}**，獲得了{exp_gain:,}點經驗值！\n"
                        )
                        combat_result += (
                            f"{username[user_id]} 擊殺了"
                            f" {raidhandler.mob_name}，獲得了{exp_gain:,}點經驗值！\n"
                        )
                else:
                    player.add_exp(exp_gain)
                    if player.check_levelup():
                        combat_result += f"{username[user_id]} 等級提升！\n"
                    else:
                        combat_result += f"{username[user_id]} 獲得了{exp_gain:,}點經驗值！\n"
                player.killed_mobs += 1

                if random.random() <= 0.04 and mob.level >= 45:
                    player.soulshard += 1

            world_exp = int(mob.exp_required(mob_level_org) * 0.1)
            world.add_exp(world_exp)
            if world.check_levelup():
                world_result += f"{world.name} 獲得經驗後等級提升！\n"
            else:
                world_result += f"{world.name} 獲得了{world_exp:,}點經驗值！\n"
            result = discord.Embed(
                title=f"{world.name} | 副本結算", description=None, color=world.colour
            )
            if len(player_damage_dealt) > 0:
                result.add_field(
                    name=f"• 傷害輸出: {total_dmg_dealt:,}/{m_health:,}",
                    value="\n".join(
                        [
                            f"{self.job[parts[k].job].name} **{username[k]}**"
                            for k, v in player_damage_dealt.items()
                        ]
                    ),
                    inline=True,
                )
                result.add_field(
                    name="\a",
                    value="\n".join(
                        [f"{sum(v):,}" for k, v in player_damage_dealt.items()]
                    ),
                    inline=True,
                )
            if len(player_result):
                result.add_field(name="• 玩家", value=player_result, inline=False)
            if raidhandler.mob_drop:
                user_id = random.choices(
                    population=[
                        v
                        for v in health_point.keys()
                        if v != "mob" and health_point[v] > 0
                    ],
                    weights=[
                        parts[v].petty
                        for v in health_point.keys()
                        if v != "mob" and health_point[v] > 0
                    ],
                )[0]
                for v in health_point.keys():
                    if v == "mob":
                        continue
                    if v == user_id:
                        continue
                    if health_point[v] <= 0:
                        continue
                    parts[v].petty += 1
                parts[user_id].petty = 0

                user = self.bot.get_user(int(user_id))
                item = self.create_item(self.item[raidhandler.mob_drop], mob_level_org)
                item_id = await self.give_item(user, item)
                if item_id:
                    item_str = (
                        f"**{username[user_id]}** 獲得了 **{item.name}**！\n代碼: {item_id}"
                    )
                else:
                    item_str = f"**{username[user_id]}** 的背包已滿，**{item.name}**丟失了！"
                result.add_field(name="• 掉落獎勵", value=item_str, inline=False)

            result.add_field(name="• 世界", value=world_result, inline=False)

        world.raid_result(raid_result)
        result.set_author(name=f"Lv. {mob_level_org} | {raidhandler.mob_name}")
        self.stamp_footer(result)

        combat_log = combat_result + "\n" + combat_log

        log.info(
            f"Round: {round_cnt:02d} ({time.time()-sti:.4f}s) | "
            + log_info
            + " | Drop:"
            f" { '-' if not raid_result else 'Y' if raidhandler.mob_drop else 'N' }"
        )

        await interaction.followup.send(embed=result)
        await interaction.followup.send(
            file=discord.File(io.BytesIO(combat_log.encode()), filename="combat.log")
        )

        for user_id in parts.keys():
            if user_id == "mob":
                continue
            user = self.bot.get_user(int(user_id))

            # should be better than full update
            player = await self.get_player(user)
            player.petty = parts[user_id].petty
            player.chest = parts[user_id].chest
            player.total_damage = parts[user_id].total_damage
            player.max_damage = parts[user_id].max_damage
            player.killed_mobs = parts[user_id].killed_mobs
            player.soulshard = parts[user_id].soulshard
            player.level = parts[user_id].level
            player.exp = parts[user_id].exp
            player.remain_stats = parts[user_id].remain_stats
            await self.set_player(user, player)

            # await self.set_player(user, parts[user_id])
            self.char_raid_lock.pop(int(user_id), None)
        world.last_seen = int(time.time())
        await self.set_world(interaction.guild, world)
