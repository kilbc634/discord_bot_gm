from setting import *
import discord
from discord import option
from discord.ext import tasks
import asyncio
from utils import jenkinsContent

intents = discord.Intents.default()
intents.members = True

bot = discord.Bot(intents=intents)
guild_id = 557482649279528990
channel_id = 643265881996132362


@bot.slash_command(name='game-server', guild_ids=[guild_id])
@option('switch', description="啟動(up) / 停止(down)", choices=['up', 'down'])
async def game_server_switch(ctx: discord.ApplicationContext, switch: str):
    """用於 啟動/停止 當前正在遊玩的伺服器"""
    if switch == 'up':
        await ctx.respond("啟動伺服器中，請稍後....")
        jenkinsContent.post_job_start()
    elif switch == 'down':
        await ctx.respond("即將停止伺服器....")
        jenkinsContent.post_job_stop()


@bot.slash_command(name='ping', guild_ids=[guild_id])
async def ping(ctx: discord.ApplicationContext):
    """test123の乒乒碰碰 e04"""
    await ctx.respond("pong !!")


# 存儲正在運行的背景任務
task_mapping = {}
# 背景任務，預設每 5 分鐘執行一次
@tasks.loop(seconds= 5 * 60)
async def stop_server_when_player_inactive():
    is_inactive = jenkinsContent.check_player_inactive()
    if is_inactive == True:
        jenkinsContent.post_job_stop()
        channel = bot.get_channel(channel_id)
        await channel.send("長時間無人在線，將自動暫停伺服器....")


@bot.event
async def on_ready():
    print('Ready!')

    await asyncio.sleep(10)
    task = stop_server_when_player_inactive.start()
    task_mapping['stop_server_when_player_inactive'] = task
    print("Start background task: stop_server_when_player_inactive")


if __name__ == '__main__':
    bot.run(DISCORD_BOT_TOKEN)
