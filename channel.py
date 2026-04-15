import discord
from discord.ext import commands
import json
from pathlib import Path

# Diese Datei stellt einen Cog bereit, der dynamische Voice-Kanäle erstellt.
# Nutzung: import channel; channel.setup(bot)

DEFAULT_TRIGGER_NAME = "➕ new channel"
DEFAULT_BASE_NAME = "voice channel"
DEFAULT_USER_LIMIT = 0


class VoiceChannelManager(commands.Cog):
    def __init__(self, bot, trigger_name: str = DEFAULT_TRIGGER_NAME, base_name: str = DEFAULT_BASE_NAME, user_limit: int = DEFAULT_USER_LIMIT):
        self.bot = bot
        self.trigger_name = trigger_name
        self.base_name = base_name
        self.user_limit = user_limit
        
        # Cache-Datei in __pycache__ für Persistenz
        old_cache = Path(__file__).parent / "channel_cache.json"
        cache_dir = Path(__file__).parent / "__pycache__"
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_file = cache_dir / "channel_cache.json"
            # Migrate alte Cache-Datei falls vorhanden
            if old_cache.exists() and not self._cache_file.exists():
                try:
                    old_cache.replace(self._cache_file)
                except Exception:
                    pass
        except Exception:
            self._cache_file = old_cache
        
        self.created_channels = {}  # {guild_id: [channel_ids]}
        self._pruned = False  # Flag um sicherzustellen, dass Pruning nur einmal läuft
        self._load_cache()

    def _load_cache(self):
        try:
            if self._cache_file.exists():
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.created_channels = {int(k): v for k, v in data.get("created_channels", {}).items()}
        except Exception:
            self.created_channels = {}

    def _save_cache(self):
        try:
            data = {
                "created_channels": {str(k): v for k, v in self.created_channels.items()}
            }
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Fehler beim Speichern der Channel-Cache: {e}")

    async def _prune_cache(self):
        """Entfernt Einträge für Gilden/Channels, die nicht mehr existieren oder löscht leere Channels."""
        changed = False
        for guild_id in list(self.created_channels.keys()):
            guild = self.bot.get_guild(guild_id)
            
            # Prüfe ob Guild noch existiert
            if not guild:
                self.created_channels.pop(guild_id, None)
                changed = True
                print(f"Guild {guild_id} nicht mehr vorhanden, Cache gelöscht")
                continue
            
            # Prüfe ob Bot noch auf dem Server ist
            if not guild.me:
                self.created_channels.pop(guild_id, None)
                changed = True
                print(f"Bot nicht mehr auf Guild {guild_id}, Cache gelöscht")
                continue
            
            # Entfernt Channel-IDs, die nicht mehr existieren oder kümmert sich um leere Channels
            valid_channels = []
            for channel_id in self.created_channels[guild_id]:
                channel = guild.get_channel(channel_id)
                if channel is not None:
                    # Prüfe ob Bot Zugriff auf Channel hat
                    perms = channel.permissions_for(guild.me)
                    if not perms.view_channel:
                        changed = True
                        print(f"Bot hat keinen Zugriff auf Channel {channel_id}, aus Cache gelöscht")
                        continue
                    
                    # Wenn Channel leer ist, lösche ihn
                    if len(channel.members) == 0:
                        try:
                            await channel.delete()
                            changed = True
                            print(f"Leerer Channel {channel_id} ({channel.name}) wurde gelöscht")
                        except Exception as e:
                            print(f"Fehler beim Löschen von Channel {channel_id}: {e}")
                            valid_channels.append(channel_id)
                    else:
                        valid_channels.append(channel_id)
                else:
                    changed = True
                    print(f"Channel {channel_id} nicht mehr vorhanden, aus Cache gelöscht")
            
            self.created_channels[guild_id] = valid_channels
        
        if changed:
            self._save_cache()
            print("Channel-Cache bereinigt und gespeichert")

    def get_next_channel_number(self, channels):
        numbers = []
        for ch in channels:
            if self.base_name in ch.name:
                parts = ch.name.split()
                if parts and parts[0].isdigit():
                    numbers.append(int(parts[0]))
        return max(numbers, default=0) + 1

    @commands.Cog.listener()
    async def on_ready(self):
        # Führe Pruning nur einmal nach dem Bot-Start aus
        if not self._pruned:
            self._pruned = True
            try:
                await self._prune_cache()
            except Exception as e:
                print(f"Fehler beim Prunen der Channel-Cache: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        existing = discord.utils.get(guild.voice_channels, name=self.trigger_name)
        if not existing:
            await guild.create_voice_channel(self.trigger_name)
            print(f"{self.trigger_name} wurde erstellt in {guild.name}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild

        # Nutzer betritt den Trigger-Kanal -> neuen Kanal erstellen und verschieben
        if after and after.channel and after.channel.name == self.trigger_name:
            number = self.get_next_channel_number(guild.voice_channels)
            new_channel_name = f"{number} {self.base_name}"

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, move_members=True)
            }

            new_channel = await guild.create_voice_channel(
                new_channel_name,
                overwrites=overwrites,
                user_limit=self.user_limit,
            )

            # Speichern der erstellten Channel-ID
            if guild.id not in self.created_channels:
                self.created_channels[guild.id] = []
            self.created_channels[guild.id].append(new_channel.id)
            self._save_cache()

            try:
                await member.move_to(new_channel)
            except Exception as e:
                print(f"Fehler beim Verschieben von {member}: {e}")
            else:
                print(f"{member} wurde in {new_channel_name} verschoben")

        # Nur bot-erstellte leere Kanäle löschen
        if before and before.channel and (before.channel != (after.channel if after else None)):
            if before.channel.name != self.trigger_name and len(before.channel.members) == 0:
                # Prüfe, ob dieser Channel vom Bot erstellt wurde
                if guild.id in self.created_channels and before.channel.id in self.created_channels[guild.id]:
                    try:
                        await before.channel.delete()
                        self.created_channels[guild.id].remove(before.channel.id)
                        self._save_cache()
                        print(f"Leerer Channel {before.channel.name} wurde gelöscht")
                    except Exception as e:
                        print(f"Fehler beim Löschen von {before.channel.name}: {e}")


async def setup(bot):
    await bot.add_cog(VoiceChannelManager(bot))