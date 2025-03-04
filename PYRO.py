import os
import asyncio
import logging
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
from aria2p import API, Client as Aria2Client, Download
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests import Session
import json

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


# Safe function to edit message to avoid Telegram errors
async def safe_edit_message(message: Message, text: str):
    try:
        # Check if the message exists before editing
        if message.text != text:  # Only edit if the content is different
            await message.edit_text(text)
    except Exception as e:
        logging.error(f"Error editing message: {str(e)}")
        # If the message was deleted or is invalid, we log the error and do not try to edit
        if "MESSAGE_ID_INVALID" in str(e):
            logging.warning("Message ID is invalid, skipping edit.")
        else:
            logging.error(f"Unexpected error: {str(e)}")


# Download using aria2p
async def download_with_aria2p(link: str, message: Message):
    try:
        # Add the download to aria2
        download: Download = aria2.add(link, options={"dir": TEMP_DOWNLOAD_PATH})
        await safe_edit_message(message, f"Started download: {download.name}")

        # Monitor download progress
        while not download.is_complete:
            await asyncio.sleep(2)
            download.update()
            progress = (download.completed_length / download.total_length) * 100 if download.total_length > 0 else 0
            await safe_edit_message(message, f"Downloading... {progress:.2f}%")

        # Notify user that download is complete
        await safe_edit_message(message, f"Download complete: {download.name}")

        # Return the file path
        return os.path.join(TEMP_DOWNLOAD_PATH, download.name)

    except Exception as e:
        await safe_edit_message(message, f"Error during download: {str(e)}")
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
        await message.reply("Please provide a valid URL or torrent link. Example: /filelink <url>")
        return

    link = message.command[1]

    progress_message = await message.reply("Preparing to download...")

    try:
        # Download file with aria2p
        downloaded_file = await download_with_aria2p(link, progress_message)

        # Notify user download is complete
        await safe_edit_message(progress_message, "Download complete. Uploading...")

        # Upload file
        await upload_file(progress_message, downloaded_file)

        # Notify user of success
        await safe_edit_message(progress_message, "File uploaded successfully!")

        # Clean up downloaded file
        os.remove(downloaded_file)

    except Exception as e:
        await safe_edit_message(progress_message, f"An error occurred: {str(e)}")


# Command handler for /start
@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply(
        "Hello! Use /filelink <url> to download and upload a file to Telegram. "
        "Supports both direct links and torrent links."
    )


# Command handler to show active, waiting, and failed downloads
@app.on_message(filters.command("status"))
async def show_download_status(client: Client, message: Message):
    try:
        all_downloads = aria2.get_downloads()  # Get all downloads
        active_downloads = [d for d in all_downloads if d.status == "active"]
        waiting_downloads = [d for d in all_downloads if d.status == "waiting"]
        failed_downloads = [d for d in all_downloads if d.status == "failed"]

        status_message = "Download Status:\n\n"

        if active_downloads:
            status_message += "Active Downloads:\n"
            for download in active_downloads:
                progress = (
                    (download.completed_length / download.total_length) * 100
                    if download.total_length > 0
                    else 0
                )
                status_message += f"- {download.name} (GID: {download.gid}): {progress:.2f}% complete\n"

        if waiting_downloads:
            status_message += "\nWaiting Downloads:\n"
            for download in waiting_downloads:
                status_message += f"- {download.name}: Waiting\n"

        if failed_downloads:
            status_message += "\nFailed Downloads:\n"
            for download in failed_downloads:
                status_message += f"- {download.name}: Failed\n"

        if not (active_downloads or waiting_downloads or failed_downloads):
            status_message += "No downloads in progress.\n"

        # Send a new message instead of editing an old one
        await message.reply(status_message)

    except Exception as e:
        await message.reply(f"An error occurred while retrieving download status: {str(e)}")


# Function to handle MediaFire folder direct link
def mediafireFolder(url):
    if "::" in url:
        _password = url.split("::")[-1]
        url = url.split("::")[-2]
    else:
        _password = ""
    try:
        raw = url.split("/", 4)[-1]
        folderkey = raw.split("/", 1)[0]
        folderkey = folderkey.split(",")
    except:
        raise Exception("ERROR: Could not parse URL for folder key.")
    
    if len(folderkey) == 1:
        folderkey = folderkey[0]
    
    details = {"contents": [], "title": "", "total_size": 0, "header": ""}
    
    session = Session()
    adapter = HTTPAdapter(
        max_retries=Retry(total=10, read=10, connect=10, backoff_factor=0.3)
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    folder_infos = []

    def __get_info(folderkey):
        try:
            if isinstance(folderkey, list):
                folderkey = ",".join(folderkey)
            # Make the request to MediaFire API
            response = session.post(
                "https://www.mediafire.com/api/1.5/folder/get_info.php",
                data={
                    "recursive": "yes",
                    "folder_key": folderkey,
                    "response_format": "json",
                },
            )

            # Log the raw response for debugging
            logging.info(f"Raw response: {response.text}")

            # Attempt to parse the JSON response
            try:
                _json = response.json()
            except json.JSONDecodeError:
                raise Exception("ERROR: JSONDecodeError while parsing MediaFire response.")
            
        except Exception as e:
            raise Exception(f"ERROR: {e.__class__.__name__} While getting folder info")
        
        # Handle the response
        _res = _json["response"]
        if "folder_infos" in _res:
            folder_infos.extend(_res["folder_infos"])
        elif "folder_info" in _res:
            folder_infos.append(_res["folder_info"])
        elif "message" in _res:
            raise Exception(f"ERROR: {_res['message']}")
        else:
            raise Exception("ERROR: something went wrong!")
    
    __get_info(folderkey)

    return folder_infos


# Run the bot
if __name__ == "__main__":
    try:
        # Ensure aria2c is running
        start_aria2c_daemon()
        app.run()
    except Exception as e:
        logging.error(f"Failed to start bot: {str(e)}")
