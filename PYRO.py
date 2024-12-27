from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import xmlrpc.client
import requests
import os
import asyncio
import math

# Bot and Aria2 Configuration
API_ID = 29001415
API_HASH = "92152fd62ffbff12f057edc057f978f1"
BOT_TOKEN = "7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM"

ARIA2_RPC_SECRET = "your_aria2_secret"
ARIA2_RPC_URL = "http://localhost:6800/rpc"
DOWNLOAD_DIR = "./downloads"

DEEP_AI_API_KEY = "your_deepai_api_key"

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

CHUNK_SIZE = 1024 * 1024 * 1999  # ~2GB
gids = []

# ---------------- Pornography Detection ------------------

async def detect_pornography(url_or_file_path):
    try:
        endpoint = "https://api.deepai.org/api/nsfw-detector"
        headers = {"api-key": DEEP_AI_API_KEY}
        if url_or_file_path.startswith("http://") or url_or_file_path.startswith("https://"):
            data = {"image": url_or_file_path}
            response = requests.post(endpoint, headers=headers, data=data)
        else:
            with open(url_or_file_path, "rb") as file:
                files = {"image": file}
                response = requests.post(endpoint, headers=headers, files=files)

        response.raise_for_status()
        result = response.json()
        return result.get("output", {}).get("nsfw_score", 0) > 0.5
    except Exception as e:
        print(f"Porn detection error: {e}")
        return False

# ---------------- Commands -----------------

@app.on_message(filters.command("add"))
async def add_download(client: Client, message: Message):
    if len(message.command) > 1:
        url = message.command[1]
        try:
            await message.reply_text("Checking the URL for adult content...")
            is_porn = await detect_pornography(url)
            if is_porn:
                await message.reply_text("The URL contains adult content and has been blocked.")
                return

            options = {"dir": os.path.abspath(DOWNLOAD_DIR)}
            gid = aria2.aria2.addUri(ARIA2_RPC_SECRET, [url], options)
            if gid:
                gids.append(gid)
                await message.reply_text(f"Download added. GID: `{gid}`")
                asyncio.create_task(wait_for_download_and_upload(gid, message.chat.id))
            else:
                await message.reply_text("Failed to add the download to Aria2.")
        except Exception as e:
            await message.reply_text(f"Error: {e}")
    else:
        await message.reply_text("Please provide a URL. Usage: `/add <url>`")


async def wait_for_download_and_upload(gid: str, chat_id: int):
    while True:
        try:
            status = aria2.aria2.tellStatus(ARIA2_RPC_SECRET, gid)
            if status["status"] == "complete":
                file_path = status["files"][0]["path"]

                await app.send_message(chat_id, "Scanning the file for adult content...")
                is_porn = await detect_pornography(file_path)
                if is_porn:
                    await app.send_message(chat_id, "The file contains adult content and has been blocked.")
                    os.remove(file_path)
                    break

                await app.send_message(chat_id, "Download complete. Uploading...")
                await upload_to_telegram(chat_id, file_path)
                os.remove(file_path)
                break
            elif status["status"] in ["error", "removed"]:
                await app.send_message(chat_id, f"Download failed: {status.get('errorMessage', 'Unknown error')}")
                break
        except Exception as e:
            print(f"Error monitoring download: {e}")
        await asyncio.sleep(5)


async def upload_to_telegram(chat_id: int, file_path: str):
    file_size = os.path.getsize(file_path)
    num_chunks = math.ceil(file_size / CHUNK_SIZE)

    if num_chunks > 1:
        await app.send_message(chat_id, text="File is larger than 2GB. Splitting into parts.")

    with open(file_path, "rb") as f:
        for i in range(num_chunks):
            chunk_path = f"{file_path}.{i:03d}"
            with open(chunk_path, "wb") as chunk_file:
                chunk_file.write(f.read(CHUNK_SIZE))
            await app.send_document(chat_id, document=chunk_path)
            os.remove(chunk_path)

    if num_chunks == 1:
        await app.send_document(chat_id, document=file_path)


@app.on_message(filters.command("stats"))
async def get_stats(client: Client, message: Message):
    try:
        stats = aria2.aria2.getGlobalStat(ARIA2_RPC_SECRET)
        message_text = (
            f"**Download Stats:**\n"
            f"Download Speed: {int(stats['downloadSpeed']) / 1024:.2f} KB/s\n"
            f"Upload Speed: {int(stats['uploadSpeed']) / 1024:.2f} KB/s\n"
            f"Active Downloads: {stats['numActive']}\n"
            f"Waiting Downloads: {stats['numWaiting']}\n"
            f"Stopped Downloads: {stats['numStopped']}"
        )
        await message.reply_text(message_text)
    except Exception as e:
        await message.reply_text(f"Error fetching stats: {e}")

# ---------------- Start the Bot -----------------
if __name__ == "__main__":
    app.run()
