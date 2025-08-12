import discord
from discord.ext import commands, tasks
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
        """Verifica periodicamente os canais do YouTube monitorados e atualiza o estado unificado."""
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
            logger.error(f"❌ Falha no monitoramento do YouTube: {e}. Alerta: Falha na operação.")

    # ========== COMANDOS DE ADMINISTRAÇÃO ========== #
    # O resto do código para os comandos /adicionar_yt e /remover_yt permanece o mesmo
    # e não precisa ser alterado.

async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeMonitor(bot))
