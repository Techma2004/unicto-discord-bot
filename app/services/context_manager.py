class ContextManager:
    """
    Keeps NOVA's conversation context within a safe size.
    """

    MAX_MESSAGES = 12
    MAX_MESSAGE_CHARS = 2000
    MAX_CONTEXT_CHARS = 12000

    def prepare_messages(self, messages):
        if not messages:
            return []

        prepared = []

        for message in messages[-self.MAX_MESSAGES:]:
            content = message["content"].strip()

            if len(content) > self.MAX_MESSAGE_CHARS:
                content = (
                    content[:self.MAX_MESSAGE_CHARS]
                    + "\n[message truncated]"
                )

            prepared.append({
                "role": message["role"],
                "content": content,
                "model": message.get("model"),
            })

        return prepared

    def build_prompt_context(self, messages):
        messages = self.prepare_messages(messages)

        if not messages:
            return ""

        lines = []

        for message in messages:
            if message["role"] == "user":
                speaker = "User"
            else:
                speaker = "NOVA"

            lines.append(
                f"{speaker}: {message['content']}"
            )

        context = "\n".join(lines)

        if len(context) > self.MAX_CONTEXT_CHARS:
            context = context[-self.MAX_CONTEXT_CHARS:]

        return (
            "\n\n--- CONVERSATION HISTORY ---\n"
            + context
            + "\n--- END CONVERSATION HISTORY ---\n"
        )


context_manager = ContextManager()
