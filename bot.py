import discord

intents = discord.Intents.default()
intents.members = True

bot = discord.Bot(intents=intents)


@bot.slash_command(name='ping', guild_ids=[557482649279528990])
async def hello(ctx: discord.ApplicationContext):
    """test123の乒乒碰碰 e04"""
    await ctx.respond("pong !!")



bot.run("")
