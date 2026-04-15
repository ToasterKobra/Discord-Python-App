import os
import discord
from discord.ext import commands


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True


class MyBot(commands.Bot):
    async def setup_hook(self):
        extensions = [
            "forum",
            "clean",
            "giveaway",
            "server",
            "music",
            "channel"
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"✅ Extension geladen: {ext}")
            except Exception as e:
                print(f"❌ Fehler bei {ext}: {e}")

        try:
            synced = await self.tree.sync()
            print(f"🔄 Slash Commands synchronisiert: {len(synced)}")
        except Exception as e:
            print(f"❌ Sync Fehler: {e}")


bot = MyBot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    print("❌ Kein Bot-Token gefunden!")
else:
    bot.run(TOKEN)