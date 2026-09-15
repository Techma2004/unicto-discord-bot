from discord.ext import commands


class AICommands(commands.Cog):
    """AI commands for NOVA."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ask")
    async def ask(self, ctx, *, prompt=None):
        """Ask NOVA an AI question."""

        handler = getattr(
            self.bot,
            "nova_ai_handler",
            None,
        )

        if not handler:
            await ctx.send(
                "⚠️ NOVA's AI system is currently unavailable."
            )
            return

        if not prompt or not prompt.strip():
            await ctx.send(
                "🤖 Please give me something to work with.\n"
                "Example: `!ask explain Python functions`"
            )
            return

        await handler(
            ctx.message,
            prompt.strip(),
        )


async def setup(bot):
    await bot.add_cog(AICommands(bot))
