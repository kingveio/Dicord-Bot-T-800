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
            logger.error(f"❌ Falha no monitoramento do Twitch: {e}. Alerta: Falha na operação.")

    # ========== COMANDOS DE ADMINISTRAÇÃO ========== #
    # O resto do código para os comandos /adicionar_twitch e /remover_twitch permanece o mesmo
    # e não precisa ser alterado.

async def setup(bot: commands.Bot):
    await bot.add_cog(Monitoramento(bot))
