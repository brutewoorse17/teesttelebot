import os
import logging
import requests
import asyncio
from tqdm import tqdm
from pyrogram import Client, filters
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

# Progress bar for downloading files
def download_file(url, file_path, progress_callback=None, message=None):
    # Make an HTTP GET request with stream=True to download the file
    response = requests.get(url, stream=True)
    file_size = int(response.headers.get('content-length', 0))

    with tqdm(total=file_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))  # Update the progress bar with the chunk's length
                    # Call progress callback to update the message
                    if progress_callback:
                        progress_callback(pbar.n, file_size, message)

# Progress bar for uploading files to Telegram
async def upload_file_to_telegram(message, file_path, progress_callback=None):
    try:
        # Upload the document and show progress
        await message.reply_document(
            document=file_path,
            progress=upload_progress,
            progress_args=("Uploading...", message, progress_callback)  # Custom progress message
        )
    except FloodWait as e:
        # In case of a flood wait, wait before retrying
        await message.reply(f"Rate limit exceeded. Please wait {e.x} seconds.")
        await asyncio.sleep(e.x)

# Upload progress callback
def upload_progress(current, total, message, prefix="Uploading...", progress_callback=None):
    # Calculate the percentage of the file uploaded
    progress = current / total * 100
    # Update the message with the progress
    progress_callback(message, download_progress=100, upload_progress=progress)

# Update progress message that combines download and upload progress
def update_progress_message(message, download_progress, upload_progress):
    message.edit(f"Download Progress: {download_progress:.2f}%\nUpload Progress: {upload_progress:.2f}%")

# Command handler to download file from a link and upload to Telegram
@app.on_message(filters.command('filelink'))
async def download_and_upload_file(client, message):
    if len(message.command) < 2:
        await message.reply("Please provide a valid URL. Example: /filelink <url>")
        return

    file_url = message.command[1]  # Get the URL from the message

    # Ensure the downloads directory exists
    if not os.path.exists(TEMP_DOWNLOAD_PATH):
        os.makedirs(TEMP_DOWNLOAD_PATH)

    try:
        # Send a message that the bot is downloading the file
        progress_msg = await message.reply("Downloading and uploading...")

        # Get the file name from the URL
        filename = file_url.split("/")[-1]
        file_path = os.path.join(TEMP_DOWNLOAD_PATH, filename)

        # Start downloading the file with progress updates
        download_file(file_url, file_path, progress_callback=update_progress_message, message=progress_msg)

        # Notify the user that the file has been downloaded
        await progress_msg.edit("Download complete! Now uploading...")

        # Start uploading the file with progress updates
        await upload_file_to_telegram(progress_msg, file_path, progress_callback=update_progress_message)

        # Optionally, delete the file after uploading to Telegram
        os.remove(file_path)

        # Notify the user that the file is uploaded
        await progress_msg.edit(f"File uploaded successfully: {filename}")

    except Exception as e:
        await message.reply(f"An error occurred: {str(e)}")

# Command handler for /start
@app.on_message(filters.command('start'))
async def start(client, message):
    await message.reply("Hello! Use /filelink <url> to download and upload a file to Telegram.")

# Run the bot
if __name__ == '__main__':
    app.run()
