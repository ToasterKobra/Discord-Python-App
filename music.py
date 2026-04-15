import discord
from discord.ext import commands
import yt_dlp
import asyncio
from collections import deque

# ─────────────────────────────
# MusicPlayer-Klasse
# ─────────────────────────────
class MusicPlayer:
    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild
        self.voice_client = None
        self.queue = deque()
        self.current = None
        self.loop = False
        self.volume = 0.5
        self.disconnect_timer = None
        self.now_playing_message = None
        self.update_task = None
        self.start_time = 0

    async def connect(self, channel):
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()

        # Optional: Auto-Deafen (empfohlen)
        try:
            await self.guild.me.edit(deafen=True)
        except:
            pass

        self.reset_disconnect_timer()

    def reset_disconnect_timer(self):
        if self.disconnect_timer:
            self.disconnect_timer.cancel()
        self.disconnect_timer = asyncio.create_task(self.auto_disconnect())

    async def auto_disconnect(self):
        await asyncio.sleep(300)
        if self.voice_client and self.voice_client.is_connected():
            await self.stop()

    async def play_next(self):
        if self.loop and self.current:
            self.queue.appendleft(self.current)

        if self.queue:
            next_song = self.queue.popleft()
            self.current = next_song
            await self.play_song(next_song)
        else:
            if self.loop and self.current:
                await self.play_song(self.current)
            else:
                self.current = None
                self.reset_disconnect_timer()
                if self.now_playing_message:
                    try:
                        await self.now_playing_message.delete()
                    except discord.NotFound:
                        pass
                    finally:
                        self.now_playing_message = None

    async def play_song(self, song):
        # 🔊 AUTO-UNMUTE (Server-Mute Fix)
        if self.guild.me.voice and self.guild.me.voice.mute:
            try:
                await self.guild.me.edit(mute=False)
            except Exception as e:
                print(f"Entmute Fehler: {e}")

        self.start_time = asyncio.get_event_loop().time()
        url = song['url']

        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True}
        loop = asyncio.get_event_loop()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                audio_url = info['url']

            before_options = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(audio_url, before_options=before_options),
                volume=self.volume
            )

            def after_play(error):
                if error:
                    print(f"Fehler beim Abspielen: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(), self.bot.loop)

            self.voice_client.play(source, after=after_play)
            await self.start_now_playing()
        except yt_dlp.utils.DownloadError as e:
            print(f"Fehler beim Laden von {url}: {e}")
            await self.play_next()

    async def start_now_playing(self):
        if self.update_task:
            self.update_task.cancel()
        self.update_task = asyncio.create_task(self.update_now_playing_loop())

    async def update_now_playing_loop(self):
        try:
            while self.voice_client and self.current:
                if self.now_playing_message:
                    embed = self.create_now_playing_embed()
                    try:
                        await self.now_playing_message.edit(embed=embed, view=MusicControls(self))
                    except discord.NotFound:
                        channel = self.now_playing_message.channel
                        self.now_playing_message = await channel.send(embed=embed, view=MusicControls(self))
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    def create_now_playing_embed(self):
        embed = discord.Embed(color=discord.Color.green())
        if not self.current:
            embed.title = "🎧 Kein Song"
            embed.description = "Es wird gerade nichts abgespielt."
        else:
            now = asyncio.get_event_loop().time()
            elapsed = int(now - self.start_time)
            duration = self.current.get("duration", 0)

            def format_time(sec):
                m, s = divmod(int(sec), 60)
                return f"{m}:{s:02d}"

            queue_count = len(self.queue)
            desc = f"[{self.current['title']}]({self.current['url']}) `[{format_time(elapsed)}/{format_time(duration)}]`"
            if queue_count > 0:
                desc += f"\n➕ **{queue_count} weitere Songs in der Warteschlange**"

            embed.title = "🎧 Now Playing"
            embed.description = desc

        embed.set_footer(text=f"🔁 {'An' if self.loop else 'Aus'} | 🔊 {int(self.volume*100)}%")
        return embed

    async def add_to_queue(self, query):
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
        loop = asyncio.get_event_loop()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(f'ytsearch:{query}', download=False))
                if 'entries' in info and info['entries']:
                    entry = info['entries'][0]
                    url = f"https://www.youtube.com/watch?v={entry['id']}"
                    title = entry['title']
                    duration = entry.get('duration', 0)
                    self.queue.append({'url': url, 'title': title, 'duration': duration})
                    return title
        except yt_dlp.utils.DownloadError as e:
            print(f"Fehler beim Suchen von {query}: {e}")
        return None

    async def skip(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()

    async def stop(self):
        self.queue.clear()
        self.current = None
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        if self.disconnect_timer:
            self.disconnect_timer.cancel()
        if self.update_task:
            self.update_task.cancel()
        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except discord.NotFound:
                pass
            finally:
                self.now_playing_message = None
        if self.voice_client:
            await self.voice_client.disconnect()
        self.voice_client = None

    def set_loop(self, loop):
        self.loop = loop

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        if self.voice_client and self.voice_client.source:
            self.voice_client.source.volume = self.volume


# ─────────────────────────────
# MusicControls View
# ─────────────────────────────
class MusicControls(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        await self.player.skip()

    @discord.ui.button(label="🔁", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        self.player.set_loop(not self.player.loop)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        await self.player.stop()

    @discord.ui.button(label="🔊", style=discord.ButtonStyle.secondary)
    async def vol_up_button(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        self.player.set_volume(self.player.volume + 0.1)

    @discord.ui.button(label="🔉", style=discord.ButtonStyle.secondary)
    async def vol_down_button(self, interaction: discord.Interaction, button):
        await interaction.response.defer()
        self.player.set_volume(self.player.volume - 0.1)


# ─────────────────────────────
# Music Cog mit Slash-Commands
# ─────────────────────────────
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    @discord.app_commands.command(name="play", description="Spiele Musik von YouTube ab")
    async def play(self, interaction: discord.Interaction, query: str):
        guild = interaction.guild
        if not guild or not interaction.user.voice:
            await interaction.response.send_message(
                "Du musst in einem Voice-Kanal sein!",
                ephemeral=True,
                delete_after=3
            )
            return

        player = self.players.get(guild.id)
        if not player:
            player = MusicPlayer(self.bot, guild)
            self.players[guild.id] = player

        await player.connect(interaction.user.voice.channel)
        title = await player.add_to_queue(query)

        if not title:
            await interaction.response.send_message(
                "Kein Ergebnis gefunden.",
                ephemeral=True,
                delete_after=3
            )
            return

        await interaction.response.send_message(
            f"🎶 **{title}** wurde zur Warteschlange hinzugefügt.",
            ephemeral=True,
            delete_after=2
        )

        embed = player.create_now_playing_embed()
        if player.now_playing_message:
            try:
                await player.now_playing_message.edit(embed=embed, view=MusicControls(player))
            except discord.NotFound:
                player.now_playing_message = await interaction.channel.send(embed=embed, view=MusicControls(player))
        else:
            player.now_playing_message = await interaction.channel.send(embed=embed, view=MusicControls(player))

        if not player.voice_client.is_playing() and not player.current:
            await player.play_next()

    @discord.app_commands.command(name="skip", description="Überspringe den aktuellen Song")
    async def skip(self, interaction: discord.Interaction):
        guild = interaction.guild
        player = self.players.get(guild.id)
        if player and player.voice_client and player.voice_client.is_playing():
            await player.skip()
            await interaction.response.send_message(
                "Der Song wurde übersprungen.",
                ephemeral=True,
                delete_after=2
            )
        else:
            await interaction.response.send_message(
                "Es läuft keine Musik.",
                ephemeral=True,
                delete_after=2
            )

    @discord.app_commands.command(name="stop", description="Stoppe die Musik und verlasse den Voice-Channel")
    async def stop(self, interaction: discord.Interaction):
        guild = interaction.guild
        player = self.players.get(guild.id)
        if player:
            await player.stop()
            await interaction.response.send_message(
                "Die Musik wurde gestoppt und der Bot hat den Voice-Channel verlassen.",
                ephemeral=True,
                delete_after=2
            )
        else:
            await interaction.response.send_message(
                "Es läuft keine Musik.",
                ephemeral=True,
                delete_after=2
            )

    @discord.app_commands.command(name="loop", description="Schalte die Loop-Funktion ein oder aus")
    async def loop(self, interaction: discord.Interaction):
        guild = interaction.guild
        player = self.players.get(guild.id)
        if player:
            player.set_loop(not player.loop)
            await interaction.response.send_message(
                f"Loop ist nun {'ein' if player.loop else 'aus'}.",
                ephemeral=True,
                delete_after=2
            )
        else:
            await interaction.response.send_message(
                "Es läuft keine Musik.",
                ephemeral=True,
                delete_after=2
            )

    @discord.app_commands.command(name="volume", description="Setze die Lautstärke (0 bis 100)")
    async def volume(self, interaction: discord.Interaction, volume: int):
        if 0 <= volume <= 100:
            guild = interaction.guild
            player = self.players.get(guild.id)
            if player:
                player.set_volume(volume / 100)
                await interaction.response.send_message(
                    f"Lautstärke auf {volume}% gesetzt.",
                    ephemeral=True,
                    delete_after=2
                )
            else:
                await interaction.response.send_message(
                    "Es läuft keine Musik.",
                    ephemeral=True,
                    delete_after=2
                )
        else:
            await interaction.response.send_message(
                "Lautstärke muss zwischen 0 und 100 liegen.",
                ephemeral=True,
                delete_after=2
            )

    @discord.app_commands.command(name="queue", description="Zeige die Warteschlange an")
    async def queue(self, interaction: discord.Interaction):
        guild = interaction.guild
        player = self.players.get(guild.id)
        if player and player.queue:
            queue_list = "\n".join([f"{i + 1}. {song['title']}" for i, song in enumerate(player.queue)])
            await interaction.response.send_message(
                f"Warteschlange:\n{queue_list}",
                ephemeral=True,
                delete_after=2
            )
        else:
            await interaction.response.send_message(
                "Die Warteschlange ist leer.",
                ephemeral=True,
                delete_after=2
            )


# ─────────────────────────────
# Setup-Funktion für den Cog
# ─────────────────────────────
async def setup(bot):
    # Registriere den MusicCog beim Bot
    await bot.add_cog(MusicCog(bot))
    print("MusicCog wurde geladen.")