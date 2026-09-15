from app.services.project_members import project_member_service


class PermissionService:
    """
    Centralized permission checks for NOVA projects.
    """

    OWNER = "owner"

    MANAGEMENT_ROLES = {
        "owner",
        "manager",
    }

    WORK_ROLES = {
        "owner",
        "manager",
        "developer",
        "designer",
        "tester",
        "member",
    }

    async def get_project_role(
        self,
        project_id,
        discord_user_id,
    ):
        """
        Return the user's project role.

        Returns:
            str | None
        """

        member = await project_member_service.get_member(
            project_id,
            discord_user_id,
        )

        if not member:
            return None

        return member.role

    async def is_project_member(
        self,
        project_id,
        discord_user_id,
    ):
        """Check whether a user belongs to a project."""

        role = await self.get_project_role(
            project_id,
            discord_user_id,
        )

        return role is not None

    async def is_project_owner(
        self,
        project,
        discord_user_id,
    ):
        """Check whether the user owns the project."""

        return (
            project.owner_discord_user_id
            == discord_user_id
        )

    async def can_manage_project(
        self,
        project,
        discord_user_id,
    ):
        """
        Project-level management permission.

        The project owner always has permission.
        Managers may manage project operations.
        """

        if await self.is_project_owner(
            project,
            discord_user_id,
        ):
            return True

        role = await self.get_project_role(
            project.id,
            discord_user_id,
        )

        return role in self.MANAGEMENT_ROLES

    async def can_manage_members(
        self,
        project,
        discord_user_id,
    ):
        """
        Permission to add/remove project members.
        """

        return await self.can_manage_project(
            project,
            discord_user_id,
        )

    async def can_manage_tasks(
        self,
        project,
        discord_user_id,
    ):
        """
        Permission to create, assign, update,
        or delete project tasks.
        """

        return await self.can_manage_project(
            project,
            discord_user_id,
        )

    async def can_manage_memory(
        self,
        project,
        discord_user_id,
    ):
        """
        Permission to add or delete project memory.
        """

        return await self.can_manage_project(
            project,
            discord_user_id,
        )

    async def can_view_project(
        self,
        project,
        discord_user_id,
    ):
        """
        Check whether a user can access project information.
        """

        return await self.is_project_member(
            project.id,
            discord_user_id,
        )


permission_service = PermissionService()
