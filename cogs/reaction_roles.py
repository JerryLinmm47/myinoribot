import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging

load_dotenv()
REACTION_MESSAGE_ID = int(os.getenv("REACTION_MESSAGE_ID", 0))

EMOJI_TO_ROLE = {
    "🍤": "いのりちゃん推",
    "🐬": "JGP Queen",
    "😺": "ミケちゃん推",
    "🐺": "ひかるちゃん推",
}

class ReactionRoleView(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if REACTION_MESSAGE_ID == 0:
            logging.warning("REACTION_MESSAGE_ID 未設定或為 0，請確認 .env 設定")

    @app_commands.command(name="send_reaction_message", description="傳送反應領取身分組的訊息")
    async def send_reaction_message(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ 你沒有權限使用這個指令。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            embed = discord.Embed(
                title="📌 身份組選擇",
                description="\n".join([f"{emoji} → {role}" for emoji, role in EMOJI_TO_ROLE.items()]),
                color=discord.Color.blue()
            )
            embed.set_footer(text="您好，我是いのり！歡迎來到金牌得主|メダリストdiscord討論區，請點選下方的表情符號領取身分組，也可以以/register來選擇身分組喔")

            message = await interaction.channel.send(embed=embed)

            for emoji in EMOJI_TO_ROLE:
                await message.add_reaction(emoji)

            await interaction.followup.send(
                f"✅ 已建立反應角色訊息，ID：`{message.id}`\n請將此 ID 複製貼到 `.env` 檔案的 `REACTION_MESSAGE_ID`。",
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"發送反應訊息失敗：{e}")
            await interaction.followup.send("❌ 發生錯誤，無法建立反應訊息。", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != REACTION_MESSAGE_ID or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        role_name = EMOJI_TO_ROLE.get(str(payload.emoji))
        if not guild or not role_name:
            return
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.add_roles(role)
                logging.info(f"已給予 {member.display_name} 身分組 {role_name}")
            except Exception as e:
                logging.error(f"無法給予身分組：{e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != REACTION_MESSAGE_ID or payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        role_name = EMOJI_TO_ROLE.get(str(payload.emoji))
        if not guild or not role_name:
            return
        role = discord.utils.get(guild.roles, name=role_name)
        member = guild.get_member(payload.user_id)
        if role and member:
            try:
                await member.remove_roles(role)
                logging.info(f"已移除 {member.display_name} 的身分組 {role_name}")
            except Exception as e:
                logging.error(f"無法移除身分組：{e}")

async def setup(bot):
    await bot.add_cog(ReactionRoleView(bot))