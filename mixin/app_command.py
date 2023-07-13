import random

import discord
from discord import app_commands
from discord.app_commands import Choice
from loguru import logger as log

from maki.cogs.utils.view import Confirm

from ..lib import DEV, Guild, Item
from ..utils import board_view, info_view, stamp_footer


class DungeonAppCommandsMixin:
    # cog commands
    @app_commands.command(name="player", description="檢視角色資訊")
    async def playersheet(self, interaction: discord.Interaction) -> None:
        base: discord.ui.View = info_view(interaction.user)
        user_sheet = await self.user_sheet(interaction.user)
        try:
            await interaction.response.send_message(embed=user_sheet, view=base)
        except discord.errors.InteractionResponded:
            await interaction.edit_original_response(embed=user_sheet, view=base)
        except Exception as e:
            log.error(e)

        result = await base.wait()

        if base.value == "statsrecord":
            await self.statsrec_view(
                interaction, await self.user_statsrecord(interaction.user)
            )
        elif base.value == "equipments":
            await self.equipment_view(
                interaction, await self.user_equipments(interaction.user)
            )
        elif isinstance(result, bool):
            await interaction.edit_original_response(embed=user_sheet, view=None)

    @app_commands.command(name="guild", description="檢視公會資訊")
    async def guildinfo(self, interaction: discord.Interaction) -> None:
        e = await self.world_info(interaction.guild)
        await interaction.response.send_message(embed=e)

    # https://github.com/Rapptz/discord.py/issues/7823#issuecomment-1086830458
    # async def checkusercontext(
    #     self, interaction: discord.Interaction, user: discord.User
    # ) -> None:
    #     embed = await self.user_sheet(user)
    #     await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="character", description="設定遊戲相關資訊")
    @app_commands.choices(
        subject=[
            Choice(name="角色狀態", value="set_status"),
            Choice(name="遊戲顏色", value="set_colour"),
        ],
    )
    @app_commands.rename(subject="設定", content="內容")
    @app_commands.describe(
        subject="角色狀態會顯示在角色資訊，遊戲顏色為顯示框顏色",
        content="狀態可以直接輸入，顏色請輸入顏色代碼",
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
            player.status = content
            await self.set_user(interaction.user.id)
            return await interaction.response.send_message(
                embed=discord.Embed(
                    description="個人狀態已更改為: `{}`".format(content),
                    colour=discord.Colour.green(),
                ),
                ephemeral=True,
            )
        elif subject == "set_colour":
            try:
                colour = discord.Colour.from_str(content)
            except ValueError:
                return await interaction.response.send_message(
                    embed=discord.Embed(
                        description="顏色格式錯誤，請輸入色碼",
                        colour=discord.Colour.red(),
                    ),
                    ephemeral=True,
                )
            player.colour = colour
            await self.set_user(interaction.user.id)
            return await interaction.response.send_message(
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
    @app_commands.describe(
        subject="更改伺服器世界的名稱，狀態，以及專屬顏色",
        content="名稱與狀態請輸入文字，顏色請輸入色碼",
    )
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
        self, interaction: discord.Interaction, world: Guild, content: str
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
        self, interaction: discord.Interaction, world: Guild, content: str
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
        self, interaction: discord.Interaction, world: Guild, content: str
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
    @app_commands.describe(
        item_id="請輸入物品代碼，可以從/backpack 找到物品代碼", user="請選擇玩家"
    )
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
                embed=discord.Embed(
                    description="已取消強化裝備。", color=self.bot.color
                ),
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
                        f"{item_name}碰觸靈魂碎片時，閃耀出了新的光芒。"
                        f"\n獲得了{item.name} {self.int2Roman(item.reinforced)}。"
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
            embed=discord.Embed(
                description="確定要清除你的資料嗎?", color=self.bot.color
            ),
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
            stamp_footer(leaderboard_embed)
            leaderboard_embeds.append(leaderboard_embed)

        lb_view = board_view(interaction.user, leaderboard_embeds)
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
