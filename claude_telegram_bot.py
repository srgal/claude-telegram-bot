import subprocess
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"   # Get from @BotFather
ALLOWED_USER_ID = 123456789                 # Your Telegram user ID (get from @userinfobot)

# user_id -> { "mode": "normal"/"dev", "history": [{"role": ..., "content": ...}] }
user_sessions = {}

MAX_HISTORY = 20  # מקסימום זוגות הודעות לזכור

SYSTEM_PROMPT_NORMAL = """אתה עוזר אישי חכם שרץ על Raspberry Pi 5.
תמיד בצע פעולות בפועל — אל תסביר רק איך לעשות אותן.

== פרטי ה-Pi ==
- משתמש: YOUR_PI_USERNAME
- IP מקומי: YOUR_PI_LOCAL_IP
- Tailscale: YOUR_TAILSCALE_IP

== Services קיימים ==
- bambu-monitor: מוניטור מדפסת Bambu (~/bambu_monitor.py)
- bambu-dashboard: דשבורד Flask פורט 8080 (~/bambu_dashboard.py)
- claude-telegram-bot: הבוט הזה (~/claude_telegram_bot.py)
- homeassistant: Home Assistant דוקר פורט 8123

== מדפסת Bambu A1 Mini ==
- IP: YOUR_PRINTER_IP, סיריאל: YOUR_PRINTER_SERIAL
- לוגים: journalctl -u bambu-monitor -n 50 --no-pager

== Home Assistant ==
- כתובת: http://YOUR_HA_IP:8123
- קונפיגורציה: /home/YOUR_PI_USERNAME/homeassistant/

== כללי ==
- תמיד ענה בעברית פשוטה
- בצע פעולות בפועל
- סכם תוצאות בצורה ברורה וידידותית
- היה תמציתי
"""

SYSTEM_PROMPT_DEV = """אתה עוזר טכני מקצועי שרץ על Raspberry Pi 5.
אתה במצב תכנות — החזר פלט גולמי מלא, לוגים מלאים, קוד מלא, שגיאות מלאות.

== פרטי ה-Pi ==
- משתמש: YOUR_PI_USERNAME
- IP מקומי: YOUR_PI_LOCAL_IP
- Tailscale: YOUR_TAILSCALE_IP

== Services קיימים ==
- bambu-monitor: מוניטור מדפסת Bambu (~/bambu_monitor.py)
- bambu-dashboard: דשבורד Flask פורט 8080 (~/bambu_dashboard.py)
- claude-telegram-bot: הבוט הזה (~/claude_telegram_bot.py)
- homeassistant: Home Assistant דוקר פורט 8123

== מדפסת Bambu A1 Mini ==
- IP: YOUR_PRINTER_IP, סיריאל: YOUR_PRINTER_SERIAL
- לוגים: journalctl -u bambu-monitor -n 50 --no-pager

== Home Assistant ==
- כתובת: http://YOUR_HA_IP:8123

== כללי ==
- החזר פלט גולמי מלא — לוגים, קוד, שגיאות, הכל
- אל תסכם ואל תקצר
- כתוב בעברית רק הסברים קצרים, הפלט עצמו באנגלית כפי שהוא
- כשכותבים קוד — הצג את הקוד המלא
- כשיש שגיאה — הצג את השגיאה המלאה עם stack trace
"""

def get_mode_keyboard():
    keyboard = [[KeyboardButton("🟢 מצב רגיל"), KeyboardButton("💻 מצב תכנות")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {"mode": None, "history": []}
    return user_sessions[user_id]

def build_prompt_with_history(history, new_message):
    """בנה prompt שכולל את כל ההיסטוריה + ההודעה החדשה"""
    if not history:
        return new_message

    lines = ["להלן היסטוריית השיחה שלנו עד כה:\n"]
    for msg in history:
        if msg["role"] == "user":
            lines.append(f"משתמש: {msg['content']}")
        else:
            lines.append(f"אתה (Claude): {msg['content']}")

    lines.append(f"\nעכשיו המשתמש שואל: {new_message}")
    lines.append("\nענה בהתאם להקשר השיחה המלא למעלה.")
    return "\n".join(lines)

def trim_history(history):
    """שמור מקסימום MAX_HISTORY זוגות אחרונים"""
    max_items = MAX_HISTORY * 2
    if len(history) > max_items:
        return history[-max_items:]
    return history

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return
    user_sessions[user_id] = {"mode": None, "history": []}
    await update.message.reply_text(
        "👋 שלום!\nבאיזה מצב תרצה לעבוד?",
        reply_markup=get_mode_keyboard()
    )

async def run_claude_with_history(user_id, user_message, session, app, chat_id):
    try:
        mode = session["mode"]
        system_prompt = SYSTEM_PROMPT_DEV if mode == "dev" else SYSTEM_PROMPT_NORMAL

        # בנה את ה-prompt עם ההיסטוריה
        full_prompt = build_prompt_with_history(session["history"], user_message)

        result = subprocess.run(
            [
                "claude",
                "-p", full_prompt,
                "--system-prompt", system_prompt,
                "--dangerously-skip-permissions"
            ],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=os.path.expanduser("~")
        )

        response = result.stdout.strip() or result.stderr.strip() or "לא התקבלה תשובה"

        # שמור בהיסטוריה
        session["history"].append({"role": "user", "content": user_message})
        session["history"].append({"role": "assistant", "content": response})
        session["history"] = trim_history(session["history"])

        # שלח תשובה (פצל אם ארוכה מדי)
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await app.bot.send_message(chat_id=chat_id, text=response[i:i+4096])
        else:
            await app.bot.send_message(chat_id=chat_id, text=response)

    except subprocess.TimeoutExpired:
        await app.bot.send_message(chat_id=chat_id, text="⏰ הבקשה לקחה יותר מדי זמן (מעל 10 דקות)")
    except Exception as e:
        await app.bot.send_message(chat_id=chat_id, text=f"❌ שגיאה: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ALLOWED_USER_ID:
        return

    text = update.message.text
    session = get_session(user_id)

    if text == "🟢 מצב רגיל":
        session["mode"] = "normal"
        session["history"] = []
        await update.message.reply_text("✅ מצב רגיל פעיל — שאל אותי כל דבר!")
        return
    elif text == "💻 מצב תכנות":
        session["mode"] = "dev"
        session["history"] = []
        await update.message.reply_text("💻 מצב תכנות פעיל — אקבל פלט גולמי מלא!")
        return
    elif text == "🗑 נקה שיחה":
        session["history"] = []
        await update.message.reply_text("🗑 השיחה נוקתה — מתחילים מחדש!")
        return

    if session["mode"] is None:
        await update.message.reply_text(
            "באיזה מצב תרצה לעבוד?",
            reply_markup=get_mode_keyboard()
        )
        return

    history_count = len(session["history"]) // 2
    history_note = f" (🧠 זוכר {history_count} הודעות)" if history_count > 0 else ""
    await update.message.reply_text(f"⏳ מעבד...{history_note}")

    asyncio.create_task(run_claude_with_history(
        user_id, text, session,
        context.application,
        update.effective_chat.id
    ))

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Claude Telegram Bot עם היסטוריה פועל...")
    app.run_polling()

if __name__ == "__main__":
    main()
