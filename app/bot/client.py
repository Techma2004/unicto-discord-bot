import discord
from discord.ext import commands


class NOVAClient(commands.Bot):
    """Custom Discord client for NOVA."""

    def __init__(self, request_queue, ai_handler=None):
        super().__init__(
            command_prefix="!",
            intents=self._build_intents(),
        )

        self.request_queue = request_queue
        self.nova_ai_handler = ai_handler

    @staticmethod
    def _build_intents():
        intents = discord.Intents.default()
        intents.message_content = True
        return intents

    async def setup_hook(self):
        # Start the NOVA request queue first.
        await self.request_queue.start()

        # Load command extensions.
        await self.load_extension(
            "app.bot.commands.general"
        )

        await self.load_extension(
            "app.bot.commands.projects"
        )

        await self.load_extension(
            "app.bot.commands.tasks"
        )

        await self.load_extension(
            "app.bot.commands.memory"
        )

        await self.load_extension(
            "app.bot.commands.ai"
        )

        # Load Discord event handlers.
        await self.load_extension(
            "app.bot.events"
        )

        # Sync slash commands with Discord.
        await self.tree.sync()

        print("NOVA command extensions loaded.")
        print("Slash commands synced.")
