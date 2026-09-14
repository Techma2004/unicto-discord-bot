import asyncio
import logging
import os
import time

import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai

from app.ai.prompts import SYSTEM_PROMPT
from app.services.context_manager import context_manager
from app.services.memory import memory
from app.services.project_members import project_member_service
from app.services.project_memory import project_memory
from app.services.projects import project_service
from app.services.request_queue import request_queue
from app.services.tasks import task_service
from app.services.team import team_service
from app.services.usage_guard import usage_guard





# ============================================================
# CONFIG
# ============================================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in .env")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("nova")


# ============================================================
# GEMINI
# ============================================================

gemini = genai.Client(
    api_key=GEMINI_API_KEY
)

MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]




# ============================================================
# MODEL ROUTER
# ============================================================

model_cooldowns = {}


def model_is_available(model):
    cooldown_until = model_cooldowns.get(model, 0)

    return time.monotonic() >= cooldown_until


def cooldown_model(model, seconds):
    model_cooldowns[model] = (
        time.monotonic() + seconds
    )

    logger.warning(
        "Model %s cooled down for %s seconds",
        model,
        seconds,
    )


def get_cooldown_remaining(model):
    remaining = (
        model_cooldowns.get(model, 0)
        - time.monotonic()
    )

    return max(0, int(remaining))


def classify_error(error):
    error_text = str(error).lower()

    if (
        "generaterequestsperdayperproject"
        in error_text
        or "free_tier_requests"
        in error_text
    ):
        return "daily_quota"

    if (
        "resource_exhausted"
        in error_text
        or "429"
        in error_text
        or "rate limit"
        in error_text
        or "quota"
        in error_text
    ):
        return "rate_limit"

    if (
        "503"
        in error_text
        or "unavailable"
        in error_text
        or "server error"
        in error_text
    ):
        return "server"

    if (
        "remoteprotocolerror"
        in error_text
        or "server disconnected"
        in error_text
        or "connection"
        in error_text
        or "timeout"
        in error_text
    ):
        return "network"

    return "unknown"


# ============================================================
# GEMINI REQUEST
# ============================================================

async def ask_nova(
    prompt,
    conversation_context="",
):
    """
    Send a request through the Gemini model router.

    Returns:
        (response_text, model_used)
    """

    full_prompt = (
        SYSTEM_PROMPT
        + conversation_context
        + "\n\nCURRENT USER MESSAGE:\n"
        + prompt
    )

    for model in MODELS:

        if not model_is_available(model):

            remaining = get_cooldown_remaining(model)

            logger.info(
                "Skipping %s (cooldown: %ss)",
                model,
                remaining,
            )

            continue

        try:

            logger.info(
                "Trying Gemini model: %s",
                model,
            )

            response = await asyncio.to_thread(
                gemini.models.generate_content,
                model=model,
                contents=full_prompt,
            )

            text = response.text

            if not text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            logger.info(
                "Gemini response successful using %s",
                model,
            )

            return text, model

        except Exception as error:

            error_type = classify_error(error)

            logger.warning(
                "Gemini %s failed: %s | %s",
                model,
                error_type,
                error,
            )

            if error_type == "daily_quota":

                cooldown_model(
                    model,
                    20 * 60 * 60,
                )

            elif error_type == "rate_limit":

                cooldown_model(
                    model,
                    90,
                )

            elif error_type == "server":

                cooldown_model(
                    model,
                    60,
                )

            elif error_type == "network":

                cooldown_model(
                    model,
                    30,
                )

            else:
                raise

    raise RuntimeError(
        "All NOVA AI models are currently unavailable."
    )


# ============================================================
# DISCORD
# ============================================================

from app.bot.client import NOVAClient

bot = NOVAClient(request_queue)



@bot.event
async def on_ready():

    logger.info(
        "NOVA is online as %s",
        bot.user,
    )

    logger.info(
        "Bot ID: %s",
        bot.user.id,
    )


# ============================================================
# DISCORD MESSAGE CHUNKING
# ============================================================

async def send_reply(
    message,
    text,
):
    """
    Discord has a 2000-character message limit.
    """

    for index in range(
        0,
        len(text),
        2000,
    ):

        chunk = text[index:index + 2000]

        await message.reply(
            chunk,
            mention_author=False,
        )


# ============================================================
# PROCESS AI REQUEST
# ============================================================

async def process_ai_request(
    message,
    prompt,
):
    """
    Submit a NOVA AI request to the request queue.
    """

    if not prompt.strip():

        await message.reply(
            "Please give me something to work with 😄",
            mention_author=False,
        )

        return

    try:

        await request_queue.submit(
            process_ai_request_inner,
            message,
            prompt,
        )

    except RuntimeError as error:

        await message.reply(
            f"⏳ {error}",
            mention_author=False,
        )

    except Exception:

        logger.exception(
            "Queued NOVA request failed."
        )

        await message.reply(
            "⚠️ I ran into a problem while processing that request. Please try again.",
            mention_author=False,
        )


async def process_ai_request_inner(
    message,
    prompt,
):
    """
    Actual NOVA AI + team + usage guard + memory workflow.

    This function runs inside the request queue.
    """

    # ------------------------------------------------
    # 1. Usage Guard
    # ------------------------------------------------

    allowed, limit_message = await usage_guard.check(
        message.author.id
    )

    if not allowed:

        logger.info(
            "Usage Guard blocked Discord ID %s: %s",
            message.author.id,
            limit_message,
        )

        await message.reply(
            limit_message,
            mention_author=False,
        )

        return

    try:

        async with message.channel.typing():

            # ------------------------------------------------
            # 2. Register / update UNICTO team member
            # ------------------------------------------------

            member, is_new_member = (
                await team_service.register_member(
                    message.author
                )
            )

            logger.info(
                "Team member registered | Discord ID: %s | New: %s",
                message.author.id,
                is_new_member,
            )

            # ------------------------------------------------
            # 3. Identify / create NOVA user
            # ------------------------------------------------

            user_id = await memory.get_or_create_user(
                message.author
            )

            logger.info(
                "NOVA user ID: %s | Discord ID: %s",
                user_id,
                message.author.id,
            )

            # ------------------------------------------------
            # 4. Identify / create conversation
            # ------------------------------------------------

            conversation_id = (
                await memory.get_or_create_conversation(
                    user_id,
                    message.channel.id,
                )
            )

            logger.info(
                "Conversation ID: %s",
                conversation_id,
            )

            # ------------------------------------------------
            # 5. Load previous conversation
            # ------------------------------------------------

            previous_messages = (
                await memory.get_recent_messages(
                    conversation_id,
                    limit=12,
                )
            )

            logger.info(
                "Loaded %s previous messages",
                len(previous_messages),
            )

            # ------------------------------------------------
            # 6. Context Manager
            # ------------------------------------------------

            conversation_context = (
                context_manager.build_prompt_context(
                    previous_messages
                )
            )

            logger.info(
                "Context prepared: %s characters",
                len(conversation_context),
            )

            # ------------------------------------------------
            # 7. Ask Gemini
            # ------------------------------------------------

            reply, model_used = await ask_nova(
                prompt,
                conversation_context,
            )

            # ------------------------------------------------
            # 8. Record successful usage
            # ------------------------------------------------

            usage_guard.record_request(
                message.author.id
            )

            await usage_guard.record_usage(
                message.author.id,
                model_used,
            )

            logger.info(
                "Usage recorded | Discord ID: %s | Model: %s",
                message.author.id,
                model_used,
            )

            # ------------------------------------------------
            # 9. Save user message
            # ------------------------------------------------

            await memory.save_message(
                conversation_id,
                "user",
                prompt,
            )

            # ------------------------------------------------
            # 10. Save NOVA response
            # ------------------------------------------------

            await memory.save_message(
                conversation_id,
                "assistant",
                reply,
                model_used,
            )

            logger.info(
                "Conversation saved successfully."
            )

            # ------------------------------------------------
            # 11. Send response
            # ------------------------------------------------

            await send_reply(
                message,
                reply,
            )

    except Exception:

        logger.exception(
            "NOVA request failed."
        )

        await message.reply(
            "⚠️ I ran into a problem while processing that request. Please try again.",
            mention_author=False,
        )


# ============================================================
# MESSAGE HANDLER
# ============================================================

@bot.event
async def on_message(message):

    # Ignore bots
    if message.author.bot:
        return

    # --------------------------------------------------------
    # !ping
    # --------------------------------------------------------

    if message.content == "!ping":

        await message.reply(
            "🏓 Pong! NOVA is online.",
            mention_author=False,
        )

        return

    # --------------------------------------------------------
    # !project
    # --------------------------------------------------------

    if message.content.startswith("!project"):

        logger.info(
            "PROJECT COMMAND RECEIVED | Content: %s",
            message.content,
        )

        parts = message.content.split(maxsplit=3)

        if len(parts) < 2:
            await message.reply(
                "📁 **Project Management**\n\n"
                "Available commands:\n"
                "`!project create <name> [description]`\n"
                "`!project list`\n"
                "`!project info <name>`\n"
                "`!project delete <name>`",
                mention_author=False,
            )
            return

        action = parts[1].lower()
        # !project member
        if action == "member":

            member_parts = message.content.split(
                maxsplit=4
            )

            if len(member_parts) < 4:
                await message.channel.send(
                    "**Project Member Commands**\n\n"
                    "`!project member add <project> @user <role>`\n"
                    "`!project member list <project>`\n"
                    "`!project member remove <project> @user`\n\n"
                    "**Roles:** `developer`, `designer`, "
                    "`tester`, `manager`, `member`"
                )
                return

            member_action = member_parts[2].lower()
            project_name = member_parts[3]

            project = await project_service.get_project(
                project_name
            )

            if not project:
                await message.channel.send(
                    f"❌ Project `{project_name}` was not found."
                )
                return

            # LIST MEMBERS
            if member_action == "list":

                members = await project_member_service.get_members(
                    project.id
                )

                if not members:
                    await message.channel.send(
                        f"👥 Project **{project.name}** has no members."
                    )
                    return

                lines = [
                    f"👥 **{project.name} — Members**",
                    ""
                ]

                for member in members:
                    lines.append(
                        f"• <@{member.discord_user_id}> "
                        f"— `{member.role}`"
                    )

                await message.channel.send(
                    "\n".join(lines)
                )
                return

            # OWNER-ONLY ACTIONS
            if message.author.id != project.owner_discord_user_id:
                await message.channel.send(
                    "🔒 Only the **project owner** can manage "
                    "project members."
                )
                return

            # ADD MEMBER
            if member_action == "add":

                if len(member_parts) < 5:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!project member add <project> "
                        "@user <role>`"
                    )
                    return

                if not message.mentions:
                    await message.channel.send(
                        "❌ Please mention the Discord user "
                        "you want to add."
                    )
                    return

                target_user = message.mentions[0]
                role = member_parts[4].lower()

                member, created, status = (
                    await project_member_service.add_member(
                        project.id,
                        target_user.id,
                        role,
                    )
                )

                if status == "invalid_role":
                    await message.channel.send(
                        "❌ Invalid role.\n\n"
                        "**Available roles:** "
                        "`developer`, `designer`, `tester`, "
                        "`manager`, `member`"
                    )
                    return

                if status == "already_member":
                    await message.channel.send(
                        f"⚠️ {target_user.mention} is already "
                        f"a member of **{project.name}**."
                    )
                    return

                await message.channel.send(
                    f"✅ Added {target_user.mention} to "
                    f"**{project.name}** as `{role}`."
                )
                return

            # REMOVE MEMBER
            if member_action == "remove":

                if not message.mentions:
                    await message.channel.send(
                        "❌ Please mention the Discord user "
                        "you want to remove."
                    )
                    return

                target_user = message.mentions[0]

                removed = (
                    await project_member_service.remove_member(
                        project.id,
                        target_user.id,
                    )
                )

                if not removed:
                    await message.channel.send(
                        f"⚠️ {target_user.mention} is not "
                        f"a member of **{project.name}**."
                    )
                    return

                await message.channel.send(
                    f"✅ Removed {target_user.mention} from "
                    f"**{project.name}**."
                )
                return

            await message.channel.send(
                "❌ Unknown member action.\n\n"
                "Use:\n"
                "`add` — Add a member\n"
                "`list` — List members\n"
                "`remove` — Remove a member"
            )
            return
        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

        if action == "create":

            if len(parts) < 3:
                await message.reply(
                    "❌ Please provide a project name.\n"
                    "Example: `!project create WENET`",
                    mention_author=False,
                )
                return

            project_name = parts[2]
            description = ""

            if len(parts) >= 4:
                description = parts[3]

            project, created = (
                await project_service.create_project(
                    name=project_name,
                    description=description,
                    owner_discord_user_id=message.author.id,
                )
            )

            if not created:
                await message.reply(
                    f"⚠️ A project named **{project_name}** "
                    "already exists.",
                    mention_author=False,
                )
                return

            await message.reply(
                f"✅ **Project created!**\n\n"
                f"📁 **Name:** {project.name}\n"
                f"👤 **Owner:** {message.author.mention}\n"
                f"📝 **Description:** "
                f"{project.description or 'No description'}",
                mention_author=False,
            )
            return

        # ----------------------------------------------------
        # LIST
        # ----------------------------------------------------

        if action == "list":

            projects = (
                await project_service.get_all_projects()
            )

            if not projects:
                await message.reply(
                    "📁 No UNICTO projects have been created yet.",
                    mention_author=False,
                )
                return

            lines = [
                "📁 **UNICTO Projects**",
                "",
            ]

            for project in projects:
                lines.append(
                    f"• **{project.name}** — "
                    f"{project.description or 'No description'}"
                )

            await message.reply(
                "\n".join(lines),
                mention_author=False,
            )
            return

        # ----------------------------------------------------
        # INFO
        # ----------------------------------------------------

        if action == "info":

            if len(parts) < 3:
                await message.reply(
                    "❌ Please provide a project name.\n"
                    "Example: `!project info WENET`",
                    mention_author=False,
                )
                return

            project_name = parts[2]

            project = await project_service.get_project(
                project_name
            )

            if not project:
                await message.reply(
                    f"❌ Project **{project_name}** was not found.",
                    mention_author=False,
                )
                return

            await message.reply(
                f"📁 **Project: {project.name}**\n\n"
                f"📝 **Description:** "
                f"{project.description or 'No description'}\n"
                f"👤 **Owner ID:** `{project.owner_discord_user_id}`\n"
                f"📅 **Created:** "
                f"{project.created_at.strftime('%Y-%m-%d')}",
                mention_author=False,
            )
            return

        # ----------------------------------------------------
        # DELETE
        # ----------------------------------------------------

        if action == "delete":

            if len(parts) < 3:
                await message.reply(
                    "❌ Please provide a project name.\n"
                    "Example: `!project delete WENET`",
                    mention_author=False,
                )
                return

            project_name = parts[2]

            project = await project_service.get_project(
                project_name
            )

            if not project:
                await message.reply(
                    f"❌ Project **{project_name}** was not found.",
                    mention_author=False,
                )
                return

            if (
                project.owner_discord_user_id
                != message.author.id
            ):
                await message.reply(
                    "🔒 Only the project owner can delete "
                    "this project.",
                    mention_author=False,
                )
                return

            deleted = await project_service.delete_project(
                project_name
            )

            if deleted:
                await message.reply(
                    f"🗑️ Project **{project_name}** has been deleted.",
                    mention_author=False,
                )

            return

        await message.reply(
            f"❓ Unknown project action: `{action}`\n\n"
            "Use `!project` to see available commands.",
            mention_author=False,
        )

        return

        # !task
        if message.content.startswith("!task"):
            logger.info(
                "TASK COMMAND RECEIVED | Content: %s",
                message.content,
            )

            parts = message.content.split(maxsplit=3)

            if len(parts) < 2:
                await message.channel.send(
                    "**NOVA Task Commands**\n\n"
                    "`!task create <project> <title>`\n"
                    "`!task list <project>`\n"
                    "`!task assign <project> <task_id> @user`\n"
                    "`!task status <project> <task_id> <status>`\n"
                    "`!task delete <project> <task_id>`\n\n"
                    "**Statuses:** `todo`, `in_progress`, `done`\n"
                    "**Priorities:** `low`, `normal`, `high`, `urgent`"
                )
                return

            action = parts[1].lower()

            # CREATE TASK
            if action == "create":

                if len(parts) < 4:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!task create <project> <title>`"
                    )
                    return

                project_name = parts[2]
                title = parts[3].strip()

                project = await project_service.get_project(
                    project_name
                )

                if not project:
                    await message.channel.send(
                        f"❌ Project `{project_name}` was not found."
                    )
                    return

                member = await project_member_service.get_member(
                    project.id,
                    message.author.id,
                )

                if not member:
                    await message.channel.send(
                        "🔒 You must be a member of this project "
                        "to create tasks."
                    )
                    return

                task, created, status = (
                    await task_service.create_task(
                        project.id,
                        title,
                        None,
                        message.author.id,
                    )
                )

                if not created:
                    await message.channel.send(
                        "❌ Failed to create the task."
                    )
                    return

                await message.channel.send(
                    f"✅ Task created in **{project.name}**\n\n"
                    f"**#{task.id} — {task.title}**\n"
                    f"Status: `todo`\n"
                    f"Priority: `normal`"
                )
                return

            # LIST TASKS
            if action == "list":

                if len(parts) < 3:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!task list <project>`"
                    )
                    return

                project_name = parts[2]

                project = await project_service.get_project(
                    project_name
                )

                if not project:
                    await message.channel.send(
                        f"❌ Project `{project_name}` was not found."
                    )
                    return

                member = await project_member_service.get_member(
                    project.id,
                    message.author.id,
                )

                if not member:
                    await message.channel.send(
                        "🔒 You must be a member of this project "
                        "to view its tasks."
                    )
                    return

                tasks = await task_service.get_tasks(
                    project.id
                )

                if not tasks:
                    await message.channel.send(
                        f"📋 **{project.name}** has no tasks yet."
                    )
                    return

                lines = [
                    f"📋 **{project.name} — Tasks**",
                    "",
                ]

                for task in tasks:
                    assignee = (
                        f"<@{task.assigned_discord_user_id}>"
                        if task.assigned_discord_user_id
                        else "Unassigned"
                    )

                    lines.append(
                        f"**#{task.id} — {task.title}**\n"
                        f"Status: `{task.status}` | "
                        f"Priority: `{task.priority}`\n"
                        f"Assigned: {assignee}"
                    )

                await message.channel.send(
                    "\n\n".join(lines)
                )
                return

            # ASSIGN TASK
            if action == "assign":

                member_parts = message.content.split(
                    maxsplit=4
                )

                if len(member_parts) < 5:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!task assign <project> <task_id> @user`"
                    )
                    return

                project_name = member_parts[2]

                try:
                    task_id = int(member_parts[3])
                except ValueError:
                    await message.channel.send(
                        "❌ Task ID must be a number."
                    )
                    return

                if not message.mentions:
                    await message.channel.send(
                        "❌ Please mention the user to assign "
                        "the task to."
                    )
                    return

                target_user = message.mentions[0]

                project = await project_service.get_project(
                    project_name
                )

                if not project:
                    await message.channel.send(
                        f"❌ Project `{project_name}` was not found."
                    )
                    return

                member = await project_member_service.get_member(
                    project.id,
                    message.author.id,
                )

                if not member:
                    await message.channel.send(
                        "🔒 You must be a project member to "
                        "assign tasks."
                    )
                    return

                target_member = (
                    await project_member_service.get_member(
                        project.id,
                        target_user.id,
                    )
                )

                if not target_member:
                    await message.channel.send(
                        f"❌ {target_user.mention} is not a member "
                        f"of **{project.name}**."
                    )
                    return

                task, updated = await task_service.assign_task(
                    project.id,
                    task_id,
                    target_user.id,
                )

                if not updated:
                    await message.channel.send(
                        f"❌ Task `#{task_id}` was not found."
                    )
                    return

                await message.channel.send(
                    f"✅ Task **#{task.id} — {task.title}** "
                    f"assigned to {target_user.mention}."
                )
                return

            # UPDATE STATUS
            if action == "status":

                if len(parts) < 4:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!task status <project> "
                        "<task_id> <status>`"
                    )
                    return

                status_parts = message.content.split(
                    maxsplit=4
                )

                if len(status_parts) < 5:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!task status <project> "
                        "<task_id> <status>`"
                    )
                    return

                project_name = status_parts[2]

                try:
                    task_id = int(status_parts[3])
                except ValueError:
                    await message.channel.send(
                        "❌ Task ID must be a number."
                    )
                    return

                new_status = status_parts[4].lower()

                project = await project_service.get_project(
                    project_name
                )

                if not project:
                    await message.channel.send(
                        f"❌ Project `{project_name}` was not found."
                    )
                    return

                member = await project_member_service.get_member(
                    project.id,
                    message.author.id,
                )

                if not member:
                    await message.channel.send(
                        "🔒 You must be a project member to "
                        "update tasks."
                    )
                    return

                task, updated, result = (
                    await task_service.update_status(
                        project.id,
                        task_id,
                        new_status,
                    )
                )

                if result == "invalid_status":
                    await message.channel.send(
                        "❌ Invalid status.\n\n"
                        "**Available:** "
                        "`todo`, `in_progress`, `done`"
                    )
                    return

                if result == "not_found":
                    await message.channel.send(
                        f"❌ Task `#{task_id}` was not found."
                    )
                    return

                await message.channel.send(
                    f"✅ Task **#{task.id} — {task.title}** "
                    f"is now `{task.status}`."
                )
                return

            # DELETE TASK
            if action == "delete":

                if len(parts) < 4:
                    await message.channel.send(
                        "❌ Usage:\n"
                        "`!task delete <project> <task_id>`"
                    )
                    return

                project_name = parts[2]

                try:
                    task_id = int(parts[3])
                except ValueError:
                    await message.channel.send(
                        "❌ Task ID must be a number."
                    )
                    return

                project = await project_service.get_project(
                    project_name
                )

                if not project:
                    await message.channel.send(
                        f"❌ Project `{project_name}` was not found."
                    )
                    return

                member = await project_member_service.get_member(
                    project.id,
                    message.author.id,
                )

                if not member:
                    await message.channel.send(
                        "🔒 You must be a project member to "
                        "delete tasks."
                    )
                    return

                task = await task_service.get_task(
                    project.id,
                    task_id,
                )

                if not task:
                    await message.channel.send(
                        f"❌ Task `#{task_id}` was not found."
                    )
                    return

                deleted = await task_service.delete_task(
                    project.id,
                    task_id,
                )

                if not deleted:
                    await message.channel.send(
                        "❌ Failed to delete the task."
                    )
                    return

                await message.channel.send(
                    f"🗑️ Task `#{task_id}` — "
                    f"**{task.title}** has been deleted."
                )
                return

            await message.channel.send(
                "❌ Unknown task command.\n\n"
                "Use `!task` to see the available commands."
            )
            return
            # --------------------------------
            # PROJECT MEMORY COMMANDS
            # --------------------------------

            if message.content.startswith("!memory"):
                raw = message.content[len("!memory"):].strip()

                if not raw:
                    await message.channel.send(
                        "🧠 **Project Memory**\n"
                        "Usage: `!memory add <project> | <title> | <content>`"
                    )
                    return

                parts = [part.strip() for part in raw.split("|", 2)]

                action = parts[0].lower()

                if action != "add":
                    await message.channel.send(
                        "❌ Unknown memory command.\n"
                        "Use: `!memory add <project> | <title> | <content>`"
                    )
                    return

                if len(parts) != 3:
                    await message.channel.send(
                        "🧠 Usage:\n"
                        "`!memory add <project> | <title> | <content>`"
                    )
                    return

                project_name = parts[0]
                title = parts[1]
                content = parts[2]

                # The first part currently contains "add <project>"
                action_parts = project_name.split(maxsplit=1)

                if len(action_parts) != 2:
                    await message.channel.send(
                        "🧠 Usage:\n"
                        "`!memory add <project> | <title> | <content>`"
                    )
                    return

                project_name = action_parts[1].strip()

                if not project_name or not title or not content:
                    await message.channel.send(
                        "❌ Project, title, and content cannot be empty."
                    )
                    return

                project = await project_service.get_project(
                    project_name
                )

                if not project:
                    await message.channel.send(
                        f"❌ Project `{project_name}` was not found."
                    )
                    return

                member = await project_member_service.get_member(
                    project.id,
                    message.author.id,
                )

                if not member:
                    await message.channel.send(
                        "❌ You must be a member of this project "
                        "to add shared memory."
                    )
                    return

                note = await project_memory.create_note(
                    project_id=project.id,
                    title=title,
                    content=content,
                    created_by_discord_user_id=message.author.id,
                )

                await message.channel.send(
                    "🧠 **Memory saved!**\n"
                    f"**ID:** `{note.id}`\n"
                    f"**Project:** `{project.name}`\n"
                    f"**Title:** {note.title}"
                )

                return
    # --------------------------------------------------------
    # !ask
    # --------------------------------------------------------

    if message.content.startswith("!ask"):

        prompt = message.content[4:].strip()

        await process_ai_request(
            message,
            prompt,
        )

        return

    # --------------------------------------------------------
    # Direct Messages
    # --------------------------------------------------------

    if isinstance(
        message.channel,
        discord.DMChannel,
    ):

        await process_ai_request(
            message,
            message.content,
        )

        return

    # --------------------------------------------------------
    # Mentions
    # --------------------------------------------------------

    if bot.user in message.mentions:

        prompt = message.content.replace(
            f"<@{bot.user.id}>",
            "",
        ).strip()

        prompt = prompt.replace(
            f"<@!{bot.user.id}>",
            "",
        ).strip()

        if not prompt:
            await message.reply(
                "👋 Hi! I'm NOVA, the UNICTO AI assistant.\n"
                "Ask me something or use `!ask <question>`.",
                mention_author=False,
            )
            return

        await process_ai_request(
            message,
            prompt,
        )

        return

# ============================================================
# START
# ============================================================

def main():

    logger.info(
        "Starting NOVA..."
    )

    bot.run(
        DISCORD_TOKEN
    )


if __name__ == "__main__":
    main()
