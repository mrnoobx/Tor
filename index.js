import express from "express";
import { Bot, webhookCallback } from "grammy";
import WebTorrent from "webtorrent";
import { config } from "dotenv";
import fs from "fs";
import path from "path";
import os from "os";
import { fileURLToPath } from "url";

config();
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const bot = new Bot(process.env.BOT_TOKEN);
const client = new WebTorrent();

// === Start Command ===
bot.command("start", async (ctx) => {
  await ctx.reply(
    "👋 *Welcome to the Magnet ➜ .torrent Bot!*\n\nSend a magnet link and I'll generate a `.torrent` file for you.",
    { parse_mode: "Markdown" }
  );
});

// === Help Command ===
bot.command("help", async (ctx) => {
  await ctx.reply("📌 Just send a valid magnet link like:\n`magnet:?xt=...`", { parse_mode: "Markdown" });
});

// === Handle Magnet Links ===
bot.on("message:text", async (ctx) => {
  const magnet = ctx.message.text.trim();

  if (!magnet.startsWith("magnet:?xt=")) {
    return ctx.reply("⚠️ Please send a valid magnet link.");
  }

  await ctx.reply("🧲 Fetching torrent metadata...");

  try {
    client.add(magnet, { destroyStoreOnDestroy: true }, async (torrent) => {
      const torrentBuffer = torrent.torrentFile;
      const filePath = path.join(os.tmpdir(), `${torrent.name}.torrent`);

      fs.writeFileSync(filePath, torrentBuffer);

      await ctx.replyWithDocument({
        source: fs.createReadStream(filePath),
        filename: `${torrent.name}.torrent`
      });

      torrent.destroy(); // Clean up
    });
  } catch (err) {
    console.error("Error:", err);
    await ctx.reply("🚨 Something went wrong while generating the `.torrent` file.");
  }
});

// === Express Webhook Server ===
const app = express();
app.use(express.json());
app.use(`/${bot.token}`, webhookCallback(bot));
app.get("/", (_, res) => res.send("✅ Bot is alive"));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));
