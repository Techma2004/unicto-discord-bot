import discord
from discord import app_commands
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
                "🤖 Please give me something to work with."
            )
            return

        await handler(
            ctx.message,
            prompt.strip(),
        )

    @app_commands.command(
        name="ask",
        description="Ask NOVA anything."
    )
    @app_commands.describe(
        message="Your question or message for NOVA"
    )
    async def slash_ask(
        self,
        interaction: discord.Interaction,
        message: str,
    ):
        """Ask NOVA through a Discord slash command."""

        handler = getattr(
            self.bot,
            "nova_ai_handler",
            None,
        )

        if not handler:
            await interaction.response.send_message(
                "⚠️ NOVA's AI system is currently unavailable."
            )
            return

        await interaction.response.defer()

        await handler(
            interaction,
            message.strip(),
        )


async def setup(bot):
    await bot.add_cog(AICommands(bot))
