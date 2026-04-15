import discord
from discord import app_commands
from discord.ext import commands
import asyncio


# ----------------------------
# 🔐 ADMIN CHECK (Rollen/Permissions)
# ----------------------------
def is_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


# ----------------------------
# 🧹 USER MESSAGE DELETE
# ----------------------------
async def delete_user_messages(channel: discord.TextChannel, user: discord.User, limit: int):
    deleted = 0

    async for message in channel.history(limit=limit):
        if message.author.id == user.id:
            try:
                await message.delete()
                deleted += 1
                await asyncio.sleep(0.15)
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

    return deleted


# ----------------------------
# COG
# ----------------------------
class CleanCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================
    # /clean_user
    # =========================
    @app_commands.command(
        name="clean_user",
        description="Löscht Nachrichten eines Users im aktuellen Channel"
    )
    @is_admin()
    async def clean_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        limit: int = 500
    ):
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        deleted = await delete_user_messages(channel, user, limit)

        await interaction.followup.send(
            f"✅ Gelöscht: {deleted} Nachrichten von {user.mention}",
            ephemeral=True
        )

    # =========================
    # /clean
    # =========================
    @app_commands.command(
        name="clean",
        description="Löscht Nachrichten in einem ausgewählten Channel"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def clean(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        limit: int = 500
    ):
        await interaction.response.defer(ephemeral=True)

        deleted = 0

        async for message in channel.history(limit=limit):
            try:
                await message.delete()
                deleted += 1
                await asyncio.sleep(0.15)
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

        await interaction.followup.send(
            f"✅ {deleted} Nachrichten in {channel.mention} gelöscht!",
            ephemeral=True
        )


# ----------------------------
# SETUP (WICHTIG)
# ----------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(CleanCog(bot))