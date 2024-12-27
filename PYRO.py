import os
import asyncio
import logging
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from aria2p import API, Client as Aria2Client, Download

# Enable logging
logging.basicConfig(level=logging.INFO)

# Your bot's credentials
api_id = '29001415'  # Replace with your API ID
api_hash = '92152fd62ffbff12f057edc057f978f1'  # Replace with your API Hash
bot_token = '7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM'  # Replace with your Bot Token

# Directory to temporarily save downloaded files
TEMP_DOWNLOAD_PATH = "./downloads"

# Ensure the directory exists
if not os.path.exists(TEMP_DOWNLOAD_PATH):
    os.makedirs(TEMP_DOWNLOAD_PATH)

# Create a Pyrogram client
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Connect to aria2 RPC
aria2 = API(
    Aria2Client(host="http://localhost", port=6800, secret="")
)

# Function to ensure aria2c is running
def start_aria2c_daemon():
    try:
        # Check if aria2c is already running
        result = subprocess.run(["pgrep", "-x", "aria2c"], stdout=subprocess.PIPE)
        if result.returncode == 0:
            logging.info("aria2c is already running.")
            return

        # Start aria2c with RPC enabled
        subprocess.Popen([
            "aria2c",
            "--enable-rpc",
            "--rpc-listen-all=true",
            "--rpc-allow-origin-all=true",
            "--daemon"
        ])
        logging.info("aria2c daemon started successfully!")
    except FileNotFoundError:
        logging.error("aria2c is not installed. Please install aria2c and try again.")
        raise
    except Exception as e:
        logging.error(f"Failed to start aria2c daemon: {str(e)}")
        raise


# Download using aria2p with timeout
async def download_with_aria2p(link: str, message: Message):
    try:
        # Add the download to aria2
        downloads = aria2.add(link, options={"dir": TEMP_DOWNLOAD_PATH})
        download = downloads[0] if isinstance(downloads, list) else downloads

        # Monitor download progress
        previous_message = f"Started download: {download.name}"
        await message.edit_text(previous_message)

        timeout = 600  # 10 minutes timeout
        elapsed_time = 0
        interval = 2  # Check progress every 2 seconds

        while not download.is_complete and not download.has_failed:
            await asyncio.sleep(interval)
            elapsed_time += interval
            download.update()

            if download.error_message:
                raise Exception(f"Download failed: {download.error_message}")

            if elapsed_time >= timeout:
                # Stop the download if it exceeds the timeout
                aria2.remove([download], force=True)
                raise Exception("Download timed out.")

            progress = (
                (download.completed_length / download.total_length) * 100
                if download.total_length > 0 else 0
            )
            new_message = f"Downloading... {progress:.2f}%"
            if new_message != previous_message:
                await message.edit_text(new_message)
                previous_message = new_message

        if download.has_failed:
            raise Exception(f"Download failed for link: {link}")

        new_message = f"Download complete: {download.name}"
        if new_message != previous_message:
            await message.edit_text(new_message)

        # Return the file path
        return os.path.join(TEMP_DOWNLOAD_PATH, download.name)

    except Exception as e:
        await message.edit_text(f"Error during download: {str(e)}")
        raise


# Upload file to Telegram with progress updates
async def upload_file(message: Message, file_path: str):
    try:
        await app.send_document(
            chat_id=message.chat.id,
            document=file_path,
            progress=upload_progress,
            progress_args=(message,),
        )
    except Exception as e:
        await message.edit_text(f"Error during upload: {str(e)}")


# Upload progress callback
async def upload_progress(current: int, total: int, message: Message):
    try:
        progress = (current / total) * 100
        new_message = f"Uploading... {progress:.2f}%"
        if new_message != message.text:
            await message.edit_text(new_message)
    except Exception as e:
        logging.error(f"Error updating upload progress: {str(e)}")


# Command handler to download and upload a file
@app.on_message(filters.command("filelink"))
async def handle_filelink(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("Please provide a valid URL or torrent link. Example: /filelink <url>")
        return

    link = message.command[1]
    progress_message = await message.reply("Preparing to download...")

    try:
        # Download file with aria2p
        downloaded_file = await download_with_aria2p(link, progress_message)

        # Notify user download is complete
        await progress_message.edit_text("Download complete. Uploading...")

        # Upload file
        await upload_file(progress_message, downloaded_file)

        # Notify user of success
        await progress_message.edit_text("File uploaded successfully!")

        # Clean up downloaded file
        os.remove(downloaded_file)

    except Exception as e:
        await progress_message.edit_text(f"An error occurred: {str(e)}")


# Command handler for /start
@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply(
        "Hello! Use /filelink <url> to download and upload a file to Telegram. "
        "Supports both direct links and torrent links."
    )


# Run the bot
if __name__ == "__main__":
    try:
        # Ensure aria2c is running
        start_aria2c_daemon()
        app.run()
    except Exception as e:
        logging.error(f"Failed to start bot: {str(e)}")
