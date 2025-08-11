import os
import aiohttp
import discord
import logging
from discord.ext import commands, tasks
from discord import app_commands
from typing import Dict, Any
from datetime import datetime, timezone

from .data_manager import get_data, save_data

logger = logging.getLogger('discord')


class T800Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drive_service = None
        self.twitch_api = None
        self.live_role = os.environ.get("DISCORD_LIVE_ROLE") or "AO VIVO"
        self.system_ready = False

    async def on_ready(self):
        try:
            logger.info(f"🦾 T-800 ativado! Conectado como {self.user} (ID: {self.user.id})")
            await self.tree.sync()
            logger.info("Comandos sincronizados. Status: Missão concluída.")
            monitor_streams.start()
            self.system_ready = True
        except Exception as e:
            logger.critical(f"❌ Falha crítica ao inicializar bot: {e}. Alerta: Falha na operação.")

    async def on_member_update(self, before, after):
        # Lógica para garantir que o cargo 'AO VIVO' não seja removido manualmente.
        if before.roles != after.roles:
            live_role = discord.utils.get(after.guild.roles, name=self.live_role)
            if live_role in before.roles and live_role not in after.roles:
                data = await get_data()
                user_twitch_name = next(
                    (name for name, info in data["monitored_users"]["twitch"].items() if info["added_by"] == after.id),
                    None
                )
                if user_twitch_name:
                    is_live = await self.twitch_api.check_live_channels([user_twitch_name])
                    if is_live.get(user_twitch_name.lower()):
                        await after.add_roles(live_role, reason="Remoção manual do cargo 'AO VIVO' detectada. Revertendo.")
                        logger.warning(
                            f"⚠️ Ação manual no cargo de {after.name} revertida. Status: Alerta corrigido."
                        )

bot = T800Bot(command_prefix='!', intents=discord.Intents.default())


@bot.tree.command(name="adicionar", description="Adiciona um streamer para monitoramento")
@app_commands.describe(
    plataforma="Plataforma (twitch)",
    nome="Nome do canal da Twitch",
    usuario="O usuário do Discord a ser vinculado"
)
@app_commands.choices(plataforma=[
    app_commands.Choice(name="Twitch", value="twitch")
])
async def adicionar_streamer(interaction: discord.Interaction, plataforma: str, nome: str, usuario: discord.Member):
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
            "added_at": datetime.now(timezone.utc).isoformat(),
            "guild_id": interaction.guild.id
        }
        await save_data(bot.drive_service)

        await interaction.edit_original_response(
            content=f"✅ **{nome}** adicionado ao sistema e vinculado a {usuario.mention}. Missão concluída."
        )
    except Exception as e:
        await interaction.edit_original_response(
            content=f"❌ Erro ao adicionar alvo: {e}. Alerta: Falha na operação."
        )


@bot.tree.command(name="remover", description="Remove um streamer do monitoramento")
@app_commands.describe(
    plataforma="Plataforma (twitch)",
    nome="Nome do canal da Twitch"
)
@app_commands.choices(plataforma=[
    app_commands.Choice(name="Twitch", value="twitch")
])
async def remover_streamer(interaction: discord.Interaction, plataforma: str, nome: str):
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
        await save_data(bot.drive_service)

        await interaction.edit_original_response(
            content=f"✅ **{nome}** removido do sistema. Missão concluída."
        )
    except Exception as e:
        await interaction.edit_original_response(
            content=f"❌ Erro ao remover alvo: {e}. Alerta: Falha na operação."
        )


@bot.tree.command(name="listar", description="Mostra a lista de alvos monitorados")
async def listar_streamers(interaction: discord.Interaction):
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


@tasks.loop(minutes=3)
async def monitor_streams():
    """Verifica periodicamente os streamers monitorados."""
    if not bot.system_ready:
        return

    logger.info("🔍 Análise de alvos iniciada...")
    try:
        data = await get_data()
        if not data:
            logger.error("⚠️ Dados não carregados corretamente! Alerta: Falha na operação.")
            return

        # Monitorar Twitch
        if data["monitored_users"]["twitch"]:
            streamers = list(data["monitored_users"]["twitch"].keys())
            live_status = await bot.twitch_api.check_live_channels(streamers)

            for streamer_name, is_live in live_status.items():
                user_info = data["monitored_users"]["twitch"].get(streamer_name.lower())
                if not user_info: continue

                guild = bot.get_guild(user_info.get("guild_id"))
                member = guild.get_member(user_info.get("added_by")) if guild else None
                if not member: continue

                live_role = discord.utils.get(guild.roles, name=bot.live_role)
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
