import os
import logging
import subprocess
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# Enable logging
logging.basicConfig(level=logging.INFO)

# Your bot's credentials
api_id = '29001415'  # Replace with your API ID
api_hash = '92152fd62ffbff12f057edc057f978f1'  # Replace with your API Hash
bot_token = '7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM'  # Replace with your Bot Token

# Directory to temporarily save downloaded files
TEMP_DOWNLOAD_PATH = './downloads'

# Create a Pyrogram client
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)


# Download file using aria2c
async def download_with_aria2c(link: str, output_dir: str, message: Message):
    try:
        # Ensure the downloads directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Prepare the aria2c command
        command = [
            "aria2c",
            "--dir", output_dir,
            "--max-connection-per-server=16",
            "--split=16",
            "--allow-overwrite=true",
            link,
        ]

        # Notify the user about the download start
        await message.edit_text("Starting download with aria2c...")

        # Use subprocess to run the aria2c command
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Monitor the progress
        while process.poll() is None:
            await asyncio.sleep(1)

        # Check if the download succeeded
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            error_message = stderr.decode("utf-8")
            raise Exception(f"aria2c download failed: {error_message}")

        # Notify the user of successful download
        await message.edit_text("Download complete!")

        # Return the path to the downloaded file or directory
        return output_dir

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
    except FloodWait as e:
        await asyncio.sleep(e.x)
        await message.edit_text(f"Rate limit exceeded. Retrying in {e.x} seconds.")
    except Exception as e:
        await message.edit_text(f"Error during upload: {str(e)}")


# Upload progress callback
async def upload_progress(current: int, total: int, message: Message):
    try:
        progress = (current / total) * 100
        await message.edit_text(f"Uploading... {progress:.2f}%")
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
        # Download file with aria2c
        downloaded_path = await download_with_aria2c(link, TEMP_DOWNLOAD_PATH, progress_message)

        # Check if multiple files are downloaded (for torrents)
        if os.path.isdir(downloaded_path):
            # Archive the folder (if needed) before uploading
            await progress_message.edit_text("Downloaded multiple files. Preparing to upload...")

            for root, _, files in os.walk(downloaded_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    await upload_file(progress_message, full_path)

            # Notify the user that all files are uploaded
            await progress_message.edit_text("All files from torrent uploaded successfully!")
        else:
            # Notify user download is complete
            await progress_message.edit_text("Download complete. Uploading...")

            # Upload file
            await upload_file(progress_message, downloaded_path)

            # Notify user of success
            await progress_message.edit_text("File uploaded successfully!")

        # Clean up downloaded files
        for root, dirs, files in os.walk(TEMP_DOWNLOAD_PATH):
            for name in files:
                os.remove(os.path.join(root, name))

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
    app.run()
