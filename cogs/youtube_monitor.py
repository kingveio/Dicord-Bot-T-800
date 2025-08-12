import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from data_manager import get_data, save_data

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
        """Verifica periodicamente os canais do YouTube monitorados e atualiza o estado unificado."""
        if not self.bot.system_ready or not self.bot.youtube_api:
            return

        logger.info("🔍 Análise de alvos YouTube iniciada...")
        try:
            data = await get_data()
            if not data:
                logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
                return

            monitored_yt = data["monitored_users"].get("youtube", {})
            if monitored_yt:
                channels_to_check = list(monitored_yt.keys())
                live_status = await self.bot.youtube_api.check_live_channels(channels_to_check)

                for channel_name, is_live in live_status.items():
                    user_info = monitored_yt.get(channel_name.lower())
                    if not user_info:
                        continue

                    member_id = user_info.get("added_by")
                    guild_id = user_info.get("guild_id")
                    
                    if member_id and guild_id:
                        if member_id not in self.bot.live_users:
                            self.bot.live_users[member_id] = {"twitch": False, "youtube": False, "guild_id": guild_id}

                        self.bot.live_users[member_id]["youtube"] = is_live
                        logger.debug(f"Status de live do YouTube para {member_id} atualizado para {is_live}.")
                        
        except Exception as e:
            logger.error(f"❌ Falha no monitoramento do YouTube: {e}. Alerta: Falha na operação.", exc_info=True)
            
    # ========== COMANDOS DE BARRA ========== #

@app_commands.command(name="adicionar_youtube", description="Adiciona um canal do YouTube para monitoramento.")
    @app_commands.describe(
        nome="Nome do canal do YouTube (ex: alanzoka)",
        discord_id="ID do usuário do Discord a ser marcado"
    )
    async def adicionar_youtube(self, interaction: discord.Interaction, nome: str, discord_id: str):
        """Comando de barra para adicionar um canal do YouTube à lista de monitoramento."""
        try:
            # Tenta responder imediatamente para evitar o timeout
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            # Se a interação já expirou, a gente não consegue responder, então apenas logamos o erro
            logger.error("❌ Falha ao deferir a interação. Token expirado. O bot está lento.", exc_info=True)
            return

        logger.info(f"Comando '/adicionar_youtube' acionado por {interaction.user.name} ({interaction.user.id}).")

        # ... o resto do seu código permanece o mesmo
        if not self.bot.youtube_api:
            await interaction.followup.send("⚠️ O serviço do YouTube não está disponível. Tente novamente mais tarde.")
            return
        
        # ... o resto do seu código
        channel_name = nome.lower().strip()
        
        try:
            data = await get_data()
            if not data:
                await interaction.followup.send("⚠️ Não foi possível carregar os dados. Alerta: Falha na operação.")
                return

            if channel_name in data["monitored_users"]["youtube"]:
                await interaction.followup.send(f"❌ O canal **{channel_name}** já está sendo monitorado.")
                return
            
            # ... resto da lógica
            data["monitored_users"]["youtube"][channel_name] = {
                "guild_id": interaction.guild_id,
                "added_by": discord_id,
                "timestamp": datetime.now().isoformat()
            }
            await save_data(data)
            
            await interaction.followup.send(f"✅ O canal **{channel_name}** foi adicionado à lista de monitoramento, vinculado ao usuário Discord com ID **{discord_id}**.")
            logger.info(f"Canal '{channel_name}' adicionado com sucesso.")

        except Exception as e:
            logger.error(f"❌ Falha ao adicionar canal '{channel_name}': {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro ao adicionar o canal.")

    @app_commands.command(name="remover_youtube", description="Remove um canal do YouTube do monitoramento.")
    @app_commands.describe(nome="Nome do canal do YouTube a ser removido (ex: alanzoka)")
    async def remover_youtube(self, interaction: discord.Interaction, nome: str):
        """Comando de barra para remover um canal do YouTube da lista de monitoramento."""
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Comando '/remover_youtube' acionado por {interaction.user.name} ({interaction.user.id}).")

        channel_name = nome.lower().strip()

        try:
            data = await get_data()
            if not data:
                await interaction.followup.send("⚠️ Não foi possível carregar os dados. Alerta: Falha na operação.")
                return

            if channel_name not in data["monitored_users"]["youtube"]:
                await interaction.followup.send(f"❌ O canal **{channel_name}** não está na lista de monitoramento.")
                return

            del data["monitored_users"]["youtube"][channel_name]
            await save_data(data)

            await interaction.followup.send(f"✅ O canal **{channel_name}** foi removido da lista de monitoramento.")
            logger.info(f"Canal '{channel_name}' removido com sucesso.")

        except Exception as e:
            logger.error(f"❌ Falha ao remover canal '{channel_name}': {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro ao remover o canal.")


async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeMonitor(bot))
