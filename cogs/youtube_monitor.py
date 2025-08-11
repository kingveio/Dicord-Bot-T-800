import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime

# Configuração do logger para este cog
logger = logging.getLogger("T-800")

class YouTubeMonitor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_role_name = "AO VIVO"
        self.monitor_youtube_streams.start()
        logger.info("✅ Módulo de monitoramento do YouTube inicializado.")

    def cog_unload(self):
        self.monitor_youtube_streams.stop()
        logger.info("❌ Módulo de monitoramento do YouTube descarregado.")

    @tasks.loop(minutes=5)
    async def monitor_youtube_streams(self):
        """Verifica periodicamente os canais do YouTube monitorados."""
        if not self.bot.system_ready or not self.bot.youtube_api:
            return

        logger.info("🔍 Análise de alvos YouTube iniciada...")
        try:
            data = await self.bot.get_data()
            if not data:
                logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
                return

            monitored_yt = data["monitored_users"].get("youtube", {})
            if monitored_yt:
                channels_to_check = list(monitored_yt.keys())
                live_status = await self.bot.youtube_api.check_live_channels(channels_to_check)

                for channel_name, is_live in live_status.items():
                    user_info = monitored_yt.get(channel_name.lower())
                    if not user_info: continue

                    guild = self.bot.get_guild(user_info.get("guild_id"))
                    member = guild.get_member(user_info.get("added_by")) if guild else None
                    if not member: continue

                    live_role = discord.utils.get(guild.roles, name=self.live_role_name)
                    if not live_role: continue

                    if is_live:
                        if live_role not in member.roles:
                            await member.add_roles(live_role, reason="Canal do YouTube está ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (YouTube). Missão concluída.")
                    else:
                        if live_role in member.roles:
                            await member.remove_roles(live_role, reason="Canal do YouTube não está mais ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (YouTube). Missão concluída.")

        except Exception as e:
            logger.error(f"❌ Falha no monitoramento do YouTube: {e}. Alerta: Falha na operação.")

    # ========== COMANDOS DE ADMINISTRAÇÃO ========== #
    @app_commands.command(name="adicionar_yt", description="Adiciona um canal do YouTube para monitoramento")
    @app_commands.describe(
        nome="Nome do canal do YouTube",
        usuario="O usuário do Discord a ser vinculado"
    )
    async def adicionar_yt(self, interaction: discord.Interaction, nome: str, usuario: discord.Member):
        """Adiciona um canal do YouTube à lista de monitoramento."""
        await interaction.response.defer(ephemeral=True)
        try:
            # Novo passo: valida o nome do canal antes de salvar
            is_valid = await self.bot.youtube_api.validate_channel_name(nome)
            if not is_valid:
                await interaction.edit_original_response(
                    content=f"⚠️ O canal '{nome}' não pôde ser encontrado. Por favor, verifique o nome. Alerta: Falha na operação."
                )
                return

            data = await self.bot.get_data()
            response_content = ""

            if "youtube" not in data["monitored_users"]:
                data["monitored_users"]["youtube"] = {}
            
            if nome.lower() in data["monitored_users"]["youtube"]:
                response_content = f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
            else:
                data["monitored_users"]["youtube"][nome.lower()] = {
                    "added_by": usuario.id,
                    "added_at": datetime.now().isoformat(),
                    "guild_id": interaction.guild.id
                }
                await self.bot.save_data()
                response_content = f"✅ **{nome}** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."

            await interaction.edit_original_response(content=response_content)

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar alvo do YouTube: {e}. Alerta: Falha na operação.")
            await interaction.edit_original_response(content=f"❌ Erro ao adicionar alvo do YouTube: {e}. Alerta: Falha na operação.")

    @app_commands.command(name="remover_yt", description="Remove um canal do YouTube do monitoramento")
    @app_commands.describe(
        nome="Nome do canal do YouTube"
    )
    async def remover_yt(self, interaction: discord.Interaction, nome: str):
        """Remove um canal do YouTube da lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await self.bot.get_data()

            if "youtube" in data["monitored_users"] and nome.lower() not in data["monitored_users"]["youtube"]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} não é um alvo! Alerta: Falha na operação."
                )

            del data["monitored_users"]["youtube"][nome.lower()]
            await self.bot.save_data()

            await interaction.edit_original_response(
                content=f"✅ **{nome}** removido do sistema. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao remover alvo do YouTube: {e}. Alerta: Falha na operação."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeMonitor(bot))
