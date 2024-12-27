import os
import asyncio
import logging
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

# Dictionary to store the last edited message text for each message
last_message_content = {}

# Helper function to safely update the message text
async def safe_edit_message(message: Message, new_text: str):
    global last_message_content
    try:
        if last_message_content.get(message.message_id) != new_text:
            await message.edit_text(new_text)  # Edit only if the content is different
            last_message_content[message.message_id] = new_text  # Update the last message content
    except Exception as e:
        logging.error(f"Error editing message: {str(e)}")


# Download using aria2p
async def download_with_aria2p(link: str, message: Message):
    try:
        # Add the download to aria2
        downloads = aria2.add(link, options={"dir": TEMP_DOWNLOAD_PATH})
        if not isinstance(downloads, list):
            downloads = [downloads]  # Ensure we always handle it as a list

        for download in downloads:
            await safe_edit_message(message, f"Started download: {download.name}")

            # Monitor download progress
            while not download.is_complete:
                await asyncio.sleep(2)
                download.update()
                progress = (
                    (download.completed_length / download.total_length) * 100
                    if download.total_length > 0
                    else 0
                )
                await safe_edit_message(message, f"Downloading... {progress:.2f}%")

            await safe_edit_message(message, f"Download complete: {download.name}")

        # Return the file paths
        return [os.path.join(TEMP_DOWNLOAD_PATH, download.name) for download in downloads]

    except Exception as e:
        await safe_edit_message(message, f"Error during download: {str(e)}")
        raise


# Upload file to Telegram with progress updates
async def upload_file(message: Message, file_paths: list):
    try:
        for file_path in file_paths:
            await app.send_document(
                chat_id=message.chat.id,
                document=file_path,
                progress=upload_progress,
                progress_args=(message,),
            )
    except Exception as e:
        await safe_edit_message(message, f"Error during upload: {str(e)}")


# Upload progress callback
async def upload_progress(current: int, total: int, message: Message):
    try:
        progress = (current / total) * 100
        await safe_edit_message(message, f"Uploading... {progress:.2f}%")
    except Exception as e:
        logging.error(f"Error updating upload progress: {str(e)}")


# Command handler to download and upload a file
@app.on_message(filters.command("filelink"))
async def handle_filelink(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("Please provide a valid URL. Example: /filelink <url>")
        return

    link = message.command[1]

    progress_message = await message.reply("Preparing to download...")

    try:
        # Download file with aria2p
        downloaded_files = await download_with_aria2p(link, progress_message)

        await safe_edit_message(progress_message, "Download complete. Uploading...")

        # Upload files
        await upload_file(progress_message, downloaded_files)

        await safe_edit_message(progress_message, "File(s) uploaded successfully!")

        # Clean up downloaded files
        for downloaded_file in downloaded_files:
            os.remove(downloaded_file)

    except Exception as e:
        await safe_edit_message(progress_message, f"An error occurred: {str(e)}")


# Command handler for /start
@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply(
        "Hello! Use /filelink <url> to download and upload a file to Telegram."
    )


# Run the bot
if __name__ == "__main__":
    try:
        app.run()
    except Exception as e:
        logging.error(f"Failed to start bot: {str(e)}")
