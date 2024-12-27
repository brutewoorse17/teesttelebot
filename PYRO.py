import asyncio
import aria2p
import os
from pyrogram import Client, filters
from pyrogram.types import Message

# Set up the Aria2 connection (without RPC secret)
aria2 = aria2p.API(
    aria2p.Client(
        host="http://127.0.0.1",  # Aria2 server IP, change if needed
        port=6800  # Aria2 RPC server port
    )
)

# Create Pyrogram client
API_ID = 29001415
API_HASH = "92152fd62ffbff12f057edc057f978f1"
BOT_TOKEN = "7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM"

app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Global dictionary to store download statuses
download_statuses = {}

async def add_download(url: str):
    """Add a download to Aria2"""
    try:
        download = aria2.add(uri=url)
        print(f"Download added with GID: {download.gid}")
        download_statuses[download.gid] = {"status": "active", "progress": 0, "file_path": None}
        return download.gid
    except Exception as e:
        print(f"Error adding download: {e}")
        return None

async def monitor_download(gid: str, chat_id: int):
    """Monitor the download progress and upload once completed"""
    while True:
        try:
            status = aria2.get_download_status(gid)
            download_statuses[gid]['progress'] = (status.completedLength / status.totalLength) * 100
            if status.status == "complete":
                download_statuses[gid]['file_path'] = status.files[0].filePath  # Get the file path
                print(f"Download complete: {gid}, file saved at {status.files[0].filePath}")
                download_statuses[gid]['status'] = "complete"
                # Upload the file to Telegram after download completion
                await upload_file_to_telegram(chat_id, status.files[0].filePath)
                break
            elif status.status == "failed":
                print(f"Download failed: {gid}")
                download_statuses[gid]['status'] = "failed"
                break
            else:
                print(f"GID: {gid} | Progress: {download_statuses[gid]['progress']:.2f}%")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error monitoring download {gid}: {e}")
            break

async def upload_file_to_telegram(chat_id: int, file_path: str):
    """Upload the file to Telegram after download completion"""
    try:
        # Check if the file exists
        if os.path.exists(file_path):
            # Send the file to the specified chat
            print(f"Uploading {file_path} to Telegram chat {chat_id}...")
            await app.send_document(chat_id, file_path)
            print(f"File {file_path} uploaded successfully.")
        else:
            print(f"File {file_path} not found!")
    except Exception as e:
        print(f"Error uploading file to Telegram: {e}")

@app.on_message(filters.command("add_download"))
async def add_download_command(client: Client, message: Message):
    """Handles adding a new download via command."""
    url = message.text.split(" ", 1)[1] if len(message.command) > 1 else None
    if url:
        gid = await add_download(url)
        if gid:
            await message.reply_text(f"Download added with GID: {gid}")
            # Monitor download for this GID and upload to the user chat once complete
            await monitor_download(gid, message.chat.id)
        else:
            await message.reply_text("Error adding the download.")
    else:
        await message.reply_text("Please provide a valid URL. Usage: /add_download <URL>")

@app.on_message(filters.command("download_status"))
async def download_status_command(client: Client, message: Message):
    """Handles checking the download status via command."""
    gid = message.text.split(" ", 1)[1] if len(message.command) > 1 else None
    if gid and gid in download_statuses:
        status = download_statuses[gid]
        await message.reply_text(
            f"Download GID: {gid}\nStatus: {status['status']}\nProgress: {status['progress']:.2f}%"
        )
    else:
        await message.reply_text("Invalid or missing GID.")

@app.on_message(filters.command("cancel_download"))
async def cancel_download_command(client: Client, message: Message):
    """Handles canceling a download via command."""
    gid = message.text.split(" ", 1)[1] if len(message.command) > 1 else None
    if gid and gid in download_statuses:
        try:
            aria2.remove(gid)
            download_statuses[gid]['status'] = 'cancelled'
            await message.reply_text(f"Download {gid} has been cancelled.")
        except Exception as e:
            await message.reply_text(f"Error canceling the download: {e}")
    else:
        await message.reply_text("Invalid or missing GID.")

# Ensure everything runs on the same event loop
async def main():
    loop = asyncio.get_event_loop()
    # Start the Pyrogram client and Aria2 monitoring tasks
    await asyncio.gather(
        app.start(),
        loop.run_in_executor(None, lambda: asyncio.run(aria2_client_monitor()))
    )

async def aria2_client_monitor():
    """This function will allow Aria2 client to run alongside the Pyrogram bot."""
    # Simulating running the Aria2p monitoring logic in a separate async task
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
