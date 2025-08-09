import os
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict

import discord
from discord.ext import commands
from discord import app_commands, ui
from data_manager import get_cached_data, set_cached_data

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="Streamers da Twitch")
)

START_TIME = datetime.now()
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 55))
CHECK_TASK = None

async def get_or_create_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Obtém ou cria o cargo 'Ao Vivo' com verificação robusta"""
    # Verifica todos os cargos existentes (case insensitive)
    existing_role = discord.utils.find(lambda r: r.name.lower() == "ao vivo", guild.roles)
    
    if existing_role:
        logger.debug(f"Usando cargo existente: {existing_role.name} (ID: {existing_role.id})")
        return existing_role

    try:
        # Cria novo cargo se não existir
        new_role = await guild.create_role(
            name="Ao Vivo",
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True,
            reason="Criado automaticamente para streamers ao vivo"
        )
        
        # Tenta posicionar o cargo acima dos membros comuns
        try:
            member_role = guild.default_role
            await new_role.edit(position=member_role.position + 1)
        except Exception as edit_error:
            logger.warning(f"Não foi possível ajustar posição do cargo: {edit_error}")

        logger.info(f"Criado novo cargo 'Ao Vivo' em {guild.name}")
        return new_role

    except discord.Forbidden:
        logger.error(f"Sem permissões para criar cargo em {guild.name}")
        return None
    except discord.HTTPException as e:
        logger.error(f"Falha ao criar cargo: {str(e)}")
        return None

def sanitize_discord_id(input_str: str) -> str:
    digits = re.sub(r'\D', '', input_str)
    return digits if digits.isdigit() and (17 <= len(digits) <= 19) else ""

# ... (mantenha os modais AddStreamerDiscordModal e AddStreamerTwitchModal existentes)

class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este painel!", ephemeral=True)
            return False
        return True

    # ... (mantenha os botões existentes)

@bot.tree.command(name="fixroles", description="Corrige problemas com cargos de streamer")
@app_commands.checks.has_permissions(administrator=True)
async def fix_roles_command(interaction: discord.Interaction):
    """Comando para corrigir cargos duplicados ou problemas de permissão"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Remove cargos duplicados
        deleted = []
        for role in interaction.guild.roles:
            if role.name.lower() == "ao vivo":
                await role.delete(reason="Correção de cargos duplicados")
                deleted.append(role.name)
        
        # Cria novo cargo
        new_role = await get_or_create_live_role(interaction.guild)
        
        if new_role:
            msg = f"✅ Cargo resetado: {new_role.mention}"
            if deleted:
                msg += f"\n🗑 Cargos removidos: {', '.join(deleted)}"
        else:
            msg = "❌ Não foi possível criar o cargo. Verifique as permissões do bot."
        
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        logger.error(f"Erro no fixroles: {str(e)}")
        await interaction.followup.send("❌ Ocorreu um erro durante a correção.", ephemeral=True)

async def check_streams_task():
    await bot.wait_until_ready()
    logger.info("✅ Iniciando verificação de lives")
    
    while not bot.is_closed():
        try:
            data = await get_cached_data()
            if not data:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
                
            all_streamers = {s.lower() for g in data.get("streamers", {}).values() for s in g.keys()}
            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue
                
            live_streamers = await bot.twitch_api.check_live_streams(all_streamers)

            for guild_id, streamers in data.get("streamers", {}).items():
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue
                    
                live_role = await get_or_create_live_role(guild)
                if not live_role:
                    logger.error(f"Não foi possível obter cargo em {guild.name}")
                    continue
                    
                for twitch_user, discord_id in streamers.items():
                    try:
                        member = guild.get_member(int(discord_id))
                        if not member:
                            continue
                            
                        is_live = twitch_user.lower() in live_streamers
                        has_role = live_role in member.roles
                        
                        logger.debug(f"{twitch_user}: Live={is_live} | Cargo={has_role}")
                        
                        if is_live and not has_role:
                            await member.add_roles(live_role, reason="Streamer ao vivo")
                            logger.info(f"➕ Cargo adicionado para {twitch_user}")
                        elif not is_live and has_role:
                            await member.remove_roles(live_role, reason="Streamer offline")
                            logger.info(f"➖ Cargo removido de {twitch_user}")
                    except Exception as e:
                        logger.error(f"Erro ao atualizar {twitch_user}: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Erro na verificação principal: {str(e)}")
            
        await asyncio.sleep(CHECK_INTERVAL)

@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user}")
    try:
        await bot.tree.sync()
        logger.info("✅ Comandos sincronizados")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos: {str(e)}")
    
    global CHECK_TASK
    if CHECK_TASK is None or CHECK_TASK.done():
        CHECK_TASK = bot.loop.create_task(check_streams_task())

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⚠️ Eu preciso da permissão **Gerenciar Cargos** para funcionar corretamente!")
