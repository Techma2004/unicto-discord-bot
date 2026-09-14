from discord.ext import commands


class NOVAClient(commands.Bot):
    def __init__(self, request_queue):
        super().__init__(
            command_prefix="!",
            intents=self._build_intents(),
        )

        self.request_queue = request_queue

    @staticmethod
    def _build_intents():
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        return intents

    async def setup_hook(self):
        await self.request_queue.start()

        await self.load_extension(
            "app.bot.commands.general"
        )

        print("NOVA command extensions loaded.")
