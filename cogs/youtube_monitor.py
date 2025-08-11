import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from typing import Dict, Any

logger = logging.getLogger("T-800")

class YouTubeMonitor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_role_name = bot.live_role_name
        self.youtube_monitor_task.start()
        logger.info("✅ Módulo de monitoramento do YouTube inicializado.")

    def cog_unload(self):
        """Para a tarefa de loop quando o cog é descarregado."""
        self.youtube_monitor_task.stop()
        logger.info("❌ Módulo de monitoramento do YouTube descarregado.")

    @tasks.loop(minutes=5) # Ajuste a frequência conforme necessário
    async def youtube_monitor_task(self):
        """Verifica periodicamente os canais do YouTube monitorados."""
        if not self.bot.system_ready:
            return

        logger.info("🔍 Analisando alvos do YouTube...")
        try:
            data = await self.bot.get_data()
            youtube_monitored_users = data["monitored_users"].get("youtube", {})
            
            if not youtube_monitored_users:
                return

            channels = list(youtube_monitored_users.keys())
            
            # Chama a sua nova API do YouTube
            live_status = await self.bot.youtube_api.get_channel_live_status(channels)

            for channel_name, is_live in live_status.items():
                user_info = youtube_monitored_users.get(channel_name)
                if not user_info: continue

                guild = self.bot.get_guild(user_info.get("guild_id"))
                if not guild: continue
                
                member = guild.get_member(user_info.get("added_by"))
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

    # ========== COMANDOS DE ADMINISTRAÇÃO PARA YOUTUBE ========== #
    @app_commands.command(name="adicionar_yt", description="Adiciona um canal do YouTube para monitoramento")
    @app_commands.describe(
        nome="Nome de usuário do canal do YouTube",
        usuario="O usuário do Discord a ser vinculado"
    )
    async def adicionar_youtube_channel(self, interaction: discord.Interaction, nome: str, usuario: discord.Member):
        """Adiciona um canal do YouTube à lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await self.bot.get_data()
            
            youtube_monitored_users = data["monitored_users"].get("youtube", {})

            if nome.lower() in youtube_monitored_users:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
                )
            
            youtube_monitored_users[nome.lower()] = {
                "added_by": usuario.id,
                "added_at": datetime.now().isoformat(),
                "guild_id": interaction.guild.id
            }
            data["monitored_users"]["youtube"] = youtube_monitored_users
            await self.bot.save_data(self.bot.drive_service)
            await interaction.edit_original_response(
                content=f"✅ **{nome}** (YouTube) adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao adicionar alvo do YouTube: {e}. Alerta: Falha na operação."
            )

    @app_commands.command(name="remover_yt", description="Remove um canal do YouTube do monitoramento")
    @app_commands.describe(
        nome="Nome de usuário do canal do YouTube"
    )
    async def remover_youtube_channel(self, interaction: discord.Interaction, nome: str):
        """Remove um canal do YouTube da lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await self.bot.get_data()
            
            youtube_monitored_users = data["monitored_users"].get("youtube", {})

            if nome.lower() not in youtube_monitored_users:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} não é um alvo! Alerta: Falha na operação."
                )

            del youtube_monitored_users[nome.lower()]
            data["monitored_users"]["youtube"] = youtube_monitored_users
            await self.bot.save_data(self.bot.drive_service)

            await interaction.edit_original_response(
                content=f"✅ **{nome}** (YouTube) removido do sistema. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao remover alvo do YouTube: {e}. Alerta: Falha na operação."
            )

async def setup(bot: commands.Bot):
    """Função de inicialização do cog."""
    await bot.add_cog(YouTubeMonitor(bot))
