import os
import random
import string
import hashlib
from urllib.parse import quote

from telegram import (
    ChatPermissions,
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CommandHandler,
)

DEFAULT_DIFFICULTY = 2  # Adjust as needed
POW_BASE_URL = os.getenv("POW_BASE_URL", "https://jdr377.github.io/telegram-pow-page/pow.html")

pending_challenges: dict[tuple[int, int], tuple[str, int]] = {}

def generate_challenge(length: int = 16) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

def build_pow_url(message: str, difficulty: int) -> str:
    return f"{POW_BASE_URL}?m={quote(message)}&d={difficulty}"

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_member = update.chat_member
    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status

    if new_status == "member" and old_status not in ("member", "administrator", "creator"):
        user = chat_member.new_chat_member.user
        if user.is_bot:
            return

        chat_id = update.effective_chat.id
        user_id = user.id

        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
            )
        except Exception:
            pass

        challenge = generate_challenge()
        difficulty = DEFAULT_DIFFICULTY
        pending_challenges[(chat_id, user_id)] = (challenge, difficulty)
        url = build_pow_url(challenge, difficulty)

        welcome_text = (
            f"Hello {user.mention_html()}, welcome!\n\n"
            f"To start chatting you need to complete a simple proof-of-work challenge.\n"
            f"Click the button below to open the mining page. Once you find a nonce, paste it here."
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🧠 Start Mining", url=url)]
        ])

        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

async def trigger_pow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
        )
    except Exception:
        pass

    challenge = generate_challenge()
    difficulty = DEFAULT_DIFFICULTY
    pending_challenges[(chat_id, user_id)] = (challenge, difficulty)
    url = build_pow_url(challenge, difficulty)

    text = (
        f"Manual PoW triggered.\n\n"
        f"Click the button below to open the mining page, then paste the nonce here."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Start Mining", url=url)]
    ])

    await update.message.reply_text(text, reply_markup=keyboard)

async def handle_user_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id
    key = (chat_id, user.id)

    if key not in pending_challenges:
        return

    nonce_str = message.text.strip()
    if not nonce_str.isdigit():
        await message.reply_text("Please reply with just the nonce (a number) from the proof-of-work page.")
        return

    challenge, difficulty = pending_challenges[key]
    digest_hex = hashlib.sha256((challenge + nonce_str).encode("utf-8")).hexdigest()

    if digest_hex.startswith("0" * difficulty):
        pending_challenges.pop(key, None)
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
        except Exception:
            pass
        await message.reply_text("✅ Verification successful! You may now speak in this chat.")
    else:
        await message.reply_text("❌ That nonce is incorrect. Try again.")

async def restrict_user(context, chat_id, user_id):
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
        )
    except Exception as e:
        print(f"Restrict failed: {e}")


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 I'm alive.")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    target = None
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    elif context.args:
        username = context.args[0].lstrip('@')
        for member in await context.bot.get_chat_administrators(chat_id):
            if member.user.username == username:
                target = member.user
                break

    if not target:
        await update.message.reply_text("❌ Usage: /mute (reply to user or mention @username)")
        return

    await restrict_user(context, chat_id, target.id)
    await update.message.reply_text(f"🔇 {target.mention_html()} has been muted.", parse_mode=ParseMode.HTML)

async def new_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id

    challenge = generate_challenge()
    difficulty = DEFAULT_DIFFICULTY
    pending_challenges[(chat_id, user_id)] = (challenge, difficulty)

    await restrict_user(context, chat_id, user_id)

    url = build_pow_url(challenge, difficulty)
    text = f"🔐 New challenge issued.\n\n{url}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Start Mining", url=url)]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("The BOT_TOKEN environment variable must be set.")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_reply))
    app.add_handler(CommandHandler("triggerpow", trigger_pow))
    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("new", new_challenge))
    app.run_polling()

if __name__ == "__main__":
    main()
