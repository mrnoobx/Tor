# 🎯 Combined Premium Telegram Torrent Downloader Bot with Flask, aria2, Pyrogram & Splitting

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
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

bot = Client("torrent_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
DOWNLOAD_DIR = "downloads"
MAX_SIZE = 1900 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TorrentBot")

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return {"status": "ok", "message": "Bot is running"}

Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT), daemon=True).start()

def human_readable_size(size, decimal_places=2):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"

def format_progress_bar(current, total, width=20):
    if total == 0:
        return "[░░░░░░░░░░░░░░░░░░░░░░░░] 0%"
    percent = current / total
    done = int(width * percent)
    bar = "█" * done + "░" * (width - done)
    return f"[{bar}] {int(percent*100)}% ({current//1024//1024}MB/{total//1024//1024}MB)"

async def safe_edit_message(message, text, max_retries=2):
    for _ in range(max_retries):
        try:
            await message.edit_text(text)
            return
        except (FloodWait, MessageNotModified, MessageIdInvalid):
            await asyncio.sleep(2)

keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ＭＩＲＲＯＲ", url="https://t.me/noob_project")]])

def split_large_file(file_path, chunk_size=MAX_SIZE):
    parts, i = [], 0
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            part_path = f"{file_path}.part{i}"
            with open(part_path, 'wb') as pf:
                pf.write(chunk)
            parts.append(part_path)
            i += 1
    return parts

def clean_directory(path):
    if os.path.exists(path):
        shutil.rmtree(path)

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(_, msg: Message):
    text = (
        "**🤖 Welcome to Torrent Downloader Bot!**\n\n"
        "📥 Send magnet or .torrent URL and I will download & upload it for you.\n\n"
        "⚙️ Max File: 1.9GB\n🧹 Auto Cleanup: Enabled ✅"
    )
    await msg.reply_photo("https://i.ibb.co/K3DtVdZ/abe163b83134.jpg", caption=text, reply_markup=keyboard)

@bot.on_message(filters.text & filters.private)
async def magnet_handler(_, msg: Message):
    url = msg.text.strip()
    if not (url.startswith("magnet:") or url.endswith(".torrent") or ".torrent" in url):
        return await msg.reply("❌ Invalid link. Must be a magnet or .torrent URL")

    user_dir = os.path.join(DOWNLOAD_DIR, f"{msg.from_user.id}_{int(time.time())}")
    os.makedirs(user_dir, exist_ok=True)
    torrent_path = url

    if url.startswith("http") and ".torrent" in url:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla"})
            filename = re.findall('filename="(.+?)"', r.headers.get("content-disposition", ""))
            name = filename[0] if filename else url.split("/")[-1]
            torrent_path = os.path.join(user_dir, name)
            with open(torrent_path, "wb") as f:
                f.write(r.content)
        except:
            return await msg.reply("❌ Failed to fetch .torrent file")

    await_msg = await msg.reply("⏬ Downloading...")

    cmd = [
        "aria2c", "--dir=" + user_dir, "--seed-time=0",
        "--max-connection-per-server=10", "--split=10", "--max-concurrent-downloads=3",
        "--check-certificate=false", "--file-allocation=none", url if url.startswith("magnet:") else torrent_path
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while process.poll() is None:
        await asyncio.sleep(10)
        await safe_edit_message(await_msg, "⏬ Still downloading...")

    files = []
    for root, _, filenames in os.walk(user_dir):
        for file in filenames:
            if not file.endswith(".aria2"):
                files.append(os.path.join(root, file))

    if not files:
        return await await_msg.edit("❌ No file found")

    for f in files:
        parts = split_large_file(f) if os.path.getsize(f) > MAX_SIZE else [f]
        for p in parts:
            caption = f"📦 `{os.path.basename(p)}`"
            mime, _ = mimetypes.guess_type(p)
            try:
                if mime and mime.startswith("video"):
                    await msg.reply_video(video=p, caption=caption, reply_markup=keyboard)
                else:
                    await msg.reply_document(document=p, caption=caption, reply_markup=keyboard)
            except Exception as e:
                await msg.reply(f"❌ Failed to upload {os.path.basename(p)}: {e}")
            finally:
                if os.path.exists(p):
                    os.remove(p)

    await await_msg.delete()
    clean_directory(user_dir)

async def auto_cleanup():
    while True:
        try:
            now = time.time()
            for dir in os.listdir(DOWNLOAD_DIR):
                path = os.path.join(DOWNLOAD_DIR, dir)
                if os.path.isdir(path) and time.time() - os.path.getmtime(path) > 3600:
                    clean_directory(path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(3600)

if __name__ == '__main__':
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    bot.loop.create_task(auto_cleanup())
    bot.run()
              
