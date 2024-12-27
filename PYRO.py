from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import xmlrpc.client
import requests
import os
import asyncio
import math
import hashlib

# Bot and Aria2 Configuration
API_ID = 29001415
API_HASH = "92152fd62ffbff12f057edc057f978f1"
BOT_TOKEN = "7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM"

ARIA2_RPC_SECRET = "your_aria2_secret"
ARIA2_RPC_URL = "http://localhost:6800/rpc"
DOWNLOAD_DIR = "./downloads"

DEEP_AI_API_KEY = "your_deepai_api_key"  # Get your API key from https://deepai.org/

# Aria2 RPC Client
try:
    aria2 = xmlrpc.client.ServerProxy(ARIA2_RPC_URL)
except Exception as e:
    print(f"Error connecting to Aria2 RPC: {e}")
    exit()

# Pyrogram Client
app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Global variables
CHUNK_SIZE = 1024 * 1024 * 1999  # Chunk size: ~2GB
download_statuses = {}
upload_statuses = {}
gids = []

# ---------------- Pornography Detection ------------------

async def detect_pornography(url_or_file_path):
    """
    Detects if a URL or file contains pornography using DeepAI's API.
    """
    try:
        endpoint = "https://api.deepai.org/api/nsfw-detector"
        headers = {"api-key": DEEP_AI_API_KEY}

        # Check if it's a URL
        if url_or_file_path.startswith("http://") or url_or_file_path.startswith("https://"):
            data = {"image": url_or_file_path}
            response = requests.post(endpoint, headers=headers, data=data)
        else:
            # Assume it's a local file
            with open(url_or_file_path, "rb") as file:
                files = {"image": file}
                response = requests.post(endpoint, headers=headers, files=files)

        response.raise_for_status()  # Raise HTTPError for bad responses
        result = response.json()
        if result.get("output") and result["output"].get("nsfw_score") > 0.5:
            return True  # Contains adult content
        return False  # Safe content
    except requests.exceptions.RequestException as e:
        print(f"Error detecting pornography: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during pornography detection: {e}")
        return False

# ---------------- Commands and Functions -----------------

@app.on_message(filters.command("add"))
async def add_download(client: Client, message: Message):
    """Handles adding a new download via URL."""
    if len(message.command) > 1:
        url = message.command[1]
        try:
            # Detect pornography in the URL
            await message.reply_text("Checking the URL for adult content...")
            is_porn = await detect_pornography(url)
            if is_porn:
                await message.reply_text("The URL contains adult content and has been blocked.")
                return

            # Add the download to Aria2
            options = {"dir": os.path.abspath(DOWNLOAD_DIR)}
            gid = aria2.aria2.addUri(ARIA2_RPC_SECRET, [url], options)
            if gid:
                gids.append(gid)
                await message.reply_text(f"Download added. GID: `{gid}`")
                asyncio.create_task(wait_for_download_and_upload(gid, message.chat.id))
            else:
                await message.reply_text("Failed to add the download to Aria2.")
        except xmlrpc.client.Fault as e:
            await message.reply_text(f"Aria2 error: {e}")
        except Exception as e:
            await message.reply_text(f"Failed to add download: {e}")
    else:
        await message.reply_text("Please provide a URL. Usage: `/add <url>`")


async def wait_for_download_and_upload(gid: str, chat_id: int):
    """Waits for an aria2 download to complete and uploads the file."""
    while True:
        try:
            status = aria2.aria2.tellStatus(ARIA2_RPC_SECRET, gid)
            if status["status"] == "complete":
                file_path = status["files"][0]["path"]

                # Detect pornography in the file
                await app.send_message(chat_id, "Scanning the file for adult content...")
                is_porn = await detect_pornography(file_path)
                if is_porn:
                    await app.send_message(chat_id, "The file contains adult content and has been blocked.")
                    os.remove(file_path)
                    break

                # Upload the file to Telegram
                await app.send_message(chat_id, "Download complete. Uploading...")
                await upload_to_telegram(chat_id, file_path)
                os.remove(file_path)
                break
            elif status["status"] in ["error", "removed"]:
                error_message = status.get("errorMessage", "Unknown error")
                await app.send_message(chat_id, f"Download failed: {error_message}")
                break
        except Exception as e:
            print(f"Error monitoring download for GID {gid}: {e}")
        await asyncio.sleep(5)


async def upload_to_telegram(chat_id: int, file_path: str):
    """Uploads a file to Telegram, splitting it if necessary."""
    file_size = os.path.getsize(file_path)
    num_chunks = math.ceil(file_size / CHUNK_SIZE)

    if num_chunks > 1:
        await app.send_message(
            chat_id,
            text="File is larger than 2GB. Splitting into multiple parts to upload."
        )

    with open(file_path, "rb") as f:
        for i in range(num_chunks):
            chunk_path = f"{file_path}.{i:03d}"  # e.g., filename.ext.001
            with open(chunk_path, "wb") as chunk_file:
                chunk_file.write(f.read(CHUNK_SIZE))

            await app.send_document(chat_id, document=chunk_path)
            os.remove(chunk_path)  # Clean up the chunk

    if num_chunks == 1:
        await app.send_document(chat_id, document=file_path)


@app.on_message(filters.command("stats"))
async def get_stats(client: Client, message: Message):
    """Gets and sends aria2 download stats."""
    try:
        global_stats = aria2.aria2.getGlobalStat(ARIA2_RPC_SECRET)
        message_text = f"**Download Stats:**\n" \
                       f"Download Speed: {int(global_stats['downloadSpeed']) / 1024:.2f} KB/s\n" \
                       f"Upload Speed: {int(global_stats['uploadSpeed']) / 1024:.2f} KB/s\n" \
                       f"Active Downloads: {global_stats['numActive']}\n" \
                       f"Waiting Downloads: {global_stats['numWaiting']}\n" \
                       f"Stopped Downloads: {global_stats['numStopped']}"
        await message.reply_text(message_text, parse_mode="markdown")
    except Exception as e:
        await message.reply_text(f"Error fetching stats: {e}")

# ---------------- Start the Bot -----------------
async def main():
    async with app:
        print("Bot is running...")
        await app.start()
        await idle()

if __name__ == "__main__":
    asyncio.run(main())
