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
        """Verifica periodicamente os canais da Twitch monitorados."""
        if not self.bot.system_ready:
            return
            
        logger.info("🔍 Análise de alvos Twitch iniciada...")
        try:
            data = await get_data()
            if not data:
                logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
                return

            # Monitorar Twitch
            if "twitch" in data["monitored_users"] and data["monitored_users"]["twitch"]:
                streamers = list(data["monitored_users"]["twitch"].keys())
                logger.debug(f"Verificando os seguintes streamers: {streamers}")
                
                live_status = await self.bot.twitch_api.check_live_channels(streamers)

                for streamer_name, is_live in live_status.items():
                    user_info = data["monitored_users"]["twitch"].get(streamer_name.lower())
                    if not user_info:
                        logger.warning(f"Informações de usuário não encontradas para {streamer_name}")
                        continue

                    guild = self.bot.get_guild(user_info.get("guild_id"))
                    if not guild:
                        logger.warning(f"Guilda com ID {user_info.get('guild_id')} não encontrada.")
                        continue
                    
                    member = guild.get_member(user_info.get("added_by"))
                    if not member:
                        logger.warning(f"Membro com ID {user_info.get('added_by')} não encontrado na guilda {guild.name}.")
                        continue

                    live_role = discord.utils.get(guild.roles, name=self.live_role_name)
                    if not live_role:
                        logger.warning(f"Cargo '{self.live_role_name}' não encontrado na guilda {guild.name}. Tentando criar...")
                        try:
                            # Tenta criar o cargo com a cor vermelha por padrão
                            live_role = await guild.create_role(
                                name=self.live_role_name,
                                color=discord.Color.red(),
                                reason="Cargo criado automaticamente para monitoramento de lives"
                            )
                            logger.info(f"✅ Cargo '{self.live_role_name}' criado com sucesso.")
                        except discord.Forbidden:
                            logger.error(f"❌ O bot não tem permissão para criar cargos na guilda {guild.name}. Alerta: Falha na operação.")
                            continue
                    
                    if is_live:
                        if live_role not in member.roles:
                            await member.add_roles(live_role, reason="Streamer está ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' adicionado para {member.name} (Twitch). Missão concluída.")
                        else:
                            logger.info(f"Streamer {member.name} já tem o cargo 'AO VIVO'.")
                    else:
                        if live_role in member.roles:
                            await member.remove_roles(live_role, reason="Streamer não está mais ao vivo")
                            logger.info(f"✅ Cargo 'AO VIVO' removido de {member.name} (Twitch). Missão concluída.")

        except Exception as e:
            logger.error(f"❌ Falha no monitoramento do Twitch: {e}. Alerta: Falha na operação.")

    # ========== COMANDOS DE ADMINISTRAÇÃO ========== #
    @app_commands.command(name="adicionar_twitch", description="Adiciona um streamer da Twitch para monitoramento")
    @app_commands.describe(
        nome="Nome de usuário da Twitch",
        usuario="O usuário do Discord a ser vinculado"
    )
    async def adicionar_twitch(self, interaction: discord.Interaction, nome: str, usuario: discord.Member):
        """Adiciona um streamer da Twitch à lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await get_data()

            if "twitch" not in data["monitored_users"]:
                data["monitored_users"]["twitch"] = {}

            if nome.lower() in data["monitored_users"]["twitch"]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} já é um alvo! Alerta: Falha na operação."
                )
            
            data["monitored_users"]["twitch"][nome.lower()] = {
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
                content=f"❌ Erro ao adicionar alvo do Twitch: {e}. Alerta: Falha na operação."
            )

    @app_commands.command(name="remover_twitch", description="Remove um streamer da Twitch do monitoramento")
    @app_commands.describe(
        nome="Nome de usuário da Twitch"
    )
    async def remover_twitch(self, interaction: discord.Interaction, nome: str):
        """Remove um streamer da Twitch da lista de monitoramento."""
        try:
            await interaction.response.defer(ephemeral=True)
            data = await get_data()

            if "twitch" in data["monitored_users"] and nome.lower() not in data["monitored_users"]["twitch"]:
                return await interaction.edit_original_response(
                    content=f"⚠️ {nome} não é um alvo! Alerta: Falha na operação."
                )

            del data["monitored_users"]["twitch"][nome.lower()]
            await save_data(self.bot.drive_service)

            await interaction.edit_original_response(
                content=f"✅ **{nome}** removido do sistema. Missão concluída."
            )
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Erro ao remover alvo do Twitch: {e}. Alerta: Falha na operação."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Monitoramento(bot))
