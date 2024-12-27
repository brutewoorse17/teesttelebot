from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import xmlrpc.client
import requests
import os
import asyncio
import math
import time
import hashlib

# ... (API ID, API Hash, Bot Token, aria2 config, etc. - same as before)

# ... (aria2 RPC client setup - same as before)

# Global dictionary to store download statuses
download_statuses = {}

# Global dictionary to store upload statuses
upload_statuses = {}

# Global list to store gids
gids = []


API_ID = 29001415
API_HASH = "92152fd62ffbff12f057edc057f978f1"
BOT_TOKEN = "7505846620:AAFvv-sFybGfFILS-dRC8l7ph_0rqIhDgRM"
# Create Pyrogram client
app = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ... (Other functions: update_download_status, periodic_status_update - same as before)

# Chunk size (slightly less than 2GB to be safe)
CHUNK_SIZE = 1024 * 1024 * 1999  # 1999 MB in bytes

async def generate_gid():
    """Generates a unique GID for each upload."""
    timestamp = str(time.time()).encode('utf-8')
    hash_object = hashlib.sha256(timestamp)
    gid = hash_object.hexdigest()[:16]  # Use first 16 characters of the hash
    return gid

async def upload_progress_callback(current, total, chat_id, message_id, start_time, gid, file_path):
    """Callback function to track and display upload progress."""
    global upload_statuses

    # Update upload status every 1 seconds
    elapsed_time = time.time() - start_time
    if elapsed_time < 1:
        return

    if current == total:
        progress_message = "Upload complete!"
        # Remove the GID from the statuses
        if gid in upload_statuses:
            del upload_statuses[gid]
    else:
        progress = (current / total) * 100
        speed = current / elapsed_time if elapsed_time > 0 else 0

        upload_statuses[gid] = {
            "file_path": file_path,
            "current": current,
            "total": total,
            "progress": progress,
            "speed": speed,
            "chat_id": chat_id,
            "message_id": message_id
        }
        progress_message = f"Uploading: {progress:.2f}% - {speed / (1024 * 1024):.2f} MB/s"
        

    try:
        await app.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=progress_message
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)

async def split_and_upload(chat_id: int, file_path: str, client: Client):
    """Splits a large file into chunks and uploads them to Telegram."""
    global gids
    file_size = os.path.getsize(file_path)
    num_chunks = math.ceil(file_size / CHUNK_SIZE)

    if num_chunks > 1:
        await client.send_message(
            chat_id,
            text="File is larger than 2GB. Splitting into multiple parts to upload."
        )

    with open(file_path, "rb") as f:
        for i in range(num_chunks):
            chunk_path = f"{file_path}.{i:03d}"  # e.g., filename.ext.001
            with open(chunk_path, "wb") as chunk_file:
                chunk_file.write(f.read(CHUNK_SIZE))

            gid = await generate_gid()
            gids.append(gid)
            part_message = await client.send_message(chat_id, text=f"Uploading part {i + 1} of {num_chunks}...\nGID: `{gid}`", parse_mode="markdown")
            start_time = time.time()
            # Pass the progress callback, chat_id, message.id, gid and file path to send_document
            await client.send_document(
                chat_id=chat_id,
                document=chunk_path,
                progress=upload_progress_callback,
                progress_args=(chat_id, part_message.id, start_time, gid, chunk_path)
            )

            # Update the upload status with file path
            upload_statuses[gid] = {
                "file_path": chunk_path,  # Add file path here
                "current": 0,  # Initial value, will be updated by the callback
                "total": os.path.getsize(chunk_path),  # Size of this chunk
                "progress": 0.0,  # Initial value
                "speed": 0.0,  # Initial value
                "chat_id": chat_id,
                "message_id": part_message.id
            }

            os.remove(chunk_path)  # Clean up the chunk

    await client.send_message(
        chat_id,
        text=f"File uploaded in {num_chunks} parts. You need to rejoin them after downloading."
    )

async def upload_to_telegram(chat_id: int, file_path: str, client: Client):
    """Uploads a file to Telegram, splitting it if necessary."""
    global gids
    if os.path.getsize(file_path) > CHUNK_SIZE:
        await split_and_upload(chat_id, file_path, client)
    else:
        try:
            gid = await generate_gid()
            gids.append(gid)
            start_time = time.time()
            # Send an initial message to the chat
            message = await client.send_message(chat_id, text=f"Starting upload...\nGID: `{gid}`", parse_mode="markdown")

            # Pass the progress callback, chat_id, message.id, gid and file path to send_document
            await client.send_document(
                chat_id=chat_id,
                document=file_path,
                progress=upload_progress_callback,
                progress_args=(chat_id, message.id, start_time, gid, file_path)
            )
            # Update the upload status with file path
            upload_statuses[gid] = {
                "file_path": file_path,  # Add file path here
                "current": 0,  # Initial value, will be updated by the callback
                "total": os.path.getsize(file_path),  # Total size of the file
                "progress": 0.0,  # Initial value
                "speed": 0.0,  # Initial value
                "chat_id": chat_id,
                "message_id": message.id
            }

        except Exception as e:
            await client.send_message(chat_id=chat_id, text=f"Error uploading file: {e}")

async def handle_torrent(client: Client, message: Message):
    """Handles .torrent files, adds them to aria2."""
    global gids
    document = message.document
    chat_id = message.chat.id

    if document.mime_type == 'application/x-bittorrent':
        try:
            file = await document.get_file()
            file_path = os.path.join(TORRENT_DIR, document.file_name)
            await file.download_to_drive(file_path)

            # Add torrent to aria2
            with open(file_path, "rb") as torrent_file:
                torrent_data = xmlrpc.client.Binary(torrent_file.read())
            gid = aria2.aria2.addTorrent(ARIA2_RPC_TOKEN, torrent_data, [], {"dir": TORRENT_DIR})
            await message.reply_text(f"Torrent added to aria2. GID: {gid}")

            # Add the gid to the global list
            gids.append(gid)

            # Update the status immediately after adding
            await update_download_status(gid)

            # Wait for the download to complete and then upload
            asyncio.create_task(wait_for_download_and_upload(gid, message.chat.id, file_path, client))

            # Clean up the temporary .torrent file
            os.remove(file_path)

        except Exception as e:
            await message.reply_text(f"Error processing torrent: {e}")
    else:
        await message.reply_text("Please send a valid .torrent file.")

async def wait_for_download_and_upload(gid: str, chat_id: int, file_path: str, client: Client):
    """Waits for an aria2 download to complete and then uploads the file to Telegram."""
    global gids
    while True:
        if gid in download_statuses:
            status = download_statuses[gid]
            download_status = status['status']

            if download_status == 'active':
                # Calculate and display progress (optional)
                completed_length = int(status['completedLength'])
                total_length = int(status['totalLength'])
                progress = (completed_length / total_length) * 100 if total_length > 0 else 0
                download_speed = int(status['downloadSpeed'])
                upload_speed = int(status['uploadSpeed'])
                print(f"GID: {gid} | Progress: {progress:.2f}% | Download Speed: {download_speed / (1024):.2f} KB/s | Upload Speed: {upload_speed / (1024):.2f} KB/s")

            elif download_status == 'complete':
                # Download finished, get the downloaded file path
                downloaded_file_path = status['files'][0]['path']

                # Notify user that download is finished
                await client.send_message(chat_id, f"Download finished for GID: {gid}. Starting upload...")

                # Upload the file to Telegram
                await upload_to_telegram(chat_id, downloaded_file_path, client)

                # Notify user that upload is finished
                await client.send_message(chat_id, f"Upload completed for file: {downloaded_file_path}")

                # Clean up the downloaded file (optional)
                os.remove(downloaded_file_path)

                # Remove the GID from the statuses and gids list
                if gid in download_statuses:
                    del download_statuses[gid]
                if gid in gids:
                    gids.remove(gid)
                break

            elif download_status in ['error', 'paused', 'removed']:
                await client.send_message(chat_id, f"Download failed or stopped with status: {download_status}")
                # Remove the GID from the statuses and gids list
                if gid in download_statuses:
                    del download_statuses[gid]
                if gid in gids:
                    gids.remove(gid)
                break

        await asyncio.sleep(5)  # Check every 5 seconds

async def cancel_download(gid: str, chat_id: int, client: Client):
    """Cancels a download using aria2."""
    global gids

    try:
        # Remove the download from aria2
        removed_gids = aria2.aria2.remove(ARIA2_RPC_TOKEN, gid)

        if removed_gids and removed_gids[0] == gid:
            # Remove the GID from the statuses and gids list
            if gid in download_statuses:
                del download_statuses[gid]
            if gid in gids:
                gids.remove(gid)

            await client.send_message(chat_id, f"Download cancelled for GID: {gid}")
        else:
            await client.send_message(chat_id, f"Failed to cancel download for GID: {gid}. It may not exist.")
    except Exception as e:
        await client.send_message(chat_id, f"Error cancelling download for GID: {gid}: {e}")

async def cancel_upload(gid: str, client: Client):
    """Cancels an upload to Telegram."""
    global upload_statuses

    if gid in upload_statuses:
        status = upload_statuses[gid]
        chat_id = status["chat_id"]
        message_id = status["message_id"]

        try:
            # Delete the message being edited
            await client.delete_messages(chat_id, message_id)
            await client.send_message(chat_id, f"Upload canceled for GID: {gid}")

        except Exception as e:
            await client.send_message(chat_id, f"Error canceling upload for GID {gid}: {e}")
        finally:
            # Remove the GID from the statuses
            if gid in upload_statuses:
                del upload_statuses[gid]
            if gid in gids:
                gids.remove(gid)
    else:
        await client.send_message(status["chat_id"], f"No active upload found for GID: {gid}")

@app.on_message(filters.command("cancel"))
async def cancel_command(client: Client, message: Message):
    """Handles the /cancel command to cancel a download by GID or an upload by GID."""
    global gids, upload_statuses
    chat_id = message.chat.id

    if len(message.command) > 1:
        identifier = message.command[1]

        if identifier in gids:
            # Check if it's an active download or upload based on available dictionaries
            if identifier in download_statuses:
                await cancel_download(identifier, chat_id, client)
            elif identifier in upload_statuses:
                await cancel_upload(identifier, client)
            else:
                await message.reply_text("The provided GID is in the list but not found in active downloads or uploads.")
        else:
            await message.reply_text("Invalid GID or operation already completed.")
    else:
        await message.reply_text("Please provide a GID to cancel. Usage: /cancel <GID>")

@app.on_message(filters.command("stats"))
async def get_stats(client: Client, message: Message):
    """Gets and sends download and upload stats."""
    chat_id = message.chat.id

    try:
        # Get global stats from aria2
        global_stats = aria2.aria2.getGlobalStat(ARIA2_RPC_TOKEN)

        message_text = "**aria2 Download Stats:**\n"
        message_text += f"**Download Speed:** {int(global_stats['downloadSpeed']) / (1024):.2f} KB/s\n"
        message_text += f"**Upload Speed:** {int(global_stats['uploadSpeed']) / (1024):.2f} KB/s\n"
        message_text += f"**Active Downloads:** {global_stats['numActive']}\n"
        message_text += f"**Waiting Downloads:** {global_stats['numWaiting']}\n"
        message_text += f"**Stopped Downloads:** {global_stats['numStopped']}\n\n"

        # Add details for each active download
        for gid in gids:
            if gid in download_statuses:
                status = download_statuses[gid]
                message_text += f"**GID:** `{gid}`\n"
                message_text += f"**Status:** {status['status']}\n"
                message_text += f"**Progress:** {int(status['completedLength']) / int(status['totalLength']) * 100 if int(status['totalLength']) > 0 else 0:.2f}%\n"
                message_text += f"**Downloaded:** {int(status['completedLength']) / (1024 * 1024):.2f} MB / {int(status['totalLength']) / (1024 * 1024):.2f} MB\n"
                message_text += f"**File:** {status['files'][0]['path']}\n\n"

        # Add details for each active uploads
        message_text += "**Active Uploads:**\n"
        for gid in gids:
            if gid in upload_statuses:
                status = upload_statuses[gid]
                message_text += f"**GID:** `{gid}`\n"
                message_text += f"**File:** {status['file_path']}\n"
                message_text += f"**Progress:** {status['progress']:.2f}%\n"
                message_text += f"**Uploaded:** {status['current'] / (1024 * 1024):.2f} MB / {status['total'] / (1024 * 1024):.2f} MB\n"
                message_text += f"**Speed:** {status['speed'] / (1024 * 1024):.2f} MB/s\n\n"

        await message.reply_text(message_text, parse_mode="markdown")

    except Exception as e:
        await message.reply_text(f"Error fetching stats: {e}")

# Start the client and periodic update task
async def main():
  async with app: