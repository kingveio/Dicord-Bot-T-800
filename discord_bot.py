import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Optional, Dict, List
import os
import asyncio
from data_manager import get_data, update_monitored_users

# Configuração T-800
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class T800Bot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="humanos streamando"
            )
        )
        self.start_time = datetime.now()
        self.live_role = "AO VIVO"
        self.system_ready = False
        self.synced = False
        self.monitored_users = {
            "twitch": {},
            "youtube": {}
        }

bot = T800Bot()

@bot.event
async def setup_hook():
    """Configuração inicial do T-800"""
    owner_id = os.getenv("BOT_OWNER_ID", "659611103399116800")
    bot.owner_id = int(owner_id)
    
    # Carrega usuários monitorados
    data = await get_data()
    bot.monitored_users = data.get("monitored_users", {
        "twitch": {},
        "youtube": {}
    })
    
    await bot.tree.sync()
    logging.info("Sistemas de armas carregados - Comandos sincronizados")

@bot.event
async def on_ready():
    """Ativação do sistema T-800"""
    if not bot.synced:
        try:
            for guild in bot.guilds:
                await bot.tree.sync(guild=guild)
            bot.synced = True
            logging.info("Sistemas de mira sincronizados por servidor")
        except Exception as e:
            logging.error(f"Falha na sincronização: {e}")
    
    bot.system_ready = True
    logging.info(f"T-800 ONLINE | ID: {bot.user.id} | Servidores: {len(bot.guilds)}")
    
    for guild in bot.guilds:
        await ensure_live_role(guild)

    if not monitor_streams.is_running():
        monitor_streams.start()

async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Garante o cargo AO VIVO está configurado"""
    try:
        if role := discord.utils.get(guild.roles, name=bot.live_role):
            return role
        
        if not guild.me.guild_permissions.manage_roles:
            return None

        role = await guild.create_role(
            name=bot.live_role,
            color=discord.Color.red(),
            hoist=True,
            mentionable=True,
            reason="Protocolo de monitoramento T-800"
        )
        
        try:
            await role.edit(position=len(guild.roles)-1)
        except:
            pass
            
        return role
    except Exception as e:
        logging.error(f"ERRO EM {guild.name}: {str(e)}")
        return None

@tasks.loop(minutes=5)
async def monitor_streams():
    """Rotina de monitoramento de alvos"""
    if not bot.system_ready:
        return
    
    logging.info("INICIANDO VARREDURA DE ALVOS...")
    
    try:
        # Monitorar Twitch
        if bot.monitored_users["twitch"]:
            targets = list(bot.monitored_users["twitch"].keys())
            live_streams = await bot.twitch_api.check_live_channels(targets)
            
            for streamer, is_live in live_streams.items():
                if is_live:
                    logging.info(f"ALVO DETECTADO: {streamer} está ao vivo")
                    # Implementar notificações aqui
                    
        # Monitorar YouTube (implementação similar)
        
    except Exception as e:
        logging.error(f"FALHA NO SISTEMA DE VARREDURA: {str(e)}")

# COMANDOS DE GERENCIAMENTO DE USUÁRIOS

@bot.tree.command(name="adicionar_twitch", description="Adiciona um streamer da Twitch para monitoramento")
@app_commands.describe(nome="Nome do streamer na Twitch")
@app_commands.default_permissions(manage_guild=True)
async def add_twitch(interaction: discord.Interaction, nome: str):
    """Adiciona um alvo Twitch ao sistema de monitoramento"""
    try:
        nome = nome.lower()
        if nome in bot.monitored_users["twitch"]:
            await interaction.response.send_message(
                f"⚠️ **{nome}** já está na lista de alvos do T-800!",
                ephemeral=True
            )
            return

        bot.monitored_users["twitch"][nome] = {
            "added_by": interaction.user.id,
            "added_at": datetime.now().isoformat(),
            "guild_id": interaction.guild.id
        }
        
        await update_monitored_users("twitch", bot.monitored_users["twitch"])
        
        await interaction.response.send_message(
            f"✅ **{nome}** adicionado ao sistema de monitoramento!\n"
            f"`O T-800 agora rastreará quando {nome} estiver online.`",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Falha no protocolo de adição: {e}",
            ephemeral=True
        )

@bot.tree.command(name="remover_twitch", description="Remove um streamer da Twitch do monitoramento")
@app_commands.describe(nome="Nome do streamer na Twitch")
@app_commands.default_permissions(manage_guild=True)
async def remove_twitch(interaction: discord.Interaction, nome: str):
    """Remove um alvo Twitch do sistema"""
    try:
        nome = nome.lower()
        if nome not in bot.monitored_users["twitch"]:
            await interaction.response.send_message(
                f"❌ **{nome}** não encontrado na lista de alvos!",
                ephemeral=True
            )
            return

        del bot.monitored_users["twitch"][nome]
        await update_monitored_users("twitch", bot.monitored_users["twitch"])
        
        await interaction.response.send_message(
            f"✅ **{nome}** removido do sistema de monitoramento!\n"
            f"`Alvo removido com sucesso.`",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Falha no protocolo de remoção: {e}",
            ephemeral=True
        )

@bot.tree.command(name="listar_twitch", description="Lista todos streamers da Twitch monitorados")
async def list_twitch(interaction: discord.Interaction):
    """Mostra a lista de alvos Twitch"""
    try:
        if not bot.monitored_users["twitch"]:
            await interaction.response.send_message(
                "ℹ️ Nenhum alvo Twitch está sendo monitorado atualmente.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📡 Alvos Twitch Monitorados",
            description="Lista de streamers sendo rastreados",
            color=0x9147ff
        )
        
        for i, (streamer, data) in enumerate(bot.monitored_users["twitch"].items(), 1):
            added_by = await bot.fetch_user(data["added_by"]) if data.get("added_by") else "Desconhecido"
            embed.add_field(
                name=f"{i}. {streamer}",
                value=f"Adicionado por: {added_by}\n"
                     f"Data: {data.get('added_at', 'N/A')}",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Falha ao acessar a lista de alvos: {e}",
            ephemeral=True
        )

# COMANDOS PARA YOUTUBE (estrutura similar)

# ... (implementar comandos similares para YouTube)

# COMANDOS DE STATUS E GERENCIAMENTO

@bot.tree.command(name="status", description="Relatório do sistema T-800")
async def system_status(interaction: discord.Interaction):
    """Mostra o status do sistema"""
    uptime = datetime.now() - bot.start_time
    total_users = sum(g.member_count for g in bot.guilds)
    
    embed = discord.Embed(
        title="⚙️ STATUS DO SISTEMA T-800",
        color=0x00ff00
    )
    embed.add_field(name="⏱ Tempo de atividade", value=str(uptime).split('.')[0], inline=False)
    embed.add_field(name="🔍 Servidores", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="👥 Usuários", value=str(total_users), inline=True)
    embed.add_field(name="📡 Alvos Twitch", value=str(len(bot.monitored_users["twitch"])), inline=True)
    embed.add_field(name="▶️ Alvos YouTube", value=str(len(bot.monitored_users["youtube"])), inline=True)
    embed.set_footer(text="Sistema operacional - Missão em andamento")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="terminar", description="Desativa o sistema T-800 (apenas admin)")
@app_commands.default_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction):
    """Protocolo de desativação"""
    await interaction.response.send_message(
        "⚠️ **ATIVAÇÃO DO PROTOCOLO DE AUTODESTRUIÇÃO**\n"
        "Sistema será desativado em 5 segundos...",
        ephemeral=True
    )
    await asyncio.sleep(5)
    await interaction.followup.send("✅ T-800 desativado com sucesso. Até a próxima, humano.")
    await bot.close()

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Sincroniza comandos (apenas dono)"""
    try:
        await bot.tree.sync()
        if ctx.guild:
            await bot.tree.sync(guild=ctx.guild)
        await ctx.send("✅ Sistemas de mira sincronizados com sucesso!")
    except Exception as e:
        await ctx.send(f"❌ Falha na sincronização: {e}")
