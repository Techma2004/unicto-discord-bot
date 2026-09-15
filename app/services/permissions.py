class PermissionService:
    """
    Centralized permission checks for NOVA projects.

    Discord server roles are the source of truth.
    """

    ROLE_MAP = {
        "Founder": "owner",
        "Administrator": "manager",
        "Moderator": "moderator",
        "Developer": "developer",
        "Designer": "designer",
        "Team Member": "member",
        "Contributor": "contributor",
    }

    MANAGEMENT_ROLES = {
        "owner",
        "manager",
        "moderator",
    }

    WORK_ROLES = {
        "owner",
        "manager",
        "moderator",
        "developer",
        "designer",
        "member",
        "contributor",
    }

    def get_discord_role_names(self, member):
        """
        Return the names of all Discord roles assigned to a member.
        """

        return {
            role.name
            for role in member.roles
            if role.name != "@everyone"
        }

    def get_nova_roles(self, member):
        """
        Convert Discord roles into NOVA roles.
        """

        discord_roles = self.get_discord_role_names(member)

        return {
            self.ROLE_MAP[role_name]
            for role_name in discord_roles
            if role_name in self.ROLE_MAP
        }

    def get_primary_nova_role(self, member):
        """
        Return the highest-priority NOVA role.

        Priority:
        owner > manager > moderator > developer >
        designer > member > contributor
        """

        nova_roles = self.get_nova_roles(member)

        priority = [
            "owner",
            "manager",
            "moderator",
            "developer",
            "designer",
            "member",
            "contributor",
        ]

        for role in priority:
            if role in nova_roles:
                return role

        return None

    def is_project_owner(self, project, member):
        """
        Check whether the Discord member owns the project.
        """

        return project.owner_discord_user_id == member.id

    def can_manage_project(self, project, member):
        """
        Check whether a Discord member can manage a project.
        """

        if self.is_project_owner(project, member):
            return True

        role = self.get_primary_nova_role(member)

        return role in self.MANAGEMENT_ROLES

    def can_manage_members(self, project, member):
        """
        Permission to add or remove project members.
        """

        return self.can_manage_project(
            project,
            member,
        )

    def can_manage_tasks(self, project, member):
        """
        Permission to create, assign, update,
        or delete project tasks.
        """

        return self.can_manage_project(
            project,
            member,
        )

    def can_manage_memory(self, project, member):
        """
        Permission to add or delete project memory.
        """

        return self.can_manage_project(
            project,
            member,
        )

    def can_view_project(self, project, member):
        """
        Check whether a Discord member can access
        project information.
        """

        return self.get_primary_nova_role(member) in self.WORK_ROLES


permission_service = PermissionService()
