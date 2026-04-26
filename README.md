# Claude Telegram Bot 🤖

A Telegram bot that runs Claude Code on a Raspberry Pi, allowing you to control and query your Pi through natural language conversations.

## Features
- 💬 Natural language interface in Hebrew (or any language)
- 🟢 Normal mode: friendly summaries
- 💻 Dev mode: raw full output for debugging
- 🧠 20-message conversation history
- ⏱️ 10-minute timeout for long-running commands

## Requirements
- Raspberry Pi with Claude Code installed
- Telegram bot token (from @BotFather)
- Python 3.10+

## Installation
```bash
pip install python-telegram-bot
```

## Configuration
Edit the constants at the top of `claude_telegram_bot.py`:
- `TELEGRAM_TOKEN` — your Telegram bot token
- `ALLOWED_USER_ID` — your Telegram user ID (get from @userinfobot)

## Usage
```bash
python3 claude_telegram_bot.py
```

## License
MIT
