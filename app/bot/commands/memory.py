from discord.ext import commands

from app.services.project_memory import project_memory
from app.services.projects import project_service
from app.services.permissions import permission_service


class MemoryCommands(commands.Cog):
    """Project memory commands for NOVA."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        name="memory",
        invoke_without_command=True,
    )
    async def memory(self, ctx):
        """Manage project memory."""

        if ctx.invoked_subcommand is None:
            await ctx.send(
                "🧠 **Memory Commands**\n"
                "`!memory add <project> <title> | <content>`\n"
                "`!memory list <project>`\n"
                "`!memory delete <project> <memory_id>`"
            )

    @memory.command(name="add")
    async def memory_add(
        self,
        ctx,
        project_name=None,
        *,
        details=None,
    ):
        """Add a memory to a project."""

        if not project_name or not details:
            await ctx.send(
                "❌ Usage:\n"
                "`!memory add <project> <title> | <content>`"
            )
            return

        if "|" not in details:
            await ctx.send(
                "❌ Please separate the memory title and "
                "content with `|`.\n"
                "Example:\n"
                "`!memory add NOVA Architecture | "
                "NOVA uses Gemini for AI responses.`"
            )
            return

        title, content = details.split("|", 1)

        title = title.strip()
        content = content.strip()

        if not title:
            await ctx.send(
                "❌ Memory title cannot be empty."
            )
            return

        if not content:
            await ctx.send(
                "❌ Memory content cannot be empty."
            )
            return

        project_name = project_name.strip()

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not permission_service.can_manage_memory(
            project,
            ctx.author,
        ):
            await ctx.send(
                "⛔ You do not have permission to add "
                "memory to this project."
            )
            return

        note = await project_memory.create_note(
            project_id=project.id,
            title=title,
            content=content,
            created_by_discord_user_id=ctx.author.id,
        )

        await ctx.send(
            f"🧠 Memory **#{note.id}** added to "
            f"**{project.name}**."
        )

    @memory.command(name="list")
    async def memory_list(
        self,
        ctx,
        *,
        project_name=None,
    ):
        """List project memories."""

        if not project_name:
            await ctx.send(
                "❌ Please provide a project name.\n"
                "Example: `!memory list NOVA`"
            )
            return

        project_name = project_name.strip()

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not permission_service.can_view_project(
            project,
            ctx.author,
        ):
            await ctx.send(
                "⛔ You do not have permission to view "
                "this project's memory."
            )
            return

        notes = await project_memory.get_notes(
            project.id
        )

        if not notes:
            await ctx.send(
                f"🧠 **{project.name}** has no saved "
                f"memories yet."
            )
            return

        lines = [
            f"🧠 **Memory — {project.name}**"
        ]

        for note in notes:
            content = note.content.strip()

            if len(content) > 500:
                content = content[:500] + "…"

            lines.append(
                f"\n**#{note.id} — {note.title}**\n"
                f"{content}"
            )

        await ctx.send("\n".join(lines))

    @memory.command(name="delete")
    async def memory_delete(
        self,
        ctx,
        project_name=None,
        memory_id=None,
    ):
        """Delete a project memory."""

        if not project_name or not memory_id:
            await ctx.send(
                "❌ Usage:\n"
                "`!memory delete <project> <memory_id>`"
            )
            return

        try:
            memory_id = int(memory_id)
        except ValueError:
            await ctx.send(
                "❌ Memory ID must be a number."
            )
            return

        project_name = project_name.strip()

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not permission_service.can_manage_memory(
            project,
            ctx.author,
        ):
            await ctx.send(
                "⛔ You do not have permission to delete "
                "memory from this project."
            )
            return

        deleted = await project_memory.delete_note(
            project.id,
            memory_id,
        )

        if not deleted:
            await ctx.send(
                f"⚠️ Memory `#{memory_id}` was not found "
                f"in **{project.name}**."
            )
            return

        await ctx.send(
            f"🗑️ Memory **#{memory_id}** deleted from "
            f"**{project.name}**."
        )


async def setup(bot):
    await bot.add_cog(MemoryCommands(bot))
