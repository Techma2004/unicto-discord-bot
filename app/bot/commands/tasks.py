import discord
from discord.ext import commands

from app.services.projects import project_service
from app.services.project_members import project_member_service
from app.services.tasks import task_service


class TaskCommands(commands.Cog):
    """Commands for managing UNICTO project tasks."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="task", invoke_without_command=True)
    async def task(self, ctx):
        """Manage project tasks."""

        await ctx.send(
            "📋 **Task commands**\n"
            "`!task create <project> <title>`\n"
            "`!task list <project>`\n"
            "`!task info <project> <task_id>`\n"
            "`!task assign <project> <task_id> @user`\n"
            "`!task status <project> <task_id> <status>`\n"
            "`!task delete <project> <task_id>`"
        )

    @task.command(name="create")
    async def task_create(
        self,
        ctx,
        project_name,
        *,
        title,
    ):
        """Create a new task."""

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
                "⛔ Only the project owner can create tasks."
            )
            return

        task = await task_service.create_task(
            project_id=project.id,
            title=title,
            created_by_discord_user_id=ctx.author.id,
        )

        await ctx.send(
            f"✅ Task created in **{project.name}**.\n"
            f"📋 **{task.title}**\n"
            f"🆔 Task ID: `{task.id}`"
        )

    @task.command(name="list")
    async def task_list(
        self,
        ctx,
        project_name,
    ):
        """List tasks in a project."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        tasks = await task_service.get_tasks(
            project.id
        )

        if not tasks:
            await ctx.send(
                f"📭 **{project.name}** has no tasks yet."
            )
            return

        lines = [
            f"📋 **Tasks — {project.name}**"
        ]

        for task in tasks:
            lines.append(
                f"• `{task.id}` — **{task.title}** "
                f"[{task.status}] [{task.priority}]"
            )

        await ctx.send(
            "\n".join(lines)
        )

    @task.command(name="info")
    async def task_info(
        self,
        ctx,
        project_name,
        task_id: int,
    ):
        """Show information about a task."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        task = await task_service.get_task(
            project.id,
            task_id,
        )

        if not task:
            await ctx.send(
                f"❌ Task `{task_id}` was not found."
            )
            return

        assigned_to = (
            f"<@{task.assigned_discord_user_id}>"
            if task.assigned_discord_user_id
            else "Unassigned"
        )

        await ctx.send(
            f"📋 **{task.title}**\n"
            f"🆔 ID: `{task.id}`\n"
            f"📁 Project: **{project.name}**\n"
            f"📊 Status: `{task.status}`\n"
            f"⚡ Priority: `{task.priority}`\n"
            f"👤 Assigned: {assigned_to}\n"
            f"📝 {task.description or 'No description'}"
        )

    @task.command(name="assign")
    async def task_assign(
        self,
        ctx,
        project_name,
        task_id: int,
        member: discord.Member,
    ):
        """Assign a task to a project member."""

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
                "⛔ Only the project owner can assign tasks."
            )
            return

        task = await task_service.get_task(
            project.id,
            task_id,
        )

        if not task:
            await ctx.send(
                f"❌ Task `{task_id}` was not found."
            )
            return

        project_member = (
            await project_member_service.get_member(
                project.id,
                member.id,
            )
        )

        if not project_member:
            await ctx.send(
                f"❌ {member.mention} is not a member of "
                f"**{project.name}**."
            )
            return

        await task_service.assign_task(
            task.id,
            member.id,
        )

        await ctx.send(
            f"✅ Task **{task.title}** assigned to "
            f"{member.mention}."
        )

    @task.command(name="status")
    async def task_status(
        self,
        ctx,
        project_name,
        task_id: int,
        status,
    ):
        """Update a task's status."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        task = await task_service.get_task(
            project.id,
            task_id,
        )

        if not task:
            await ctx.send(
                f"❌ Task `{task_id}` was not found."
            )
            return

        valid_statuses = {
            "todo",
            "in_progress",
            "done",
        }

        if status not in valid_statuses:
            await ctx.send(
                "❌ Invalid status.\n"
                "Available statuses: "
                "`todo`, `in_progress`, `done`"
            )
            return

        updated = await task_service.update_status(
            task.id,
            status,
        )

        if not updated:
            await ctx.send(
                f"❌ Could not update task `{task_id}`."
            )
            return

        await ctx.send(
            f"✅ Task **{task.title}** is now "
            f"`{status}`."
        )

    @task.command(name="delete")
    async def task_delete(
        self,
        ctx,
        project_name,
        task_id: int,
    ):
        """Delete a task."""

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
                "⛔ Only the project owner can delete tasks."
            )
            return

        task = await task_service.get_task(
            project.id,
            task_id,
        )

        if not task:
            await ctx.send(
                f"❌ Task `{task_id}` was not found."
            )
            return

        deleted = await task_service.delete_task(
            task.id
        )

        if not deleted:
            await ctx.send(
                f"❌ Could not delete task `{task_id}`."
            )
            return

        await ctx.send(
            f"🗑️ Task **{task.title}** has been deleted."
        )


async def setup(bot):
    await bot.add_cog(TaskCommands(bot))
