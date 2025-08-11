import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime

# Configuração do logger para este cog
logger = logging.getLogger("T-800")

class TwitchMonitor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_role_name = "AO VIVO"
        self.monitor_twitch_streams.start()
        logger.info("✅ Módulo de monitoramento da Twitch inicializado.")

    def cog_unload(self):
        self.monitor_twitch_streams.stop()
        logger.info("❌ Módulo de monitoramento da Twitch descarregado.")

    @tasks.loop(minutes=5)
    async def monitor_twitch_streams(self):
        """Verifica periodicamente os canais da Twitch monitorados."""
        if not self.bot.system_ready or not self.bot.twitch_api:
            return

        logger.info("🔍 Análise de alvos Twitch iniciada...")
        try:
            data = await self.bot.get_data()
            if not data:
                logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
                return

            monitored_twitch = data["monitored_users"].get("twitch", {})
            if monitored_twitch:
                streamers = list(monitored_twitch.keys())
                live_status = await self.bot.twitch_api.check_live_channels(streamers)

                for streamer_name, is_live in live_status.items():
                    user_info = monitored_twitch.get(streamer_name.lower())
                    if not user_info: continue

                    guild = self.bot.get_guild(user_info.get("guild_id"))
                    member = guild.get_member(user_info.get("added_by")) if guild else None
                    if not member: continue

                    live_role = discord.utils.get(guild.roles, name=self.live_role_name)
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
            logger.error(f"❌ Falha no monitoramento da Twitch: {e}. Alerta: Falha na operação.")

    # ========== COMANDOS DE ADMINISTRAÇÃO ========== #
    @app_commands.command(name="adicionar_twitch", description="Adiciona um streamer da Twitch para monitoramento")
    @app_commands.describe(
        nome="Nome do streamer da Twitch",
        usuario="O usuário do Discord a ser vinculado"
    )
    async def adicionar_twitch(self, interaction: discord.Interaction, nome: str, usuario: discord.Member):
        """Adiciona um streamer da Twitch à lista de monitoramento."""
        await interaction.response.defer(ephemeral=True)
        try:
            data = await self.bot.get_data()
            response_content = ""

            if "twitch" not in data["monitored_users"]:
                data["monitored_users"]["twitch"] = {}
            
            if nome.lower() in data["monitored_users"]["twitch"]:
                response_content = f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
            else:
                data["monitored_users"]["twitch"][nome.lower()] = {
                    "added_by": usuario.id,
                    "added_at": datetime.now().isoformat(),
                    "guild_id": interaction.guild.id
                }
                await self.bot.save_data()
                response_content = f"✅ **{nome}** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."

            await interaction.edit_original_response(content=response_content)

        except Exception as e:
            logger.error(f"❌ Erro ao adicionar alvo da Twitch: {e}. Alerta: Falha na operação.")
            await interaction.edit_original_response(content=f"❌ Erro ao adicionar alvo da Twitch: {e}. Alerta: Falha na operação.")

    @app_commands.command(name="remover_twitch", description="Remove um streamer da Twitch do monitoramento")
    @app_commands.describe(
        nome="Nome do streamer da Twitch"
    )
    async def remover_twitch(self, interaction: discord.Interaction, nome: str):
        """Remove um streamer da Twitch da lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await self.bot.get_data()

            if "twitch" in data["monitored_users"] and nome.lower() not in data["monitored_users"]["twitch"]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} não é um alvo! Alerta: Falha na operação."
                )

            del data["monitored_users"]["twitch"][nome.lower()]
            await self.bot.save_data()

            await interaction.edit_original_response(
                content=f"✅ **{nome}** removido do sistema. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao remover alvo da Twitch: {e}. Alerta: Falha na operação."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(TwitchMonitor(bot))
