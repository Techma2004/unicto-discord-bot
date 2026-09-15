import logging
import os

import discord
from dotenv import load_dotenv
from app.health import start_health_server
from app.ai.router import GeminiRouter
from app.bot.client import NOVAClient
from app.services.context_manager import context_manager
from app.services.memory import memory
from app.services.request_queue import request_queue
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

MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

gemini_router = GeminiRouter(
    api_key=GEMINI_API_KEY,
    models=MODELS,
)


# ============================================================
# GEMINI REQUEST
# ============================================================

async def ask_nova(
    prompt,
    conversation_context="",
):
    return await gemini_router.ask(
        prompt,
        conversation_context,
    )


# ============================================================
# DISCORD
# ============================================================

bot = NOVAClient(request_queue)


# ============================================================
# TARGET HELPERS
# ============================================================

def get_author(target):
    """Return the Discord user from a Message or Interaction."""

    if isinstance(target, discord.Interaction):
        return target.user

    return target.author


def get_channel(target):
    """Return the Discord channel from a Message or Interaction."""

    return target.channel


# ============================================================
# DISCORD RESPONSE
# ============================================================

async def send_reply(
    target,
    text,
):
    """
    Send a response to either a Discord Message
    or a Discord Interaction.

    Discord messages are limited to 2000 characters.
    """

    for index in range(
        0,
        len(text),
        2000,
    ):
        chunk = text[index:index + 2000]

        if isinstance(target, discord.Interaction):
            await target.followup.send(chunk)
        else:
            await target.reply(
                chunk,
                mention_author=False,
            )


# ============================================================
# PROCESS AI REQUEST
# ============================================================

async def process_ai_request(
    target,
    prompt,
):
    """
    Submit a NOVA AI request to the request queue.

    Supports both:
    - Discord Message
    - Discord Interaction
    """

    if not prompt.strip():
        await send_reply(
            target,
            "Please give me something to work with 😄",
        )
        return

    try:
        await request_queue.submit(
            process_ai_request_inner,
            target,
            prompt,
        )

    except RuntimeError as error:
        await send_reply(
            target,
            f"⏳ {error}",
        )

    except Exception:
        logger.exception(
            "Queued NOVA request failed."
        )

        await send_reply(
            target,
            "⚠️ I ran into a problem while processing that request. "
            "Please try again.",
        )


# ============================================================
# AI REQUEST WORKER
# ============================================================

async def process_ai_request_inner(
    target,
    prompt,
):
    """
    Actual NOVA AI + team + usage guard + memory workflow.

    This function runs inside the request queue.
    """

    author = get_author(target)
    channel = get_channel(target)

    # ------------------------------------------------
    # 1. Usage Guard
    # ------------------------------------------------

    allowed, limit_message = await usage_guard.check(
        author.id
    )

    if not allowed:
        logger.info(
            "Usage Guard blocked Discord ID %s: %s",
            author.id,
            limit_message,
        )

        await send_reply(
            target,
            limit_message,
        )

        return

    try:
        async with channel.typing():

            # ------------------------------------------------
            # 2. Register / update UNICTO team member
            # ------------------------------------------------

            member, is_new_member = (
                await team_service.register_member(
                    author
                )
            )

            logger.info(
                "Team member registered | Discord ID: %s | New: %s",
                author.id,
                is_new_member,
            )

            # ------------------------------------------------
            # 3. Identify / create NOVA user
            # ------------------------------------------------

            user_id = await memory.get_or_create_user(
                author
            )

            logger.info(
                "NOVA user ID: %s | Discord ID: %s",
                user_id,
                author.id,
            )

            # ------------------------------------------------
            # 4. Identify / create conversation
            # ------------------------------------------------

            conversation_id = (
                await memory.get_or_create_conversation(
                    user_id,
                    channel.id,
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

            member_context = (
                f"Discord username: {author.name}\n"
                f"Display name: {author.display_name}\n"
            )

            conversation_context = (
                context_manager.build_prompt_context(
                    previous_messages,
                    member_context=member_context,
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
                author.id
            )

            await usage_guard.record_usage(
                author.id,
                model_used,
            )

            logger.info(
                "Usage recorded | Discord ID: %s | Model: %s",
                author.id,
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
                target,
                reply,
            )

    except Exception:
        logger.exception(
            "NOVA request failed."
        )

        await send_reply(
            target,
            "⚠️ I ran into a problem while processing that request. "
            "Please try again.",
        )


# ============================================================
# AI HANDLER REGISTRATION
# ============================================================

bot.nova_ai_handler = process_ai_request


# ============================================================
# START
# ============================================================


async def run_nova():
    logger.info(
        "Starting NOVA..."
    )

    await start_health_server()

    await bot.start(
        DISCORD_TOKEN
    )


def main():
    import asyncio

    asyncio.run(
        run_nova()
    )


if __name__ == "__main__":
    main()
