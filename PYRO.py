from pyrogram import Client, filters
from pyrogram.types import Message
import xmlrpc.client
import os
import asyncio

# Aria2 RPC settings
ARIA2_RPC_SECRET = "your_aria2_secret"
ARIA2_RPC_URL = "http://localhost:6800/rpc"

# Telegram Bot settings
API_ID = 29001415
API_HASH = "92152fd62ffbff12f057edc057f978f1"
BOT_TOKEN = "7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM"

# Initialize Pyrogram Client
app = Client(
    "aria2_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Aria2 RPC Client
aria2 = xmlrpc.client.ServerProxy(ARIA2_RPC_URL)

# Function to fetch aria2 stats
@app.on_message(filters.command("stats"))
async def get_stats(client: Client, message: Message):
    """Fetch and display download stats from aria2."""
    try:
        stats = aria2.aria2.getGlobalStat(ARIA2_RPC_SECRET)
        message_text = (
            "**Aria2 Download Stats:**\n\n"
            f"**Download Speed:** `{int(stats['downloadSpeed']) / 1024:.2f} KB/s`\n"
            f"**Upload Speed:** `{int(stats['uploadSpeed']) / 1024:.2f} KB/s`\n"
            f"**Active Downloads:** `{stats['numActive']}`\n"
            f"**Waiting Downloads:** `{stats['numWaiting']}`\n"
            f"**Stopped Downloads:** `{stats['numStopped']}`"
        )
        # Use the split text approach to avoid message too long error
        if len(message_text) > 4096:
            parts = [message_text[i:i+4096] for i in range(0, len(message_text), 4096)]
            for part in parts:
                await message.reply_text(part, parse_mode="markdown")
        else:
            await message.reply_text(message_text, parse_mode="markdown")
    except Exception as e:
        await message.reply_text(f"Error fetching stats: {e}")

# Function to add a download
@app.on_message(filters.command("add"))
async def add_download(client: Client, message: Message):
    """Add a new download to aria2 using a URL."""
    if len(message.command) > 1:
        url = message.command[1]
        try:
            gid = aria2.aria2.addUri(ARIA2_RPC_SECRET, [url])
            await message.reply_text(f"Download added successfully! GID: `{gid}`", parse_mode="markdown")
        except Exception as e:
            await message.reply_text(f"Error adding download: {e}")
    else:
        await message.reply_text("Please provide a URL to download. Usage: /add <URL>")

# Function to cancel a download
@app.on_message(filters.command("cancel"))
async def cancel_download(client: Client, message: Message):
    """Cancel a download by GID."""
    if len(message.command) > 1:
        gid = message.command[1]
        try:
            removed = aria2.aria2.remove(ARIA2_RPC_SECRET, gid)
            if removed:
                await message.reply_text(f"Download canceled successfully! GID: `{gid}`", parse_mode="markdown")
            else:
                await message.reply_text(f"Failed to cancel download for GID: `{gid}`", parse_mode="markdown")
        except Exception as e:
            await message.reply_text(f"Error canceling download: {e}")
    else:
        await message.reply_text("Please provide a GID to cancel. Usage: /cancel <GID>")

# Function to handle .torrent files
@app.on_message(filters.document)
async def handle_torrent(client: Client, message: Message):
    """Add a .torrent file to aria2."""
    if message.document.mime_type == "application/x-bittorrent":
        try:
            file = await message.download()
            with open(file, "rb") as torrent_file:
                torrent_data = xmlrpc.client.Binary(torrent_file.read())
            gid = aria2.aria2.addTorrent(ARIA2_RPC_SECRET, torrent_data)
            os.remove(file)  # Clean up the downloaded file
            await message.reply_text(f"Torrent added successfully! GID: `{gid}`", parse_mode="markdown")
        except Exception as e:
            await message.reply_text(f"Error adding torrent: {e}")
    else:
        await message.reply_text("Please send a valid .torrent file.")

# Start the bot
async def main():
    try:
        async with app:
            print("Bot is running...")
            await app.run()
    except Exception as e:
        print(f"Error starting the bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
