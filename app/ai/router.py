import asyncio
import logging
import time

from google import genai

from app.ai.prompts import SYSTEM_PROMPT


class GeminiRouter:
    """
    Handles Gemini model selection, fallback, and cooldowns.
    """

    def __init__(self, api_key, models=None):
        self.logger = logging.getLogger("nova")

        self.gemini = genai.Client(
            api_key=api_key
        )

        self.models = models or [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ]

        self.model_cooldowns = {}

    def model_is_available(self, model):
        cooldown_until = self.model_cooldowns.get(
            model,
            0,
        )

        return time.monotonic() >= cooldown_until

    def cooldown_model(self, model, seconds):
        self.model_cooldowns[model] = (
            time.monotonic() + seconds
        )

        self.logger.warning(
            "Model %s cooled down for %s seconds",
            model,
            seconds,
        )

    def get_cooldown_remaining(self, model):
        remaining = (
            self.model_cooldowns.get(model, 0)
            - time.monotonic()
        )

        return max(0, int(remaining))

    def classify_error(self, error):
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

    async def ask(
        self,
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

        for model in self.models:

            if not self.model_is_available(model):

                remaining = (
                    self.get_cooldown_remaining(model)
                )

                self.logger.info(
                    "Skipping %s (cooldown: %ss)",
                    model,
                    remaining,
                )

                continue

            try:

                self.logger.info(
                    "Trying Gemini model: %s",
                    model,
                )

                response = await asyncio.to_thread(
                    self.gemini.models.generate_content,
                    model=model,
                    contents=full_prompt,
                )

                text = response.text

                if not text:
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                self.logger.info(
                    "Gemini response successful using %s",
                    model,
                )

                return text, model

            except Exception as error:

                error_type = self.classify_error(
                    error
                )

                self.logger.warning(
                    "Gemini %s failed: %s | %s",
                    model,
                    error_type,
                    error,
                )

                if error_type == "daily_quota":

                    self.cooldown_model(
                        model,
                        20 * 60 * 60,
                    )

                elif error_type == "rate_limit":

                    self.cooldown_model(
                        model,
                        90,
                    )

                elif error_type == "server":

                    self.cooldown_model(
                        model,
                        60,
                    )

                elif error_type == "network":

                    self.cooldown_model(
                        model,
                        30,
                    )

                else:
                    raise

        raise RuntimeError(
            "All NOVA AI models are currently unavailable."
        )
