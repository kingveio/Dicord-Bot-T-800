import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from data_manager import get_data, save_data

# Configuração do logger para este cog
logger = logging.getLogger("T-800")

class Monitoramento(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_role_name = "AO VIVO"
        self.monitor_twitch_streams.start()
        logger.info("✅ Módulo de monitoramento do Twitch inicializado.")

    def cog_unload(self):
        self.monitor_twitch_streams.stop()
        logger.info("❌ Módulo de monitoramento do Twitch descarregado.")

    @tasks.loop(minutes=5)
    async def monitor_twitch_streams(self):
        """Verifica periodicamente os canais da Twitch monitorados e atualiza o estado unificado."""
        if not self.bot.system_ready:
            return
            
        logger.info("🔍 Análise de alvos Twitch iniciada...")
        try:
            data = await get_data()
            if not data:
                logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
                return

            if "twitch" in data["monitored_users"] and data["monitored_users"]["twitch"]:
                streamers = list(data["monitored_users"]["twitch"].keys())
                logger.debug(f"Verificando os seguintes streamers: {streamers}")
                
                live_status = await self.bot.twitch_api.check_live_channels(streamers)

                for streamer_name, is_live in live_status.items():
                    user_info = data["monitored_users"]["twitch"].get(streamer_name.lower())
                    if not user_info:
                        continue

                    member_id = user_info.get("added_by")
                    guild_id = user_info.get("guild_id")
                    
                    if member_id and guild_id:
                        if member_id not in self.bot.live_users:
                            self.bot.live_users[member_id] = {"twitch": False, "youtube": False, "guild_id": guild_id}
                        
                        self.bot.live_users[member_id]["twitch"] = is_live
                        logger.debug(f"Status de live do Twitch para {member_id} atualizado para {is_live}.")

        except Exception as e:
            logger.error(f"❌ Falha no monitoramento do Twitch: {e}. Alerta: Falha na operação.", exc_info=True)

    # ========== COMANDOS DE BARRA ========== #

    @app_commands.command(name="adicionar_twitch", description="Adiciona um streamer da Twitch para monitoramento.")
    @app_commands.describe(
        nome="Nome de usuário do streamer na Twitch (ex: alanzoka)",
        discord_id="ID do usuário do Discord a ser marcado"
    )
    async def adicionar_twitch(self, interaction: discord.Interaction, nome: str, discord_id: str):
        """Comando de barra para adicionar um streamer da Twitch à lista de monitoramento."""
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Comando '/adicionar_twitch' acionado por {interaction.user.name} ({interaction.user.id}).")

        if not self.bot.twitch_api:
            await interaction.followup.send("⚠️ O serviço da Twitch não está disponível. Tente novamente mais tarde.")
            return

        streamer_name = nome.lower().strip()
        
        try:
            data = await get_data()
            if not data:
                await interaction.followup.send("⚠️ Não foi possível carregar os dados. Alerta: Falha na operação.")
                return

            if streamer_name in data["monitored_users"]["twitch"]:
                await interaction.followup.send(f"❌ O streamer **{streamer_name}** já está sendo monitorado.")
                return

            data["monitored_users"]["twitch"][streamer_name] = {
                "guild_id": interaction.guild_id,
                "added_by": discord_id,
                "timestamp": datetime.now().isoformat()
            }
            await save_data(data)
            
            await interaction.followup.send(f"✅ O streamer **{streamer_name}** foi adicionado à lista de monitoramento, vinculado ao usuário Discord com ID **{discord_id}**.")
            logger.info(f"Streamer '{streamer_name}' adicionado com sucesso.")

        except Exception as e:
            logger.error(f"❌ Falha ao adicionar streamer '{streamer_name}': {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro ao adicionar o streamer.")

    @app_commands.command(name="remover_twitch", description="Remove um streamer do monitoramento.")
    @app_commands.describe(nome="Nome de usuário do streamer na Twitch a ser removido (ex: alanzoka)")
    async def remover_twitch(self, interaction: discord.Interaction, nome: str):
        """Comando de barra para remover um streamer da lista de monitoramento."""
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Comando '/remover_twitch' acionado por {interaction.user.name} ({interaction.user.id}).")

        streamer_name = nome.lower().strip()

        try:
            data = await get_data()
            if not data:
                await interaction.followup.send("⚠️ Não foi possível carregar os dados. Alerta: Falha na operação.")
                return

            if streamer_name not in data["monitored_users"]["twitch"]:
                await interaction.followup.send(f"❌ O streamer **{streamer_name}** não está na lista de monitoramento.")
                return

            del data["monitored_users"]["twitch"][streamer_name]
            await save_data(data)

            await interaction.followup.send(f"✅ O streamer **{streamer_name}** foi removido da lista de monitoramento.")
            logger.info(f"Streamer '{streamer_name}' removido com sucesso.")

        except Exception as e:
            logger.error(f"❌ Falha ao remover streamer '{streamer_name}': {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ocorreu um erro ao remover o streamer.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Monitoramento(bot))
