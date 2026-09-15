
from discord.ext import commands

from app.services.project_memory import project_memory
from app.services.projects import project_service


class MemoryCommands(commands.Cog):
    """Commands for managing shared project memory."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="memory", invoke_without_command=True)
    async def memory(self, ctx):
        """Manage shared project memory."""

        await ctx.send(
            "🧠 **Memory commands**\n"
            "`!memory add <project> <title> | <content>`\n"
            "`!memory list <project>`\n"
            "`!memory delete <project> <memory_id>`"
        )

    @memory.command(name="add")
    async def memory_add(
        self,
        ctx,
        project_name,
        *,
        memory_data,
    ):
        """Add a memory to a project."""

        if "|" not in memory_data:
            await ctx.send(
                "❌ Please provide both a title and content.\n"
                "Example:\n"
                "`!memory add TestProject API Setup | "
                "Gemini API is connected successfully.`"
            )
            return

        title, content = memory_data.split(
            "|",
            1,
        )

        title = title.strip()
        content = content.strip()

        if not title or not content:
            await ctx.send(
                "❌ Both the memory title and content are required."
            )
            return

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if project.owner_discord_user_id != ctx.author.id:
            await ctx.send(
                "⛔ Only the project owner can add project memory."
            )
            return

        note = await project_memory.create_note(
            project_id=project.id,
            title=title,
            content=content,
            created_by_discord_user_id=ctx.author.id,
        )

        await ctx.send(
            f"🧠 Memory saved to **{project.name}**.\n"
            f"📌 **{note.title}**\n"
            f"🆔 Memory ID: `{note.id}`"
        )

    @memory.command(name="list")
    async def memory_list(
        self,
        ctx,
        project_name,
    ):
        """List project memories."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        notes = await project_memory.get_notes(
            project.id
        )

        if not notes:
            await ctx.send(
                f"📭 **{project.name}** has no saved memories."
            )
            return

        lines = [
            f"🧠 **Project Memory — {project.name}**"
        ]

        for note in notes:
            lines.append(
                f"• `{note.id}` — **{note.title}**\n"
                f"  {note.content}"
            )

        await ctx.send(
            "\n".join(lines)
        )

    @memory.command(name="delete")
    async def memory_delete(
        self,
        ctx,
        project_name,
        memory_id: int,
    ):
        """Delete a project memory."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if project.owner_discord_user_id != ctx.author.id:
            await ctx.send(
                "⛔ Only the project owner can delete project memory."
            )
            return

        deleted = await project_memory.delete_note(
            project.id,
            memory_id,
        )

        if not deleted:
            await ctx.send(
                f"❌ Memory `{memory_id}` was not found."
            )
            return

        await ctx.send(
            f"🗑️ Memory `{memory_id}` has been deleted "
            f"from **{project.name}**."
        )


async def setup(bot):
    await bot.add_cog(MemoryCommands(bot))
