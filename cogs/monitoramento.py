import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from data_manager import get_data, save_data

logger = logging.getLogger("T-800")

class Monitoramento(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_role = bot.live_role
        self.monitor_streams.start()
        logger.info("✅ Módulo de monitoramento da Twitch inicializado.")

    def cog_unload(self):
        self.monitor_streams.stop()
        logger.info("❌ Módulo de monitoramento da Twitch descarregado.")

    @tasks.loop(minutes=3)
    async def monitor_streams(self):
        """Verifica periodicamente os streamers monitorados na Twitch."""
        if not self.bot.system_ready:
            return

        logger.info("🔍 Análise de alvos Twitch iniciada...")
        try:
            data = await get_data()
            if not data:
                logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
                return

            if data["monitored_users"]["twitch"]:
                streamers = list(data["monitored_users"]["twitch"].keys())
                live_status = await self.bot.twitch_api.check_live_channels(streamers)

                for streamer_name, is_live in live_status.items():
                    user_info = data["monitored_users"]["twitch"].get(streamer_name.lower())
                    if not user_info: continue

                    guild = self.bot.get_guild(user_info.get("guild_id"))
                    member = guild.get_member(user_info.get("added_by")) if guild else None
                    if not member: continue

                    live_role = discord.utils.get(guild.roles, name=self.live_role)
                    if not live_role: continue

                    if is_live:
                        if live_role not in member.roles:
                            await member.add_roles(live_role, reason="Streamer está ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (Twitch). Missão concluída.")
                    else:
                        if live_role in member.roles:
                            await member.remove_roles(live_role, reason="Streamer não está mais ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (Twitch). Missão concluída.")

        except Exception as e:
            logger.error(f"❌ Falha no monitoramento: {e}. Alerta: Falha na operação.")

    # ========== COMANDOS DE ADMINISTRAÇÃO ========== #
    @app_commands.command(name="adicionar", description="Adiciona um streamer para monitoramento")
    @app_commands.describe(
        plataforma="Plataforma do canal (twitch)",
        nome="Nome do canal da Twitch",
        usuario="O usuário do Discord a ser vinculado"
    )
    @app_commands.choices(plataforma=[
        app_commands.Choice(name="Twitch", value="twitch")
    ])
    async def adicionar_streamer(self, interaction: discord.Interaction, plataforma: str, nome: str, usuario: discord.Member):
        """Adiciona um streamer à lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await get_data()
            plataforma = plataforma.lower()

            if plataforma != "twitch":
                return await interaction.edit_original_response(content="❌ Plataforma inválida! Alerta: Falha na operação.")

            if nome.lower() in data["monitored_users"][plataforma]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
                )
            
            data["monitored_users"][plataforma][nome.lower()] = {
                "added_by": usuario.id,
                "added_at": datetime.now().isoformat(),
                "guild_id": interaction.guild.id
            }
            await save_data(self.bot.drive_service)
            await interaction.edit_original_response(
                content=f"✅ **{nome}** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao adicionar alvo: {e}. Alerta: Falha na operação."
            )

    @app_commands.command(name="remover", description="Remove um streamer do monitoramento")
    @app_commands.describe(
        plataforma="Plataforma do canal (twitch)",
        nome="Nome do canal da Twitch"
    )
    @app_commands.choices(plataforma=[
        app_commands.Choice(name="Twitch", value="twitch")
    ])
    async def remover_streamer(self, interaction: discord.Interaction, plataforma: str, nome: str):
        """Remove um streamer da lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await get_data()
            plataforma = plataforma.lower()

            if plataforma != "twitch":
                return await interaction.edit_original_response(content="❌ Plataforma inválida! Alerta: Falha na operação.")

            if nome.lower() not in data["monitored_users"][plataforma]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} não é um alvo! Alerta: Falha na operação."
                )

            del data["monitored_users"][plataforma][nome.lower()]
            await save_data(self.bot.drive_service)

            await interaction.edit_original_response(
                content=f"✅ **{nome}** removido do sistema. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao remover alvo: {e}. Alerta: Falha na operação."
            )

    @app_commands.command(name="listar", description="Mostra a lista de alvos monitorados")
    async def listar_streamers(self, interaction: discord.Interaction):
        """Exibe a lista de usuários monitorados."""
        await interaction.response.defer(ephemeral=True)
        data = await get_data()
        
        output = "🤖 **RELATÓRIO DE ALVOS**\n\n"
        
        twitch_output = []
        for streamer, info in data["monitored_users"]["twitch"].items():
            member = interaction.guild.get_member(info.get("added_by"))
            twitch_output.append(
                f"**Plataforma:** Twitch\n"
                f"**Nome do canal:** {streamer}\n"
                f"**Usuário:** {member.mention if member else 'Desconhecido'}\n"
            )

        if twitch_output:
            output += "--- Twitch ---\n" + "\n".join(twitch_output) + "\n"
        else:
            output += "Nenhum alvo da Twitch encontrado no sistema."

        await interaction.edit_original_response(content=output)
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Monitoramento(bot))
