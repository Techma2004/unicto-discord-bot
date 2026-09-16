import os

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

        print("NOVA command extensions loaded.")

        # Slash-command synchronization is disabled by default.
        #
        # Set SYNC_COMMANDS=true in the environment when you
        # intentionally want NOVA to synchronize slash commands.
        sync_commands = os.getenv(
            "SYNC_COMMANDS",
            "false"
        ).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if sync_commands:
            try:
                print("Synchronizing slash commands with Discord...")
                synced = await self.tree.sync()
                print(
                    f"Slash commands synced successfully: {len(synced)} commands."
                )
            except discord.HTTPException as error:
                print(
                    "Slash-command synchronization failed: "
                    f"HTTP {error.status}."
                )
            except Exception as error:
                print(
                    "Slash-command synchronization failed: "
                    f"{type(error).__name__}: {error}"
                )
        else:
            print(
                "Slash-command synchronization skipped "
                "(SYNC_COMMANDS is disabled)."
            )
