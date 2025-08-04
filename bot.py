"""Telegram PoW Bot

This script implements a Telegram bot that requires new users to perform a
proof-of-work (PoW) before they are allowed to speak in a group.  When a
non-bot user joins a chat the bot restricts their ability to send messages,
generates a random challenge string and sends them a personalised link to a
small web page where they can compute a nonce.  Once the user posts the
correct nonce back into the chat the bot lifts the restriction.

The difficulty is adjustable via the ``DEFAULT_DIFFICULTY`` constant and the
web page host via the ``POW_BASE_URL`` environment variable.  See the
accompanying README for setup instructions.
"""

import os
import random
import string
import hashlib
from urllib.parse import quote

from telegram import ChatPermissions, Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Number of leading hexadecimal zero digits required for a valid PoW.
# The expected number of hashes grows exponentially with this number.
DEFAULT_DIFFICULTY = 2  # trivial by default; adjust as needed


# Base URL of the hosted PoW page.  Should point to your copy of pow.html.
POW_BASE_URL = os.getenv("POW_BASE_URL", "https://example.com/pow.html")

# In-memory store mapping (chat_id, user_id) to a (challenge, difficulty) tuple.
pending_challenges: dict[tuple[int, int], tuple[str, int]] = {}


def generate_challenge(length: int = 16) -> str:
    """Return a random alphanumeric challenge string of ``length`` characters."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def build_pow_url(message: str, difficulty: int) -> str:
    """Return a URL to the PoW page with the message and difficulty encoded."""
    return f"{POW_BASE_URL}?m={quote(message)}&d={difficulty}"


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the event when a new user joins the chat.

    When a non-bot user becomes a member, restrict their ability to send
    messages, generate a challenge and send them the verification URL.
    """
    chat_member = update.chat_member
    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status

    # We only care about users who transition to 'member' status.  Ignore
    # promotions, left/kicked events, and bots.
    if new_status == "member" and old_status not in ("member", "administrator", "creator"):
        user = chat_member.new_chat_member.user
        if user.is_bot:
            return

        chat_id = update.effective_chat.id
        user_id = user.id

        # Restrict the new user so they cannot send messages until verified.
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
            )
        except Exception:
            # If we cannot restrict the user (e.g. insufficient rights) we
            # continue anyway.  The PoW flow will still work but the user won't
            # be muted.
            pass

        # Generate a challenge and store it along with difficulty.
        challenge = generate_challenge()
        difficulty = DEFAULT_DIFFICULTY
        pending_challenges[(chat_id, user_id)] = (challenge, difficulty)

        # Construct personalised URL.
        url = build_pow_url(challenge, difficulty)

        # Send welcome and instructions.
        welcome_text = (
            f"Hello {user.mention_html()}, welcome!\n\n"
            f"To start chatting you need to complete a simple proof-of-work challenge. "
            f"Please click the link below and press “Start Mining”. When a nonce is found, "
            f"copy it and send it here.\n\n"
            f"{url}\n\n"
            f"If the link does not open automatically, copy it into your browser's address bar."
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def handle_user_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process messages sent by users who may be responding with their nonce.

    If the sender has a pending challenge, validate the nonce.  If valid, lift
    restrictions; otherwise prompt them to try again.
    """
    message = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id
    key = (chat_id, user.id)

    if key not in pending_challenges:
        # No pending PoW for this user in this chat, ignore
        return

    nonce_str = message.text.strip()
    # Expect a decimal integer for the nonce
    if not nonce_str.isdigit():
        await message.reply_text("Please reply with just the nonce (a number) from the proof-of-work page.")
        return

    challenge, difficulty = pending_challenges[key]

    # Compute SHA-256 of message + nonce
    digest_hex = hashlib.sha256((challenge + nonce_str).encode("utf-8")).hexdigest()
    if digest_hex.startswith("0" * difficulty):
        # Success: remove challenge and unrestrict user
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
        await message.reply_text(
            "❌ That nonce is incorrect. Double-check that you copied it correctly from the proof-of-work page and try again."
        )


def main() -> None:
    """Entry point for the bot.  Creates the application and registers handlers."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "The BOT_TOKEN environment variable must be set with your Telegram bot token."
        )

    app = ApplicationBuilder().token(token).build()
    # Listen for chat member updates (new members)
    app.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    # Listen for text messages that are not commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_reply))
    # Start polling
    app.run_polling()


if __name__ == "__main__":
    main()