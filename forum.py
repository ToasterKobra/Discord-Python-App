import discord
from discord.ext import commands
from discord import app_commands


class ForumCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="post",
        description="Erstelle ein Embed (Nur für Admins/Support)"
    )
    async def post(
        self,
        interaction: discord.Interaction,
        titel: str,
        text: str,
        channel: discord.TextChannel,
        farbe: str = "blau",
        bild_url: str = None,
        quellen: str = None
    ):
        # 🔒 Rollen-Check (nach Namen)
        ALLOWED_ROLES = ["Admin", "Support"]

        user_roles = [role.name for role in interaction.user.roles]

        if not any(role in ALLOWED_ROLES for role in user_roles):
            return await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Command.",
                ephemeral=True
            )

        farben = {
            "rot": discord.Color.red(),
            "blau": discord.Color.blue(),
            "grün": discord.Color.green(),
            "gelb": discord.Color.yellow(),
            "lila": discord.Color.purple(),
            "orange": discord.Color.orange()
        }

        if farbe.lower() in farben:
            embed_color = farben[farbe.lower()]
        elif farbe.startswith("#"):
            try:
                embed_color = discord.Color(int(farbe[1:], 16))
            except ValueError:
                embed_color = discord.Color.blue()
        else:
            embed_color = discord.Color.blue()

        embed = discord.Embed(
            title=titel,
            description=text,
            color=embed_color
        )

        if bild_url:
            embed.set_image(url=bild_url)

        if quellen:
            embed.add_field(name="Quellen", value=quellen, inline=False)

        embed.set_footer(text=f"Erstellt von {interaction.user}")

        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Embed wurde in {channel.mention} gepostet!",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ForumCog(bot))