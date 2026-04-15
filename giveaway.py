import discord
import asyncio
import random
import re
import json
from pathlib import Path
from discord import app_commands
from discord.ext import commands


class GiveawayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_giveaways = {}
        self.bot.active_giveaways = self.active_giveaways

        self.cache_file = Path(__file__).parent / "giveaway_cache.json"

    # =========================
    # ROLE CHECK
    # =========================
    def has_role(self, interaction: discord.Interaction):
        role = discord.utils.get(interaction.guild.roles, name="GiveawayCreator")
        return role in interaction.user.roles if role else False

    # =========================
    # TIME PARSER
    # =========================
    def parse_duration(self, text: str) -> int:
        pattern = r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?"
        match = re.fullmatch(pattern, text.strip())

        if not match:
            raise ValueError("Format z.B. 1d2h30m15s")

        d, h, m, s = match.groups(default="0")
        return int(d) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)

    # =========================
    # FORMAT TIME
    # =========================
    def format_time(self, sec: int):
        d, r = divmod(sec, 86400)
        h, r = divmod(r, 3600)
        m, s = divmod(r, 60)

        parts = []
        if d:
            parts.append(f"{d}d")
        if h:
            parts.append(f"{h}h")
        if m:
            parts.append(f"{m}m")
        parts.append(f"{s}s")

        return " ".join(parts)

    # =========================
    # SAVE / LOAD
    # =========================
    def save(self):
        data = []

        for mid, view in self.active_giveaways.items():
            if not view.message:
                continue

            data.append({
                "message_id": mid,
                "channel_id": view.message.channel.id,
                "guild_id": view.message.guild.id,
                "prize": view.prize,
                "remaining": view.remaining,
                "winners": view.winner_count,
                "starter_id": view.starter.id,
                "participants": [u.id for u in view.participants],
                "image": view.image_url
            })

        self.cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def load(self):
        if not self.cache_file.exists():
            return

        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except:
            return

        for g in data:
            guild = self.bot.get_guild(g["guild_id"])
            if not guild:
                continue

            channel = guild.get_channel(g["channel_id"])
            if not channel:
                continue

            try:
                msg = await channel.fetch_message(g["message_id"])
            except:
                continue

            view = self.GiveawayView(
                self,
                g["prize"],
                g["remaining"],
                g["winners"],
                discord.Object(id=g["starter_id"])
            )

            view.message = msg
            view.image_url = g.get("image")

            for uid in g["participants"]:
                member = guild.get_member(uid)
                if member:
                    view.participants.add(member)

            self.active_giveaways[msg.id] = view
            asyncio.create_task(view.countdown())

    # =========================
    # PAYMENT VIEW (CLEAN)
    # =========================
    class PaymentView(discord.ui.View):
        def __init__(self, cog, winner, prize):
            super().__init__(timeout=86400)
            self.cog = cog
            self.winner = winner
            self.prize = prize

        @discord.ui.button(label="💰 Kann bezahlen", style=discord.ButtonStyle.green)
        async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):

            await interaction.response.send_message(
                "✅ Bestätigt. Gewinner wird informiert.",
                ephemeral=True
            )

            try:
                await interaction.message.delete()
            except:
                try:
                    await interaction.message.edit(view=None)
                except:
                    pass

            try:
                dm = discord.Embed(
                    title="🎉 Gewinn bestätigt!",
                    description="Bitte melde dich beim Ersteller oder warte auf seine Nachricht.",
                    color=discord.Color.green()
                )
                await self.winner.send(embed=dm)
            except:
                pass

        @discord.ui.button(label="❌ Kann nicht bezahlen", style=discord.ButtonStyle.red)
        async def no(self, interaction: discord.Interaction, button: discord.ui.Button):

            await interaction.response.send_message(
                "⚠️ Hinweis wen du das zu heufig machst kann dir die rolle entzogen werden oder ich werde dich nicht mehr unterstützen.",
                ephemeral=True
            )

            try:
                await interaction.message.delete()
            except:
                try:
                    await interaction.message.edit(view=None)
                except:
                    pass

            try:
                dm = discord.Embed(
                    title="⚠️ Giveaway Problem",
                    description="Der Ersteller kann das Giveaway aktuell nicht erfüllen.",
                    color=discord.Color.red()
                )
                dm.add_field(
                    name="Info",
                    value="Der Bot ist nicht verantwortlich für externe Abmachungen.",
                    inline=False
                )

                await self.winner.send(embed=dm)
            except:
                pass

    # =========================
    # GIVEAWAY VIEW
    # =========================
    class GiveawayView(discord.ui.View):
        def __init__(self, cog, prize, duration, winners, starter):
            super().__init__(timeout=None)
            self.cog = cog
            self.prize = prize
            self.remaining = duration
            self.winner_count = winners
            self.starter = starter
            self.participants = set()
            self.message = None
            self.ended = False
            self.image_url = None

        @discord.ui.button(label="🎉 Teilnehmen", style=discord.ButtonStyle.green)
        async def join(self, interaction: discord.Interaction, button: discord.ui.Button):

            if self.ended:
                return await interaction.response.send_message("Giveaway beendet.", ephemeral=True)

            if interaction.user in self.participants:
                return await interaction.response.send_message("Schon dabei!", ephemeral=True)

            self.participants.add(interaction.user)

            await interaction.response.send_message("Du bist dabei 🎉", ephemeral=True)
            await self.update()

        async def update(self):
            if not self.message:
                return

            embed = self.message.embeds[0]
            embed.description = f"Noch: **{self.cog.format_time(self.remaining)}**"

            embed.set_field_at(
                0,
                name="Teilnehmer",
                value=str(len(self.participants)),
                inline=False
            )

            try:
                await self.message.edit(embed=embed, view=self)
            except:
                pass

        async def countdown(self):
            while self.remaining > 0 and not self.ended:
                await asyncio.sleep(1)
                self.remaining -= 1
                await self.update()

            if not self.ended:
                await self.end()

        async def end(self):
            self.ended = True

            embed = self.message.embeds[0]

            if self.participants:
                winners = random.sample(
                    list(self.participants),
                    min(self.winner_count, len(self.participants))
                )

                mentions = ", ".join(w.mention for w in winners)

                embed.description = "🎉 GIVEAWAY BEENDET"
                embed.color = discord.Color.gold()
                embed.add_field(name="🏆 Gewinner", value=mentions, inline=False)

                await self.message.edit(embed=embed, view=None)

                for w in winners:
                    try:
                        dm = discord.Embed(
                            title="🎉 Du hast gewonnen!",
                            description=f"Preis: **{self.prize}**",
                            color=discord.Color.gold()
                        )
                        dm.add_field(name="Ersteller", value=self.starter.mention, inline=False)
                        await w.send(embed=dm)
                    except:
                        pass

                try:
                    dm = discord.Embed(
                        title="🎉 Giveaway abgeschlossen",
                        description=f"Gewinner: {mentions}",
                        color=discord.Color.blue()
                    )

                    await self.starter.send(
                        embed=dm,
                        view=GiveawayCog.PaymentView(self.cog, winners[0], self.prize)
                    )

                except:
                    pass

            else:
                embed.description = "Niemand hat teilgenommen 😢"
                embed.color = discord.Color.red()
                await self.message.edit(embed=embed, view=None)

            self.cog.active_giveaways.pop(self.message.id, None)
            self.cog.save()

    # =========================
    # GIVEAWAY COMMAND
    # =========================
    @app_commands.command(name="giveaway", description="Starte ein Giveaway")
    async def giveaway(self, interaction, prize: str, duration: str, winners: int = 1, image_url: str = None):

        if not self.has_role(interaction):
            return await interaction.response.send_message("❌ Keine Berechtigung", ephemeral=True)

        seconds = self.parse_duration(duration)

        embed = discord.Embed(
            title=f"🎉 Giveaway: {prize}",
            description=f"Noch: **{self.format_time(seconds)}**",
            color=discord.Color.green()
        )

        embed.add_field(name="Teilnehmer", value="0", inline=False)

        if image_url:
            embed.set_image(url=image_url)

        view = self.GiveawayView(self, prize, seconds, winners, interaction.user)

        await interaction.response.send_message("Giveaway gestartet!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        view.message = msg
        self.active_giveaways[msg.id] = view

        self.save()
        asyncio.create_task(view.countdown())

    # =========================
    # CANCEL COMMAND
    # =========================
    @app_commands.command(name="cancel", description="Beende ein Giveaway sofort")
    async def cancel(self, interaction: discord.Interaction, message_id: str):

        try:
            message_id = int(message_id)
        except:
            return await interaction.response.send_message("❌ Ungültig", ephemeral=True)

        if message_id not in self.active_giveaways:
            return await interaction.response.send_message("❌ Kein Giveaway", ephemeral=True)

        view = self.active_giveaways[message_id]

        if view.starter.id != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Keine Rechte", ephemeral=True)

        view.ended = True

        try:
            await view.message.delete()
        except:
            pass

        self.active_giveaways.pop(message_id, None)
        self.save()

        await interaction.response.send_message("✅ Giveaway beendet", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = GiveawayCog(bot)
    await bot.add_cog(cog)
    await cog.load()