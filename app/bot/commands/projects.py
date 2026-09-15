import discord
from discord.ext import commands

from app.services.projects import project_service
from app.services.project_members import project_member_service
from app.services.team import team_service
from app.services.permissions import permission_service


class ProjectCommands(commands.Cog):
    """Commands for managing UNICTO projects."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="project", invoke_without_command=True)
    async def project(self, ctx):
        """Manage UNICTO projects."""

        await ctx.send(
            "📁 **Project commands**\n"
            "`!project create <name> [description]`\n"
            "`!project list`\n"
            "`!project info <name>`\n"
            "`!project delete <name>`\n"
            "`!project member list <name>`\n"
            "`!project member add <name> @user <role>`\n"
            "`!project member remove <name> @user`"
        )

    @project.command(name="create")
    async def project_create(
        self,
        ctx,
        name,
        *,
        description=None,
    ):
        """Create a project."""

        project, created = await project_service.create_project(
            name=name,
            description=description,
            owner_discord_user_id=ctx.author.id,
        )

        if not created:
            await ctx.send(
                f"⚠️ Project `{name}` already exists."
            )
            return

        await team_service.register_member(
            ctx.author
        )

        await ctx.send(
            f"✅ Project **{project.name}** created.\n"
            f"👑 Owner: {ctx.author.mention}"
        )

    @project.command(name="list")
    async def project_list(self, ctx):
        """List all projects."""

        projects = await project_service.get_all_projects()

        if not projects:
            await ctx.send(
                "📭 No projects have been created yet."
            )
            return

        lines = [
            "📁 **UNICTO Projects**"
        ]

        for project in projects:
            lines.append(
                f"• **{project.name}** — "
                f"{project.description or 'No description'}"
            )

        await ctx.send(
            "\n".join(lines)
        )

    @project.command(name="info")
    async def project_info(
        self,
        ctx,
        name,
    ):
        """Show project information."""

        project = await project_service.get_project(
            name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{name}` was not found."
            )
            return

        members = await project_member_service.get_members(
            project.id
        )

        await ctx.send(
            f"📁 **{project.name}**\n"
            f"📝 {project.description or 'No description'}\n"
            f"👥 Members: **{len(members)}**\n"
            f"👑 Owner ID: `{project.owner_discord_user_id}`"
        )

    @project.command(name="delete")
    async def project_delete(
        self,
        ctx,
        name,
    ):
        """Delete a project."""

        project = await project_service.get_project(
            name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{name}` was not found."
            )
            return

        if not await permission_service.can_manage_project(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to delete this project."
            )
            return

        deleted = await project_service.delete_project(
            name
        )

        if deleted:
            await ctx.send(
                f"🗑️ Project `{name}` has been deleted."
            )
        else:
            await ctx.send(
                f"❌ Could not delete project `{name}`."
            )

    @project.group(
        name="member",
        invoke_without_command=True,
    )
    async def project_member(self, ctx):
        """Manage project members."""

        await ctx.send(
            "👥 **Project member commands**\n"
            "`!project member list <project>`\n"
            "`!project member add <project> @user <role>`\n"
            "`!project member remove <project> @user`"
        )

    @project_member.command(name="list")
    async def member_list(
        self,
        ctx,
        project_name,
    ):
        """List project members."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        members = await project_member_service.get_members(
            project.id
        )

        if not members:
            await ctx.send(
                "📭 This project has no members."
            )
            return

        lines = [
            f"👥 **Members of {project.name}**"
        ]

        for member in members:
            lines.append(
                f"• <@{member.discord_user_id}> — "
                f"`{member.role}`"
            )

        await ctx.send(
            "\n".join(lines)
        )

    @project_member.command(name="add")
    async def member_add(
        self,
        ctx,
        project_name,
        member: discord.Member,
        role="member",
    ):
        """Add a member to a project."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not await permission_service.can_manage_members(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to add "
                "project members."
            )
            return

        role = role.lower()

        # Only the actual project owner can assign
        # the owner role.
        if (
            role == "owner"
            and not await permission_service.is_project_owner(
                project,
                ctx.author.id,
            )
        ):
            await ctx.send(
                "⛔ Only the project owner can assign "
                "the `owner` role."
            )
            return

        result = await project_member_service.add_member(
            project_id=project.id,
            discord_user_id=member.id,
            role=role,
        )

        project_member, created, status = result

        if status == "invalid_role":
            await ctx.send(
                "❌ Invalid role. Available roles:\n"
                "`owner`, `developer`, `designer`, "
                "`tester`, `manager`, `member`"
            )
            return

        if status == "already_member":
            await ctx.send(
                f"⚠️ {member.mention} is already a project member."
            )
            return

        await ctx.send(
            f"✅ Added {member.mention} to **{project.name}** "
            f"as `{project_member.role}`."
        )

    @project_member.command(name="remove")
    async def member_remove(
        self,
        ctx,
        project_name,
        member: discord.Member,
    ):
        """Remove a member from a project."""

        project = await project_service.get_project(
            project_name
        )

        if not project:
            await ctx.send(
                f"❌ Project `{project_name}` was not found."
            )
            return

        if not await permission_service.can_manage_members(
            project,
            ctx.author.id,
        ):
            await ctx.send(
                "⛔ You do not have permission to remove "
                "project members."
            )
            return

        if member.id == project.owner_discord_user_id:
            await ctx.send(
                "⛔ The project owner cannot be removed."
            )
            return

        removed = await project_member_service.remove_member(
            project_id=project.id,
            discord_user_id=member.id,
        )

        if not removed:
            await ctx.send(
                f"❌ {member.mention} is not a member of "
                f"**{project.name}**."
            )
            return

        await ctx.send(
            f"✅ Removed {member.mention} from "
            f"**{project.name}**."
        )


async def setup(bot):
    await bot.add_cog(ProjectCommands(bot))
