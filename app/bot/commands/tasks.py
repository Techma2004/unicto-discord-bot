import discord
from discord.ext import commands
from discord.ext.commands import Greedy

from app.services.projects import project_service
from app.services.project_members import project_member_service
from app.services.tasks import task_service
from app.services.permissions import permission_service


class TaskCommands(commands.Cog):
    """Commands for managing UNICTO project tasks."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="task", invoke_without_command=True)
    async def task(self, ctx):
        """Manage project tasks."""

        await ctx.send(
            "📋 **Task commands**\n"
            "`!task create <project> <title> [| description]`\n"
            "`!task list <project>`\n"
            "`!task info <project> <task_id>`\n"
            "`!task assign <project> <task_id> @user [@user ...]`\n"
            "`!task unassign <project> <task_id> @user [@user ...]`\n"
            "`!task status <project> <task_id> <status>`\n"
            "`!task delete <project> <task_id>`"
        )

    @task.command(name="create")
    async def task_create(
        self,
        ctx,
        project_name,
        *,
        task_data,
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

        if not await permission_service.can_manage_tasks(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to create "
                "tasks in this project."
            )
            return

        if "|" in task_data:
            title, description = task_data.split(
                "|",
                1,
            )
            title = title.strip()
            description = description.strip()
        else:
            title = task_data.strip()
            description = None

        if not title:
            await ctx.send(
                "❌ Task title cannot be empty."
            )
            return

        task, created, status = await task_service.create_task(
            project_id=project.id,
            title=title,
            description=description,
            created_by_discord_user_id=ctx.author.id,
        )

        if status == "invalid_priority":
            await ctx.send(
                "❌ Invalid task priority."
            )
            return

        if not created:
            await ctx.send(
                "❌ The task could not be created."
            )
            return

        await ctx.send(
            f"✅ Task created in **{project.name}**.\n"
            f"📋 **{task.title}**\n"
            f"🆔 Task ID: `{task.id}`\n"
            f"📊 Status: `{task.status}`\n"
            f"⚡ Priority: `{task.priority}`"
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
            assignee_ids = await task_service.get_assignees(
                project.id,
                task.id,
            )

            if assignee_ids:
                assignees = ", ".join(
                    f"<@{user_id}>"
                    for user_id in assignee_ids
                )
            else:
                assignees = "Unassigned"

            lines.append(
                f"• `{task.id}` — **{task.title}** "
                f"[{task.status}] [{task.priority}]\n"
                f"  👥 {assignees}"
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

        assignee_ids = await task_service.get_assignees(
            project.id,
            task.id,
        )

        if assignee_ids:
            assigned_to = "\n".join(
                f"• <@{user_id}>"
                for user_id in assignee_ids
            )
        else:
            assigned_to = "Unassigned"

        await ctx.send(
            f"📋 **{task.title}**\n"
            f"🆔 ID: `{task.id}`\n"
            f"📁 Project: **{project.name}**\n"
            f"📊 Status: `{task.status}`\n"
            f"⚡ Priority: `{task.priority}`\n"
            f"👥 **Assigned:**\n{assigned_to}\n"
            f"📝 {task.description or 'No description'}"
        )

    @task.command(name="assign")
    async def task_assign(
        self,
        ctx,
        project_name,
        task_id: int,
        members: Greedy[discord.Member],
    ):
        """Assign one or more project members to a task."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not await permission_service.can_manage_tasks(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to assign "
                "tasks in this project."
            )
            return

        if not members:
            await ctx.send(
                "❌ Please mention at least one member.\n"
                "Example: "
                "`!task assign Nova_test 1 @Edima @Developer`"
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

        assigned = []
        already_assigned = []
        not_members = []

        for member in members:
            project_member = (
                await project_member_service.get_member(
                    project.id,
                    member.id,
                )
            )

            if not project_member:
                not_members.append(member)
                continue

            _, created, result_status = (
                await task_service.assign_member(
                    project.id,
                    task.id,
                    member.id,
                )
            )

            if result_status == "already_assigned":
                already_assigned.append(member)
            elif created:
                assigned.append(member)

        lines = []

        if assigned:
            mentions = ", ".join(
                member.mention
                for member in assigned
            )
            lines.append(
                f"✅ Assigned **{task.title}** to {mentions}."
            )

        if already_assigned:
            mentions = ", ".join(
                member.mention
                for member in already_assigned
            )
            lines.append(
                f"⚠️ Already assigned: {mentions}."
            )

        if not_members:
            mentions = ", ".join(
                member.mention
                for member in not_members
            )
            lines.append(
                f"❌ Not project members: {mentions}."
            )

        await ctx.send(
            "\n".join(lines)
            if lines
            else "❌ No assignments were made."
        )

    @task.command(name="unassign")
    async def task_unassign(
        self,
        ctx,
        project_name,
        task_id: int,
        members: Greedy[discord.Member],
    ):
        """Remove one or more members from a task."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not await permission_service.can_manage_tasks(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to unassign "
                "task members."
            )
            return

        if not members:
            await ctx.send(
                "❌ Please mention at least one member."
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

        removed = []
        not_assigned = []

        for member in members:
            success, result_status = (
                await task_service.remove_member(
                    project.id,
                    task.id,
                    member.id,
                )
            )

            if success:
                removed.append(member)
            elif result_status == "not_assigned":
                not_assigned.append(member)

        lines = []

        if removed:
            mentions = ", ".join(
                member.mention
                for member in removed
            )
            lines.append(
                f"✅ Removed {mentions} from **{task.title}**."
            )

        if not_assigned:
            mentions = ", ".join(
                member.mention
                for member in not_assigned
            )
            lines.append(
                f"⚠️ Not assigned: {mentions}."
            )

        await ctx.send(
            "\n".join(lines)
            if lines
            else "❌ No assignments were removed."
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

        if not await permission_service.can_manage_tasks(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to update "
                "tasks in this project."
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

        updated_task, updated, result_status = (
            await task_service.update_status(
                project.id,
                task.id,
                status,
            )
        )

        if result_status == "invalid_status":
            await ctx.send(
                "❌ Invalid status.\n"
                "Available statuses: "
                "`todo`, `in_progress`, `done`"
            )
            return

        if not updated:
            await ctx.send(
                f"❌ Could not update task `{task_id}`."
            )
            return

        await ctx.send(
            f"✅ Task **{updated_task.title}** is now "
            f"`{updated_task.status}`."
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

        if not await permission_service.can_manage_tasks(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to delete "
                "tasks in this project."
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
            project.id,
            task.id,
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
