import discord
from discord.ext import commands

from app.services.projects import project_service
from app.services.project_members import project_member_service
from app.services.permissions import permission_service


class ProjectCommands(commands.Cog):
    """Project management commands for NOVA."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        name="project",
        invoke_without_command=True,
    )
    async def project(self, ctx):
        """Manage UNICTO projects."""

        if ctx.invoked_subcommand is None:
            await ctx.send(
                "📁 **Project Commands**\n"
                "`!project create <name> | <description>`\n"
                "`!project list`\n"
                "`!project info <name>`\n"
                "`!project delete <name>`\n"
                "`!project member list <name>`\n"
                "`!project member add <name> @user [role]`\n"
                "`!project member remove <name> @user`"
            )

    @project.command(name="create")
    async def project_create(
        self,
        ctx,
        *,
        details=None,
    ):
        """Create a new project."""

        if not permission_service.can_create_project(ctx.author):
            await ctx.send(
                "⛔ You do not have permission to create projects."
            )
            return

        if not details:
            await ctx.send(
                "❌ Please provide a project name.\n"
                "Example: `!project create NOVA | Discord AI assistant`"
            )
            return

        if "|" in details:
            name, description = details.split("|", 1)
            name = name.strip()
            description = description.strip()
        else:
            name = details.strip()
            description = ""

        if not name:
            await ctx.send(
                "❌ Project name cannot be empty."
            )
            return

        project, created = await project_service.create_project(
            name=name,
            description=description,
            owner_discord_user_id=ctx.author.id,
        )

        if not created:
            await ctx.send(
                f"⚠️ A project named **{name}** already exists."
            )
            return

        await ctx.send(
            f"✅ Project **{project.name}** created successfully.\n"
            f"👑 Owner: {ctx.author.mention}"
        )

    @project.command(name="list")
    async def project_list(self, ctx):
        """List projects."""

        projects = await project_service.get_all_projects()

        visible_projects = [
            project
            for project in projects
            if permission_service.can_view_project(
                project,
                ctx.author,
            )
        ]

        if not visible_projects:
            await ctx.send(
                "📁 No projects are currently available to you."
            )
            return

        lines = ["📁 **UNICTO Projects**"]

        for project in visible_projects:
            description = (
                f" — {project.description}"
                if project.description
                else ""
            )

            lines.append(
                f"• **{project.name}**{description}"
            )

        await ctx.send("\n".join(lines))

    @project.command(name="info")
    async def project_info(
        self,
        ctx,
        *,
        project_name=None,
    ):
        """Show project information."""

        if not project_name:
            await ctx.send(
                "❌ Please provide a project name.\n"
                "Example: `!project info NOVA`"
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
                "⛔ You do not have permission to view this project."
            )
            return

        members = await project_member_service.get_members(
            project.id
        )

        embed = discord.Embed(
            title=f"📁 {project.name}",
            description=(
                project.description
                or "No description provided."
            ),
        )

        embed.add_field(
            name="👑 Owner",
            value=f"<@{project.owner_discord_user_id}>",
            inline=False,
        )

        if members:
            member_lines = []

            for member in members:
                member_lines.append(
                    f"• <@{member.discord_user_id}> — "
                    f"`{member.role}`"
                )

            embed.add_field(
                name="👥 Members",
                value="\n".join(member_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="👥 Members",
                value="No project members yet.",
                inline=False,
            )

        await ctx.send(embed=embed)

    @project.command(name="delete")
    async def project_delete(
        self,
        ctx,
        *,
        project_name=None,
    ):
        """Delete a project."""

        if not project_name:
            await ctx.send(
                "❌ Please provide a project name."
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

        if not permission_service.can_manage_project(
            project,
            ctx.author,
        ):
            await ctx.send(
                "⛔ You do not have permission to delete "
                "this project."
            )
            return

        deleted = await project_service.delete_project(
            project.name
        )

        if not deleted:
            await ctx.send(
                "⚠️ The project could not be deleted."
            )
            return

        await ctx.send(
            f"🗑️ Project **{project.name}** has been deleted."
        )

    @project.group(
        name="member",
        invoke_without_command=True,
    )
    async def project_member(self, ctx):
        """Manage project members."""

        if ctx.invoked_subcommand is None:
            await ctx.send(
                "👥 **Project Member Commands**\n"
                "`!project member list <project>`\n"
                "`!project member add <project> @user [role]`\n"
                "`!project member remove <project> @user`"
            )

    @project_member.command(name="list")
    async def member_list(
        self,
        ctx,
        *,
        project_name=None,
    ):
        """List project members."""

        if not project_name:
            await ctx.send(
                "❌ Please provide a project name."
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
                "this project."
            )
            return

        members = await project_member_service.get_members(
            project.id
        )

        if not members:
            await ctx.send(
                f"👥 Project **{project.name}** has no members yet."
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

        await ctx.send("\n".join(lines))

    @project_member.command(name="add")
    async def member_add(
        self,
        ctx,
        project_name=None,
        member: discord.Member = None,
        role="member",
    ):
        """Add a member to a project."""

        if not project_name or not member:
            await ctx.send(
                "❌ Usage:\n"
                "`!project member add <project> @user [role]`"
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

        if not permission_service.can_manage_members(
            project,
            ctx.author,
        ):
            await ctx.send(
                "⛔ You do not have permission to manage "
                "this project's members."
            )
            return

        role = role.lower()

        valid_roles = project_member_service.VALID_ROLES

        if role not in valid_roles:
            roles = ", ".join(
                f"`{item}`"
                for item in sorted(valid_roles)
            )

            await ctx.send(
                f"❌ Invalid project role.\n"
                f"Valid roles: {roles}"
            )
            return

        if (
            role == "owner"
            and not permission_service.is_project_owner(
                project,
                ctx.author,
            )
        ):
            await ctx.send(
                "⛔ Only the project owner can assign "
                "the `owner` project role."
            )
            return

        existing = await project_member_service.get_member(
            project.id,
            member.id,
        )

        if existing:
            await ctx.send(
                f"⚠️ {member.mention} is already a member "
                f"of **{project.name}**."
            )
            return

        created_member, created, status = (
            await project_member_service.add_member(
                project_id=project.id,
                discord_user_id=member.id,
                role=role,
            )
        )

        if not created:
            if status == "already_member":
                await ctx.send(
                    f"⚠️ {member.mention} is already a member "
                    f"of **{project.name}**."
                )
            else:
                await ctx.send(
                    f"⚠️ Could not add {member.mention} "
                    f"to the project."
                )
            return

        await ctx.send(
            f"✅ Added {member.mention} to **{project.name}** "
            f"as `{created_member.role}`."
        )

    @project_member.command(name="remove")
    async def member_remove(
        self,
        ctx,
        project_name=None,
        member: discord.Member = None,
    ):
        """Remove a member from a project."""

        if not project_name or not member:
            await ctx.send(
                "❌ Usage:\n"
                "`!project member remove <project> @user`"
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

        if not permission_service.can_manage_members(
            project,
            ctx.author,
        ):
            await ctx.send(
                "⛔ You do not have permission to manage "
                "this project's members."
            )
            return

        if permission_service.is_project_owner(
            project,
            member,
        ):
            await ctx.send(
                "⛔ The project owner cannot be removed "
                "from the project."
            )
            return

        removed = await project_member_service.remove_member(
            project.id,
            member.id,
        )

        if not removed:
            await ctx.send(
                f"⚠️ {member.mention} is not a member "
                f"of **{project.name}**."
            )
            return

        await ctx.send(
            f"✅ Removed {member.mention} from "
            f"**{project.name}**."
        )


async def setup(bot):
    await bot.add_cog(ProjectCommands(bot))
