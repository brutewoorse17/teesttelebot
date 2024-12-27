import os
import logging
import aiohttp
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


# Async file downloader with progress updates
async def download_file(url: str, file_path: str, message: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                file_size = int(response.headers.get("content-length", 0))
                downloaded_size = 0

                # Ensure the file directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "wb") as file:
                    async for chunk in response.content.iter_chunked(1024):
                        if chunk:
                            file.write(chunk)
                            downloaded_size += len(chunk)

                            # Update download progress
                            progress = (downloaded_size / file_size) * 100
                            await message.edit_text(f"Downloading... {progress:.2f}%")

        return file_path

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
        await message.reply("Please provide a valid URL. Example: /filelink <url>")
        return

    file_url = message.command[1]
    filename = file_url.split("/")[-1]
    file_path = os.path.join(TEMP_DOWNLOAD_PATH, filename)

    progress_message = await message.reply("Starting download...")

    try:
        # Download file
        await download_file(file_url, file_path, progress_message)

        # Notify user download is complete
        await progress_message.edit_text("Download complete. Uploading...")

        # Upload file
        await upload_file(progress_message, file_path)

        # Clean up downloaded file
        os.remove(file_path)

        # Notify user of success
        await progress_message.edit_text("File uploaded successfully!")

    except Exception as e:
        await progress_message.edit_text(f"An error occurred: {str(e)}")


# Command handler for /start
@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply("Hello! Use /filelink <url> to download and upload a file to Telegram.")


# Run the bot
if __name__ == "__main__":
    app.run()
