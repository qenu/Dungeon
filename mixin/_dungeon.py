import asyncio
import io
import random
import time
from typing import List

from discord import Colour, Embed, File, Interaction, Member, User, app_commands
from discord.errors import NotFound
from discord.ext import commands
from loguru import logger as log

from ..lib import EXP_MULTIPLIER, FIBONACCI, InstanceHandler, Player
from ..utils import dungeon_view


class DungeonMixin:
    """Dungeon Instance Related Mixin."""

    @app_commands.command(name="dungeon", description="開啟副本")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 120, key=lambda i: i.guild.id)
    async def _dungeon_start(self, interaction: Interaction) -> None:
        """Start a raid."""
        if self.global_raid_lock:
            await interaction.response.send_message(
                embed=Embed(
                    title="錯誤訊息",
                    description="副本入口關閉中，請稍後再試",
                    colour=Colour.red(),
                )
            )
            return
        world = await self.get_world(interaction.guild)
        if interaction.guild_id in self.world_raid_lock.keys():
            e = Embed(
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

        raid = InstanceHandler(
            interaction, world.mob_level, random.choice(list(self.mob.values()))
        )

        self.world_raid_lock[interaction.guild_id] = [
            interaction.channel_id,
            int(time.time() + raid.preptime),
        ]  # LOCK THAT SHIT

        init_view = dungeon_view(self.bot, raid.preptime)
        embed = Embed(
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
                embed=Embed(
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
        self, interaction: Interaction, error: Exception
    ) -> None:
        """Handle raid command error."""
        if isinstance(error, commands.CheckFailure):
            await interaction.channel.send("CheckFailure")
        elif isinstance(error, commands.CommandOnCooldown):
            await interaction.channel.send("CommandOnCooldown")
        elif isinstance(error, app_commands.errors.CommandOnCooldown):
            await interaction.response.send_message(
                embed=Embed(
                    title="副本冷卻中！",
                    description=(
                        f"請稍後再試，大約<t:{int(time.time()+error.retry_after)}:R>"
                    ),
                    color=self.bot.color,
                ),
                ephemeral=True,
            )
        elif isinstance(error, NotFound):
            await interaction.channel.send("Discord 連結失敗。")
        else:
            await interaction.channel.send("Unknown error")
            log.error("Unknown error in raid command", exc_info=error)

    async def start_raid(
        self,
        interaction: Interaction,
        raidhandler: InstanceHandler,
        participants: List[str],
    ):
        """Start a raid."""
        mob: Player = raidhandler.mob
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
            user: User = self.bot.get_user(int(user_id))
            if not user:
                log.error(f"User not found: {user_id}")
                self.char_raid_lock.pop(int(user_id), None)
            else:
                member = interaction.guild.get_member(user.id)
                if not isinstance(member, Member):
                    log.error(f"Member not found: {user_id}")
                    self.char_raid_lock.pop(int(user_id), None)
                else:
                    username[user_id] = member.display_name.split()[0][:10]
                    player: Player = await self.get_player(user)
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
                            f"{username[user_id]} 偷襲了{raidhandler.mob_name}，"
                            f"攻擊了{att_cnt}下後，總共造成{damage_dealt:,}點傷害！\n"
                        )
                    elif berserker:
                        combat_log += (
                            f"{username[user_id]} 捨命狂擊，"
                            f"消耗自身生命對{raidhandler.mob_name}造成{damage_dealt:,}點傷害！\n"
                        )
                    elif wizard:
                        combat_log += (
                            f"{username[user_id]} 感受到了元素的波動，"
                            f"對{raidhandler.mob_name}造成{damage_dealt:,}點傷害！\n"
                        )
                    elif paladin:
                        combat_log += (
                            f"{username[user_id]} 對{raidhandler.mob_name}進行制裁，"
                            f"造成{damage_dealt:,}點傷害！\n"
                        )
                    elif bishop:
                        if random.random() < 0.2 + parts[user_id].remain_stats / 200:
                            if random.random() < 0.01:
                                combat_log += (
                                    f"隨著{username[user_id]}的虔誠禱告，"
                                    "遠方響起了號角的聲響。雲隙間閃爍著光芒，"
                                    "降下了神明的怒火。"
                                    f"\n造成了{monster_health}點審判傷害。\n"
                                )
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
                                f"{username[user_id]} 的祈禱觸發了神蹟，"
                                f"為現場隊友回復{heal_amount:,}生命值。\n"
                            )

                        else:
                            combat_log += f"{username[user_id]} 拼命的禱告，然而並沒有得到回應...\n"
                            player_damage_dealt[user_id].append(-1)
                    elif crit_ratio != 1:
                        combat_log += (
                            f"{username[user_id]} 瞄準了弱點，"
                            f"造成了{damage_dealt:,}點爆擊傷害！\n"
                        )
                    elif not parts[user_id].damage_type:
                        combat_log += (
                            f"{username[user_id]} 造成了{damage_dealt:,}點魔法傷害！\n"
                        )
                    else:
                        combat_log += (
                            f"{username[user_id]} 造成了{damage_dealt:,}點傷害！\n"
                        )
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
                            combat_log += (
                                f"{username[target_id]}沉入陰影，躲避了攻擊！\n"
                            )
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
                                f"{username[target_id]} 抵擋了{raidhandler.mob_name}的攻擊，"
                                f"承受了{damage_deflect+damage_dealt:,}的傷害！\n"
                            )

                            if random.random() < 0.7:
                                monster_health -= min(thornmail, monster_health)
                                combat_log += f"{username[target_id]}使出盾擊！對{raidhandler.mob_name}造成了{thornmail:,}點相應傷害！\n"
                                player_damage_dealt[target_id].append(thornmail)
                        elif berserker:
                            combat_log += f"{username[target_id]} 受到了致命傷害，但是他忍住了！\n"
                        elif crit_ratio != 1:
                            combat_log += (
                                f"{username[target_id]} 被抓住弱點，"
                                f"受到了{damage_dealt:,}點爆擊傷害！\n"
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
            result = Embed(
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
                player: Player = parts[user_id]
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
                            f"{username[user_id]} 擊殺了 {raidhandler.mob_name}，"
                            "等級獲得提升！\n"
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
                        combat_result += (
                            f"{username[user_id]} 獲得了{exp_gain:,}點經驗值！\n"
                        )
                player.killed_mobs += 1

                if random.random() <= 0.04 and mob.level >= 45:
                    player.soulshard += 1

            world_exp = int(mob.exp_required(mob_level_org) * 0.1)
            world.add_exp(world_exp)
            if world.check_levelup():
                world_result += f"{world.name} 獲得經驗後等級提升！\n"
            else:
                world_result += f"{world.name} 獲得了{world_exp:,}點經驗值！\n"
            result = Embed(
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
                        f"**{username[user_id]}** 獲得了 **{item.name}**！\n代碼:"
                        f" {item_id}"
                    )
                else:
                    item_str = (
                        f"**{username[user_id]}** 的背包已滿，**{item.name}**丟失了！"
                    )
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
            file=File(io.BytesIO(combat_log.encode()), filename="combat.log")
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
