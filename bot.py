# Premium Torrent Bot with Real-Time Progress and Flask Health Check

import os
import time
import shutil
import mimetypes
import subprocess
import asyncio
import logging
import re
import requests
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified, MessageIdInvalid
from dotenv import load_dotenv
from flask import Flask

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID", "17013900"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
PORT = int(os.getenv("PORT", 8080))

bot = Client("torrent_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
DOWNLOAD_DIR = "downloads"
MAX_SIZE = 1900 * 1024 * 1024
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PremiumTorrentBot")

# Flask Health Check
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return {"status": "ok"}
Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT), daemon=True).start()

# Utilities
def human_readable_size(size, decimal_places=2):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def format_progress_bar(current: int, total: int, width: int = 20) -> str:
    if total == 0:
        return "[----------] 0% (0B/0B)"
    percent = current / total
    filled_length = int(width * percent)
    bar = "█" * filled_length + "░" * (width - filled_length)
    percent_display = int(percent * 100)
    current_mb = current / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    return f"[{bar}] {percent_display}% ({current_mb:.1f}MB/{total_mb:.1f}MB)"

async def safe_edit_message(message, text, max_retries=2):
    retries = 0
    while retries < max_retries:
        try:
            await message.edit_text(text)
            return True
        except FloodWait as e:
            await asyncio.sleep(min(e.value, 20))
            retries += 1
        except (MessageNotModified, MessageIdInvalid):
            return True
        except Exception:
            return False
    return False

def split_large_file(file_path, chunk_size=MAX_SIZE):
    part_num, output_files = 1, []
    base_name = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            part_name = f"{base_name}.part{part_num:03d}"
            part_path = os.path.join(os.path.dirname(file_path), part_name)
            with open(part_path, 'wb') as p:
                p.write(chunk)
            output_files.append(part_path)
            part_num += 1
    return output_files

def clean_directory(directory):
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            logger.info(f"✅ Cleaned directory: {directory}")
    except Exception as e:
        logger.error(f"❌ Failed to clean directory {directory}: {str(e)}")

# UI Button
keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ＭＩＲＲＯＲ", url="https://t.me/noob_project")]])

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    welcome_image = "https://i.ibb.co/K3DtVdZ/abe163b83134.jpg"
    caption = (
        "**🤖 Welcome to Torrent Downloader Bot!**\n\n"
        "📤 Send me a magnet link or .torrent file and I'll download and upload the content for you!\n\n"
        "💡 **Features:**\n"
        "• Torrent & Magnet Link Support\n"
        "• Automatic Video Detection\n"
        "• Large File Splitting\n"
        "• Automatic File Cleanup\n\n"
        "⚙️ **Max File Size:** 1.9GB (Telegram Limit)\n"
        "🧹 **Auto Cleanup:** Enabled ✅"
    )
    try:
        await message.reply_photo(photo=welcome_image, caption=caption, reply_markup=keyboard)
    except:
        await message.reply_text(caption, reply_markup=keyboard)

@bot.on_message(filters.private & filters.text)
async def torrent_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    USER_DIR = os.path.join(DOWNLOAD_DIR, f"user_{user_id}_{int(time.time())}")
    os.makedirs(USER_DIR, exist_ok=True)

    try:
        if re.match(r"^https?://.*\\.torrent$", text):
            try:
                response = requests.get(text, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()
                fname = re.findall("filename=(.+)", response.headers.get("content-disposition", "")) or [text.split("/")[-1].split("?")[0]]
                torrent_file_path = os.path.join(USER_DIR, fname[0])
                with open(torrent_file_path, "wb") as f:
                    f.write(response.content)
                text = torrent_file_path
            except Exception as e:
                await message.reply(f"❌ Torrent download failed: {str(e)}")
                return

        if not (text.startswith("magnet:") or (text.endswith(".torrent") and os.path.exists(text))):
            await message.reply("❌ Invalid torrent or magnet link!")
            return

        msg = await message.reply("🔄 Starting download...")

        cmd = [
            "aria2c", "--dir=" + USER_DIR, "--seed-time=0",
            "--max-connection-per-server=16", "--split=16",
            "--max-concurrent-downloads=5", "--check-certificate=false",
            "--auto-file-renaming=true", "--allow-overwrite=true",
            "--file-allocation=none", "--summary-interval=15", text
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        start_time = time.time()
        last_update = time.time()

        while process.poll() is None:
            if time.time() - last_update > 15:
                await safe_edit_message(msg, f"⏳ Downloading... ({int(time.time() - start_time)}s)")
                last_update = time.time()
            await asyncio.sleep(1)

        if process.poll() != 0:
            await safe_edit_message(msg, "❌ Download failed.")
            return

        await safe_edit_message(msg, "🔍 Searching for downloaded files...")

        files = []
        for root, _, filenames in os.walk(USER_DIR):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                if not filename.endswith(('.aria2', '.tmp')) and os.path.getsize(filepath) > 0:
                    files.append(filepath)

        if not files:
            await safe_edit_message(msg, "❌ No files found after download.")
            return

        for filepath in files:
            size = os.path.getsize(filepath)
            if size > MAX_SIZE:
                await safe_edit_message(msg, f"⚠️ Splitting large file: {os.path.basename(filepath)}")
                file_parts = split_large_file(filepath)
                os.remove(filepath)
            else:
                file_parts = [filepath]

            for part in file_parts:
                part_name = os.path.basename(part)
                await safe_edit_message(msg, f"📤 Uploading: {part_name}")
                mime, _ = mimetypes.guess_type(part)
                try:
                    if mime and mime.startswith("video"):
                        await message.reply_video(
                            video=part,
                            caption=f"🎬 `{part_name}`",
                            reply_markup=keyboard,
                            supports_streaming=True,
                            progress=lambda c, t: asyncio.run_coroutine_threadsafe(
                                safe_edit_message(msg, f"📤 Uploading: {part_name}\n{format_progress_bar(c, t)}"),
                                bot.loop
                            )
                        )
                    else:
                        await message.reply_document(
                            document=part,
                            caption=f"📦 `{part_name}`",
                            reply_markup=keyboard,
                            progress=lambda c, t: asyncio.run_coroutine_threadsafe(
                                safe_edit_message(msg, f"📤 Uploading: {part_name}\n{format_progress_bar(c, t)}"),
                                bot.loop
                            )
                        )
                except Exception as e:
                    await message.reply(f"❌ Failed to upload {part_name}: {str(e)}")
                finally:
                    if os.path.exists(part):
                        os.remove(part)

        await msg.delete()
    finally:
        clean_directory(USER_DIR)

async def cleanup_scheduler():
    while True:
        try:
            now = time.time()
            for dir_name in os.listdir(DOWNLOAD_DIR):
                dir_path = os.path.join(DOWNLOAD_DIR, dir_name)
                if os.path.isdir(dir_path) and (now - os.path.getmtime(dir_path)) > 3600:
                    clean_directory(dir_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(3600)

if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    bot.loop.create_task(cleanup_scheduler())
    bot.run()
    
