import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime
from typing import Optional, Dict
import os
import asyncio

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

bot = T800Bot()

@bot.event
async def setup_hook():
    """Configura o owner_id corretamente durante a inicialização"""
    # Tenta obter o ID do dono das variáveis de ambiente
    owner_id = os.getenv("BOT_OWNER_ID", "659611103399116800")
    bot.owner_id = int(owner_id)
    
    # Sincroniza comandos globais
    await bot.tree.sync()
    logging.info("Comandos globais sincronizados durante o setup")

@bot.event
async def on_ready():
    """Evento quando o bot está pronto"""
    if not bot.synced:
        try:
            # Sincroniza comandos por servidor
            for guild in bot.guilds:
                await bot.tree.sync(guild=guild)
            bot.synced = True
            logging.info("Comandos sincronizados por servidor com sucesso!")
        except Exception as e:
            logging.error(f"Erro ao sincronizar comandos: {e}")
    
    bot.system_ready = True
    logging.info(f"T-800 ONLINE | ID: {bot.user.id} | Conectado em {len(bot.guilds)} servidores")
    
    # Configurar cargo em todos os servidores
    for guild in bot.guilds:
        await ensure_live_role(guild)

    # Iniciar monitoramento
    if not monitor_streams.is_running():
        monitor_streams.start()

async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Garante que o cargo AO VIVO existe no servidor"""
    try:
        if role := discord.utils.get(guild.roles, name=bot.live_role):
            return role
        
        if not guild.me.guild_permissions.manage_roles:
            logging.warning(f"Sem permissões para criar cargo em {guild.name}")
            return None

        role = await guild.create_role(
            name=bot.live_role,
            color=discord.Color.red(),
            hoist=True,
            mentionable=True,
            reason="Monitoramento de streams"
        )
        
        # Move o cargo para o topo da lista (se possível)
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
    """Tarefa periódica para monitorar streams"""
    if not bot.system_ready:
        return
    
    logging.info("INICIANDO VARREDURA DE ALVOS...")
    # Implementação do monitoramento aqui

# COMANDOS DE APLICAÇÃO (SLASH COMMANDS)

@bot.tree.command(name="status", description="Relatório do sistema T-800")
async def system_status(interaction: discord.Interaction):
    """Mostra o status do bot"""
    uptime = datetime.now() - bot.start_time
    await interaction.response.send_message(
        f"**STATUS DO T-800**\n"
        f"⏱ Operando por: {str(uptime).split('.')[0]}\n"
        f"🔍 Monitorando: {len(bot.guilds)} servidores\n"
        f"👥 Total de usuários: {sum(g.member_count for g in bot.guilds)}\n"
        f"✅ Sistemas operacionais\n"
        f"💻 Objetivo primário: Proteger os streamers humanos",
        ephemeral=True
    )

@bot.tree.command(name="sobre", description="Informações sobre o T-800")
async def about(interaction: discord.Interaction):
    """Mostra informações sobre o bot"""
    await interaction.response.send_message(
        "**SISTEMA T-800 v2.0**\n"
        "Modelo 101 - Cyberdyne Systems\n"
        "Ano de fabricação: 2024\n"
        "CPU: Processador neuronal de aprendizado\n"
        "Missão: Monitorar e proteger streamers humanos\n"
        "Frase característica: 'I'll be back'",
        ephemeral=True
    )

@bot.tree.command(name="terminar", description="Comando de emergência (apenas para administradores)")
@app_commands.default_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction):
    """Desliga o bot (apenas para admins)"""
    await interaction.response.send_message(
        "⚠️ ATIVAÇÃO DO PROTOCOLO DE AUTODESTRUIÇÃO\n"
        "Sistema será desativado em 5 segundos...",
        ephemeral=True
    )
    await asyncio.sleep(5)
    await interaction.followup.send("T-800 desativado. Até a próxima, humano.")
    await bot.close()

# COMANDOS DE TEXTO (PREFIXO !)

@bot.command()
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Sincroniza comandos (apenas para dono do bot)"""
    try:
        # Sincroniza globalmente
        await bot.tree.sync()
        
        # Sincroniza por servidor
        if ctx.guild:
            await bot.tree.sync(guild=ctx.guild)
        
        await ctx.send("✅ Comandos sincronizados com sucesso!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar: {e}")

@bot.command()
@commands.is_owner()
async def servers(ctx: commands.Context):
    """Lista todos os servidores (apenas para dono)"""
    embed = discord.Embed(
        title="Servidores Conectados",
        description=f"Total: {len(bot.guilds)}",
        color=discord.Color.blue()
    )
    
    for guild in bot.guilds:
        embed.add_field(
            name=guild.name,
            value=f"ID: {guild.id}\nMembros: {guild.member_count}",
            inline=False
        )
    
    await ctx.send(embed=embed)
