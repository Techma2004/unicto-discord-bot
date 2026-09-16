import asyncio
import logging
import os

import discord
from dotenv import load_dotenv

from app.ai.router import GeminiRouter
from app.bot.client import NOVAClient
from app.health import start_health_server
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
    raise RuntimeError("DISCORD_TOKEN is not set in environment.")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in environment.")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
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
    prompt: str,
    conversation_context: str = "",
):
    """
    Send a prompt through the Gemini router.
    """

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
    """
    Return the Discord user from either a Message
    or an Interaction.
    """

    if isinstance(target, discord.Interaction):
        return target.user

    return target.author


def get_channel(target):
    """
    Return the Discord channel from either a Message
    or an Interaction.
    """

    return target.channel


# ============================================================
# DISCORD RESPONSE
# ============================================================

async def send_reply(
    target,
    text: str,
):
    """
    Send a response to either a Discord Message
    or a Discord Interaction.

    Discord messages have a 2000-character limit,
    so long responses are automatically split.
    """

    if not text:
        text = "I don't have a response for that yet."

    chunks = [
        text[index:index + 2000]
        for index in range(0, len(text), 2000)
    ]

    for chunk in chunks:

        if isinstance(target, discord.Interaction):

            # Interaction responses must be handled differently
            # depending on whether the initial response was sent.
            if not target.response.is_done():
                await target.response.send_message(chunk)
            else:
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
    prompt: str,
):
    """
    Submit a NOVA AI request to the request queue.

    Supports:
    - Discord Message
    - Discord Interaction
    """

    prompt = prompt.strip()

    if not prompt:
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
    prompt: str,
):
    """
    Actual NOVA AI workflow.

    Handles:

    1. Usage limits
    2. Team registration
    3. User memory
    4. Conversation memory
    5. Context building
    6. Gemini generation
    7. Usage recording
    8. Message persistence
    9. Discord response
    """

    author = get_author(target)
    channel = get_channel(target)

    # --------------------------------------------------------
    # 1. USAGE GUARD
    # --------------------------------------------------------

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
            # 2. REGISTER / UPDATE TEAM MEMBER
            # ------------------------------------------------

            member, is_new_member = (
                await team_service.register_member(
                    author
                )
            )

            logger.info(
                "Team member registered | "
                "Discord ID: %s | New: %s",
                author.id,
                is_new_member,
            )

            # ------------------------------------------------
            # 3. IDENTIFY / CREATE NOVA USER
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
            # 4. IDENTIFY / CREATE CONVERSATION
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
            # 5. LOAD PREVIOUS CONVERSATION
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
            # 6. BUILD CONTEXT
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
            # 7. ASK GEMINI
            # ------------------------------------------------

            reply, model_used = await ask_nova(
                prompt,
                conversation_context,
            )

            logger.info(
                "Gemini response generated | Model: %s",
                model_used,
            )

            # ------------------------------------------------
            # 8. RECORD SUCCESSFUL USAGE
            # ------------------------------------------------

            usage_guard.record_request(
                author.id
            )

            await usage_guard.record_usage(
                author.id,
                model_used,
            )

            logger.info(
                "Usage recorded | "
                "Discord ID: %s | Model: %s",
                author.id,
                model_used,
            )

            # ------------------------------------------------
            # 9. SAVE USER MESSAGE
            # ------------------------------------------------

            await memory.save_message(
                conversation_id,
                "user",
                prompt,
            )

            # ------------------------------------------------
            # 10. SAVE NOVA RESPONSE
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
            # 11. SEND RESPONSE
            # ------------------------------------------------

            await send_reply(
                target,
                reply,
            )

    except Exception:

        logger.exception(
            "NOVA request failed."
        )

        # Avoid masking the original error if Discord itself
        # fails while sending the error message.
        try:

            await send_reply(
                target,
                "⚠️ I ran into a problem while processing that request. "
                "Please try again.",
            )

        except Exception:

            logger.exception(
                "Failed to send NOVA error response."
            )


# ============================================================
# AI HANDLER REGISTRATION
# ============================================================

bot.nova_ai_handler = process_ai_request


# ============================================================
# START NOVA
# ============================================================

async def run_nova():
    """
    Start the NOVA health server and Discord client.

    The Discord connection automatically retries when a
    temporary network, gateway, or rate-limit problem occurs.
    """

    logger.info("========================================")
    logger.info("Starting NOVA...")
    logger.info("========================================")

    # --------------------------------------------------------
    # HEALTH SERVER
    # --------------------------------------------------------

    try:

        await start_health_server()

        logger.info(
            "Health server started successfully."
        )

    except Exception:

        logger.exception(
            "Failed to start health server."
        )

        raise

    # --------------------------------------------------------
    # DISCORD CONNECTION LOOP
    # --------------------------------------------------------

    while True:

        try:

            logger.info(
                "Connecting NOVA to Discord..."
            )

            await bot.start(
                DISCORD_TOKEN
            )

            logger.warning(
                "NOVA Discord connection closed."
            )

        # ----------------------------------------------------
        # HTTP / RATE LIMIT
        # ----------------------------------------------------

        except discord.HTTPException as error:

            retry_after = getattr(
                error,
                "retry_after",
                None,
            )

            response = getattr(
                error,
                "response",
                None,
            )

            logger.error(
                "Discord HTTP error | "
                "status=%s | retry_after=%s | "
                "response=%s | error=%s",
                error.status,
                retry_after,
                response,
                error,
            )

            if error.status == 429:

                wait_time = (
                    retry_after
                    if retry_after is not None
                    else 60
                )

                logger.warning(
                    "Discord rate limited NOVA. "
                    "Waiting %.1f seconds before retrying...",
                    wait_time,
                )

                await asyncio.sleep(
                    wait_time
                )

                continue

            logger.error(
                "Non-retryable Discord HTTP error."
            )

            raise

        # ----------------------------------------------------
        # INVALID TOKEN / AUTHENTICATION
        # ----------------------------------------------------

        except discord.LoginFailure:

            logger.exception(
                "NOVA failed Discord authentication. "
                "Check the DISCORD_TOKEN."
            )

            raise

        # ----------------------------------------------------
        # GATEWAY UNAVAILABLE
        # ----------------------------------------------------

        except discord.GatewayNotFound:

            logger.exception(
                "Discord Gateway could not be reached. "
                "Retrying in 30 seconds..."
            )

            await asyncio.sleep(30)

        # ----------------------------------------------------
        # GATEWAY CONNECTION CLOSED
        # ----------------------------------------------------

        except discord.ConnectionClosed as error:

            logger.warning(
                "Discord Gateway connection closed | "
                "code=%s | reason=%s",
                error.code,
                error,
            )

            logger.info(
                "Retrying Discord connection in 30 seconds..."
            )

            await asyncio.sleep(30)

        # ----------------------------------------------------
        # SHUTDOWN
        # ----------------------------------------------------

        except asyncio.CancelledError:

            logger.info(
                "NOVA shutdown requested."
            )

            raise

        # ----------------------------------------------------
        # UNEXPECTED ERROR
        # ----------------------------------------------------

        except Exception:

            logger.exception(
                "NOVA stopped unexpectedly. "
                "Waiting 30 seconds before retrying..."
            )

            await asyncio.sleep(30)


# ============================================================
# MAIN
# ============================================================

def main():
    asyncio.run(
        run_nova()
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
