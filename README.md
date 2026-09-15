# NOVA — UNICTO Discord AI Assistant

NOVA is the official AI-powered Discord assistant for **UNICTO (United Computer Tech Organization)**.

It is designed to support the UNICTO community with AI assistance, project management, tasks, memory, team management, and persistent conversation context.

## 🚀 Features

* 🤖 Gemini-powered AI conversations
* 💬 Discord message and `/ask` command support
* 🧠 Persistent conversation memory
* 👥 UNICTO team-member registration
* 📁 Project management
* 📋 Task management
* 📝 Project memory and notes
* 🔐 Role-based permissions
* 📊 Usage tracking and limits
* 🔄 Gemini model fallback system
* ⚡ Asynchronous request queue
* 🗄️ PostgreSQL database support

## 🏗️ Project Structure

```text
unicto-discord-bot/
├── app/
│   ├── ai/
│   │   ├── prompts.py
│   │   └── router.py
│   │
│   ├── bot/
│   │   ├── client.py
│   │   ├── events.py
│   │   └── commands/
│   │       ├── ai.py
│   │       ├── general.py
│   │       ├── memory.py
│   │       ├── projects.py
│   │       └── tasks.py
│   │
│   ├── database/
│   │   ├── db.py
│   │   ├── init_db.py
│   │   ├── models.py
│   │   └── test_connection.py
│   │
│   ├── services/
│   │   ├── context_manager.py
│   │   ├── memory.py
│   │   ├── permissions.py
│   │   ├── project_members.py
│   │   ├── project_memory.py
│   │   ├── projects.py
│   │   ├── request_queue.py
│   │   ├── tasks.py
│   │   ├── team.py
│   │   └── usage_guard.py
│   │
│   └── main.py
│
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

## 🛠️ Tech Stack

| Component       | Technology        |
| --------------- | ----------------- |
| Language        | Python 3.11       |
| Discord         | discord.py        |
| AI              | Google Gemini API |
| Database        | PostgreSQL        |
| ORM             | SQLAlchemy        |
| Async Driver    | asyncpg           |
| Package Manager | uv                |
| Hosting         | Render            |
| Source Control  | GitHub            |

## 📋 Requirements

Before developing NOVA locally, install:

* Python 3.11
* `uv`
* Git
* A Discord bot application
* Google Gemini API access
* PostgreSQL database

## ⚙️ Local Setup

Clone the repository:

```bash
git clone https://github.com/Techma2004/unicto-discord-bot.git
cd unicto-discord-bot
```

Create the Python environment:

```bash
uv venv --python 3.11
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
uv sync
```

## 🔐 Environment Variables

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=your_postgresql_connection_string
```

**Never commit `.env` or API keys to GitHub.**

The repository already ignores `.env` through `.gitignore`.

## 🗄️ Database Setup

Initialize the NOVA database tables:

```bash
python -m app.database.init_db
```

Test the database connection:

```bash
python -m app.database.test_connection
```

NOVA uses tables prefixed with:

```text
nova_
```

This keeps NOVA's database structures separate from legacy UNICTO services.

## ▶️ Running NOVA Locally

From the project root:

```bash
source .venv/bin/activate
python -m app.main
```

A successful startup should show that NOVA has connected to Discord.

## 🤖 Discord Commands

### AI

```text
!ask <message>
/ask <message>
```

NOVA can also respond when directly mentioned in supported Discord channels.

### General

```text
!ping
```

### Projects

```text
!project create <name> | <description>
!project list
!project info <name>
!project delete <name>
!project member list <name>
!project member add <name> @user [role]
!project member remove <name> @user
```

### Tasks

Task commands are provided through the task command module and operate within NOVA projects.

### Memory

Memory commands allow authorized users to manage project-related information stored by NOVA.

## 🔐 Permissions

NOVA uses Discord server roles as the primary source of project-management permissions.

Current role mapping:

| Discord Role      | NOVA Role   |
| ----------------- | ----------- |
| Founder 👑        | Owner       |
| Administrator 🛡️ | Manager     |
| Moderator 🔨      | Moderator   |
| Developer 💻      | Developer   |
| Designer 🎨       | Designer    |
| Team Member 🤝    | Member      |
| Contributor 🌟    | Contributor |

Founder, Administrator, and Moderator roles have project-management privileges.

Developer, Designer, Team Member, and Contributor roles have normal project/work access.

## 🧠 AI Architecture

NOVA uses a Gemini model router with fallback support.

Current model order:

```text
gemini-3.8-flash
        ↓
gemini-3.5-flash-lite
        ↓
gemini-3.1-flash-lite
```

If a model encounters a quota, rate-limit, server, or network problem, the router can temporarily cool down that model and attempt another available model.

## 🧵 Request Queue

AI requests are processed through NOVA's asynchronous request queue.

This helps prevent multiple users from overwhelming the bot and provides controlled concurrency.

The queue currently starts with a limited number of workers suitable for the project's low-resource development environment.

## 🧠 Conversation Context

NOVA stores recent conversation messages and builds context before sending a request to Gemini.

The context manager limits:

* Number of previous messages
* Maximum message size
* Maximum total context size

This helps control token usage and prevents unnecessarily large AI requests.

## 🔒 Security Rules

UNICTO developers working on NOVA should follow these rules:

1. **Never commit API keys or Discord tokens.**
2. Never place secrets directly inside Python source code.
3. Never share `.env` files.
4. Do not modify legacy database tables without approval.
5. Keep NOVA database tables under the `nova_` namespace.
6. Test database changes before committing them.
7. Run the compiler before pushing changes.
8. Keep production credentials out of GitHub.
9. Review changes before pushing to `main`.

## 🧪 Before Committing

Run:

```bash
python -m compileall app
```

Then check:

```bash
git status
```

Review the files that will be committed:

```bash
git diff
```

Make sure `.env` is not tracked:

```bash
git ls-files
```

Then commit:

```bash
git add .
git commit -m "Describe your change"
```

Push:

```bash
git push
```

## 🤝 Contributing

UNICTO developers are encouraged to improve NOVA while keeping the architecture organized.

Recommended workflow:

```text
Issue / Feature
      ↓
Development branch
      ↓
Implementation
      ↓
Local testing
      ↓
Code review
      ↓
Merge
      ↓
Deployment
```

Avoid making large unrelated changes in a single commit.

Keep commits focused and descriptive.

## 🌐 Deployment

NOVA is designed to run as a continuously running Discord bot.

The current deployment target is **Render**.

Production environment variables should be configured through the hosting provider rather than committed to the repository.

## 📌 Project Status

NOVA is currently under active development.

Core systems currently include:

* Discord connection
* Gemini AI
* AI fallback routing
* Conversation memory
* PostgreSQL persistence
* Project management
* Task management
* Team management
* Role-based permissions
* Usage controls
* Request queue

Additional features will be introduced as the UNICTO platform evolves.

## 🏢 About UNICTO

**UNICTO — United Computer Tech Organization**

NOVA is being developed as part of the UNICTO technology ecosystem.

The project is intended to provide UNICTO members with an AI-assisted workspace for communication, collaboration, project management, and development.

---

**Built for UNICTO by the UNICTO development team.** 🤖
