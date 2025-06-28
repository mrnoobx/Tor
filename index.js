import express from "express";
import { Bot, webhookCallback } from "grammy";
import { config } from "dotenv";
import fs from "fs";
import os from "os";
import path from "path";
import { exec } from "child_process";
import { fileURLToPath } from "url";
import util from "util";

config();
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const bot = new Bot(process.env.BOT_TOKEN);
const execPromise = util.promisify(exec);

// === Commands ===
bot.command("start", async (ctx) => {
  await ctx.reply(
    "👋 *Welcome to the Magnet ➜ .torrent Bot!*\n\nSend a magnet link and I'll return a `.torrent` file. 🔥",
    { parse_mode: "Markdown" }
  );
});

bot.command("help", async (ctx) => {
  await ctx.reply("📌 Just send a valid magnet link starting with `magnet:?xt=`");
});

// === Magnet Handler ===
bot.on("message:text", async (ctx) => {
  const text = ctx.message.text.trim();
  if (!text.startsWith("magnet:?xt=")) {
    return ctx.reply("⚠️ Please send a valid magnet link.");
  }

  const magnet = text;
  const torrentPath = path.join(os.tmpdir(), `magnet_${Date.now()}.torrent`);

  try {
    await ctx.reply("🧲 Converting magnet...");

    const cmd = `webtorrent "${magnet}" --out "${os.tmpdir()}" --torrent`;
    await execPromise(cmd);

    const torrentFile = fs.readdirSync(os.tmpdir()).find(file => file.endsWith(".torrent"));
    if (!torrentFile) {
      return ctx.reply("❌ Failed to create `.torrent` file.");
    }

    const fullPath = path.join(os.tmpdir(), torrentFile);
    await ctx.replyWithDocument({
      source: fs.createReadStream(fullPath),
      filename: "magnet.torrent"
    });

  } catch (err) {
    console.error("❌ Conversion error:", err);
    await ctx.reply("🚨 Something went wrong while generating the `.torrent` file.");
  }
});

// === Web Server for Webhook ===
const app = express();
app.use(express.json());
app.use(`/${bot.token}`, webhookCallback(bot));
app.get("/", (_, res) => res.send("✅ Bot is up"));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Listening on port ${PORT}`));
