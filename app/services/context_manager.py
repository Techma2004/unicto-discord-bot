class ContextManager:
    """
    Builds structured, size-limited context for NOVA.
    """

    MAX_MESSAGES = 12
    MAX_MESSAGE_CHARS = 2000
    MAX_CONTEXT_CHARS = 12000

    def prepare_messages(self, messages):
        if not messages:
            return []

        prepared = []

        for message in messages[-self.MAX_MESSAGES:]:
            content = str(
                message.get("content", "")
            ).strip()

            if not content:
                continue

            if len(content) > self.MAX_MESSAGE_CHARS:
                content = (
                    content[:self.MAX_MESSAGE_CHARS]
                    + "\n[message truncated]"
                )

            prepared.append({
                "role": message.get("role", "user"),
                "content": content,
                "model": message.get("model"),
            })

        return prepared

    def build_conversation_history(self, messages):
        messages = self.prepare_messages(messages)

        if not messages:
            return ""

        lines = []

        for message in messages:
            speaker = (
                "User"
                if message["role"] == "user"
                else "NOVA"
            )

            lines.append(
                f"{speaker}: {message['content']}"
            )

        return "\n".join(lines)

    def build_prompt_context(
        self,
        messages,
        member_context="",
        project_context="",
        memory_context="",
    ):
        sections = []

        if member_context.strip():
            sections.append(
                "--- MEMBER CONTEXT ---\n"
                + member_context.strip()
                + "\n--- END MEMBER CONTEXT ---"
            )

        if project_context.strip():
            sections.append(
                "--- PROJECT CONTEXT ---\n"
                + project_context.strip()
                + "\n--- END PROJECT CONTEXT ---"
            )

        if memory_context.strip():
            sections.append(
                "--- RELEVANT MEMORY ---\n"
                + memory_context.strip()
                + "\n--- END RELEVANT MEMORY ---"
            )

        conversation_history = (
            self.build_conversation_history(messages)
        )

        if conversation_history:
            sections.append(
                "--- CONVERSATION HISTORY ---\n"
                + conversation_history
                + "\n--- END CONVERSATION HISTORY ---"
            )

        if not sections:
            return ""

        context = "\n\n".join(sections)

        if len(context) > self.MAX_CONTEXT_CHARS:
            context = context[-self.MAX_CONTEXT_CHARS:]

        return "\n\n" + context + "\n"


context_manager = ContextManager()
