import logging
import os

from dotenv import load_dotenv

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
            "⚠️ I ran into a problem while processing that request. "
            "Please try again.",
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
            "⚠️ I ran into a problem while processing that request. "
            "Please try again.",
            mention_author=False,
        )


# ============================================================
# AI HANDLER REGISTRATION
# ============================================================

bot.nova_ai_handler = process_ai_request


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
