import os
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()

import discord
import asyncio
import json
import subprocess
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime

# 載入 .env 設定
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 50:
    raise ValueError("❌ 找不到有效的 DISCORD_TOKEN，請確認環境變數或 .env 是否正確")

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))
REGISTER_CHANNEL_ID = int(os.getenv("REGISTER_CHANNEL_ID"))
DEFAULT_ROLE_NAME = os.getenv("DEFAULT_ROLE_NAME")
ROLE_OPTIONS = [name.strip() for name in os.getenv("ROLE_OPTIONS").split(",")]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 自選身分組 UI 選單 ---

class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=name)
            for name in ROLE_OPTIONS
        ]
        super().__init__(
            placeholder="選擇你要加入的身份組（可多選）",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values
        guild = interaction.guild
        member = interaction.user
        roles_to_remove = [r for r in member.roles if r.name in ROLE_OPTIONS]
        await member.remove_roles(*roles_to_remove)
        roles_to_add = [discord.utils.get(guild.roles, name=name) for name in selected]
        roles_to_add = [r for r in roles_to_add if r is not None]
        await member.add_roles(*roles_to_add)
        await interaction.response.send_message(
            f"✅ 你的身份組已更新為：{', '.join(selected)}",
            ephemeral=True
        )

class RoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(RoleSelect())

# --- Slash 指令區 ---

@bot.tree.command(name="register", description="選擇或更改你的身份組")
async def register(interaction: discord.Interaction):
    if interaction.channel.id != REGISTER_CHANNEL_ID:
        await interaction.response.send_message(
            f"⚠️ 請到指定頻道 <#{REGISTER_CHANNEL_ID}> 使用 `/register`。",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="自選身份組",
        description="請從下方選單選擇你要加入的身份組：",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(
        embed=embed,
        view=RoleSelectView(),
        ephemeral=True
    )

@bot.tree.command(name="myroles", description="查看你目前的身份組")
async def myroles(interaction: discord.Interaction):
    user_roles = [r.name for r in interaction.user.roles if r.name in ROLE_OPTIONS]
    if user_roles:
        desc = f"🎭 你目前擁有的身份組：{', '.join(user_roles)}"
    else:
        desc = "你目前沒有任何自選身份組。"
    embed = discord.Embed(description=desc, color=discord.Color.green())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset_roles", description="幫某人移除所有自選身份組")
@app_commands.describe(member="你想清除身分組的對象")
async def reset_roles(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ 你沒有權限執行這個操作", ephemeral=True)
        return
    roles_to_remove = [r for r in member.roles if r.name in ROLE_OPTIONS]
    await member.remove_roles(*roles_to_remove)
    await interaction.response.send_message(
        f"✅ 已為 {member.mention} 移除所有自選身份組",
        ephemeral=True
    )

@bot.tree.command(name="say", description="讓機器人幫你說話")
@app_commands.describe(message="你想讓機器人說的內容")
async def say(interaction: discord.Interaction, message: str):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ 你沒有權限使用這個指令。", ephemeral=True)
        return
    await interaction.channel.send(message)
    await interaction.response.send_message("✅ 已送出訊息", ephemeral=True)

# --- 成員加入事件 ---

@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    default_role = discord.utils.get(guild.roles, name=DEFAULT_ROLE_NAME)
    if welcome_channel:
        embed = discord.Embed(
            title="🎉 歡迎加入！",
            description=f"你好我是ルクス東山FSC的いのり，今天很榮幸擔任您的嚮導，歡迎 {member.mention} 歡迎加入金牌得主|メダリストdiscord討論區！\n請到 <#{REGISTER_CHANNEL_ID}> 使用 `/register` 或是按表情符號選擇你的身份組。",
            color=discord.Color.gold()
        )
        await welcome_channel.send(embed=embed)
    if default_role:
        await member.add_roles(default_role)

# --- Twitter 抓取任務 ---

LAST_TWEET_IDS = {}

@tasks.loop(minutes=5)
async def fetch_twitter_updates():
    try:
        with open("twitter_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        accounts = config.get("twitter_accounts", {})
    except Exception as e:
        print(f"❌ 無法讀取 twitter_config.json：{e}")
        return

    for account, channel_id in accounts.items():
        command = f"snscrape --jsonl --max-results 1 twitter-user:{account}"
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 or not result.stdout:
                print(f"❌ 無法抓取 {account} 的推文")
                continue

            tweet_data = json.loads(result.stdout.strip().splitlines()[0])
            tweet_id = tweet_data["id"]
            tweet_url = tweet_data["url"]
            content = tweet_data.get("content", "")
            date = tweet_data.get("date", "")

            if LAST_TWEET_IDS.get(account) == tweet_id:
                continue

            LAST_TWEET_IDS[account] = tweet_id

            channel = bot.get_channel(int(channel_id))
            if channel:
                embed = discord.Embed(
                    title=f"🐤 新推文來自 @{account}",
                    description=content[:400] + ("..." if len(content) > 400 else ""),
                    url=tweet_url,
                    color=discord.Color.blue(),
                    timestamp=datetime.fromisoformat(date.replace("Z", "+00:00"))
                )
                embed.set_footer(text="Powered by snscrape")
                await channel.send(embed=embed)
        except Exception as e:
            print(f"❌ 抓取 {account} 推文錯誤：{e}")

# --- Bot 啟動事件 ---

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"✅ 指令同步完成，共 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"❌ 指令同步失敗：{e}")
    print(f"🤖 Bot 已上線：{bot.user.name}")
    fetch_twitter_updates.start()

# --- 啟動 Bot ---

async def main():
    await bot.load_extension("cogs.reaction_roles")
    await bot.start(DISCORD_TOKEN)

asyncio.run(main())