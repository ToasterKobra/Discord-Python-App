import discord
from discord.ext import commands
from discord import app_commands
import asyncio

OWNER_ID = 911


# ----------------------------- MESSAGE MODAL -----------------------------
class MessageModal(discord.ui.Modal):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title=f"Nachricht an #{channel.name}")
        self.channel = channel

        self.msg = discord.ui.TextInput(
            label="Deine Nachricht",
            style=discord.TextStyle.long,
            placeholder="Schreib deine Nachricht hier..."
        )
        self.add_item(self.msg)

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.send(self.msg.value)

        await interaction.response.send_message(
            f"✅ Nachricht gesendet in **#{self.channel.name}**",
            ephemeral=True
        )


# ----------------------------- CHANNEL SELECT -----------------------------
class ChannelSelect(discord.ui.Select):
    def __init__(self, channels):
        options = [
            discord.SelectOption(
                label=c.name[:100],
                value=str(c.id)
            )
            for c in channels[:25]
        ]

        super().__init__(
            placeholder="Channel auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(int(self.values[0]))

        if not channel:
            return await interaction.response.send_message("❌ Channel nicht gefunden", ephemeral=True)

        await interaction.response.send_modal(MessageModal(channel))


class ChannelView(discord.ui.View):
    def __init__(self, channels):
        super().__init__(timeout=300)
        self.add_item(ChannelSelect(channels))


# ----------------------------- CONFIRMATION MODAL -----------------------------
class ConfirmationModal(discord.ui.Modal):
    def __init__(self, action_name: str):
        super().__init__(title=f"Bestätigung: {action_name}")
        self.confirmed = False

        self.input = discord.ui.TextInput(
            label="Tippe JA",
            placeholder="JA",
            style=discord.TextStyle.short
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        self.confirmed = self.input.value.strip().upper() == "JA"

        await interaction.response.send_message(
            "✅ bestätigt" if self.confirmed else "❌ abgebrochen",
            ephemeral=True
        )
        self.stop()


# ----------------------------- SERVER MANAGER -----------------------------
class ServerManager(discord.ui.View):
    def __init__(self, guilds):
        super().__init__(timeout=300)
        self.guilds = guilds
        self.page = 0
        self.selected_guild = None

        self.prev_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary)

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.update()

    def update(self):
        self.clear_items()

        start = self.page * 25
        end = start + 25

        options = [
            discord.SelectOption(
                label=g.name[:100],
                description=f"ID: {g.id} | Members: {g.member_count}",
                value=str(g.id)
            )
            for g in self.guilds[start:end]
        ]

        self.add_item(ServerSelect(options))
        self.add_item(ActionSelect())
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def prev_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update()
            await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if (self.page + 1) * 25 < len(self.guilds):
            self.page += 1
            self.update()
            await interaction.response.edit_message(view=self)


# ----------------------------- SERVER SELECT -----------------------------
class ServerSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="Server auswählen",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        view: ServerManager = self.view
        view.selected_guild = interaction.client.get_guild(int(self.values[0]))

        await interaction.response.send_message(
            f"✅ ausgewählt: **{view.selected_guild.name}**",
            ephemeral=True
        )


# ----------------------------- ACTIONS -----------------------------
class ActionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🚪 Leave", value="leave"),
            discord.SelectOption(label="✉ Message", value="message"),
            discord.SelectOption(label="📄 Copy", value="copy"),
            discord.SelectOption(label="🔗 Invite", value="invite"),
        ]

        super().__init__(placeholder="Aktion wählen", options=options)

    async def callback(self, interaction: discord.Interaction):
        view: ServerManager = self.view

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ kein Zugriff", ephemeral=True)

        if not view.selected_guild:
            return await interaction.response.send_message("⚠ kein Server gewählt", ephemeral=True)

        guild = view.selected_guild
        action = self.values[0]

        # ---------------- LEAVE (FIXED) ----------------
        if action == "leave":
            await interaction.response.defer(ephemeral=True)
            await guild.leave()
            await interaction.response.send_message("🚪 verlassen", ephemeral=True)

        # ---------------- MESSAGE ----------------
        elif action == "message":
            channels = [
                c for c in guild.text_channels
                if c.permissions_for(guild.me).send_messages
            ]

            if not channels:
                return await interaction.response.send_message(
                    "❌ keine Channels",
                    ephemeral=True
                )

            await interaction.response.send_message(
                "📌 Channel auswählen:",
                view=ChannelView(channels),
                ephemeral=True
            )

        # ---------------- INVITE ----------------
        elif action == "invite":
            ch = discord.utils.get(guild.text_channels)

            if not ch:
                return await interaction.response.send_message("❌ kein Channel", ephemeral=True)

            invite = await ch.create_invite(max_age=3600)
            await interaction.response.send_message(str(invite), ephemeral=True)

        # ---------------- COPY ----------------
        elif action == "copy":
            modal = ConfirmationModal("Copy")
            await interaction.response.send_modal(modal)
            await modal.wait()

            if modal.confirmed:
                await interaction.followup.send("🚀 Copy startet...", ephemeral=True)
                await safe_copy(interaction.client, interaction, guild)


# ----------------------------- SAFE COPY -----------------------------
async def safe_copy(bot: discord.Client, interaction: discord.Interaction, source: discord.Guild):
    target = discord.utils.find(lambda g: g.id != source.id, bot.guilds)

    if not target:
        return

    for c in list(target.channels):
        try:
            await c.delete()
            await asyncio.sleep(0.2)
        except:
            pass

    # ---------------- ROLES (FIX: duplicates removed) ----------------
    role_map = {}

    for r in source.roles:
        if r.is_default():
            continue

        for existing in target.roles:
            if existing.name == r.name and not existing.is_default():
                try:
                    await existing.delete()
                except:
                    pass

        try:
            role_map[r.id] = await target.create_role(
                name=r.name,
                permissions=r.permissions
            )
        except:
            pass

    cat_map = {}

    for cat in source.categories:
        try:
            cat_map[cat.id] = await target.create_category(name=cat.name)
        except:
            pass

    for ch in source.text_channels:
        try:
            await target.create_text_channel(
                name=ch.name,
                category=cat_map.get(ch.category_id)
            )
        except:
            pass

    for ch in source.voice_channels:
        try:
            await target.create_voice_channel(
                name=ch.name,
                category=cat_map.get(ch.category_id)
            )
        except:
            pass

    try:
        await interaction.channel.send("✅ Copy fertig")
    except:
        pass


# ----------------------------- COG -----------------------------
class ServerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="server", description="Admin Panel")
    async def server(self, interaction: discord.Interaction):

        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ kein Zugriff", ephemeral=True)

        guilds = sorted(self.bot.guilds, key=lambda g: g.name)

        await interaction.response.send_message(
            "🛠 Panel geöffnet",
            view=ServerManager(guilds),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerCog(bot))