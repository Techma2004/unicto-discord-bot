from discord.ext import commands


class GeneralCommands(commands.Cog):
    """General NOVA commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        """Check whether NOVA is online."""
        await ctx.send(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`")


async def setup(bot):
    await bot.add_cog(GeneralCommands(bot))
