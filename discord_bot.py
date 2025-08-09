import os
import re
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuração do bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class StreamBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Streamers da Twitch"
            )
        )
        self.start_time = datetime.now()
        self.streamers_data = {}  # {guild_id: {twitch_username: discord_id}}
        self.live_role_name = "Ao Vivo"
        self.check_interval = 60  # 1 minuto

bot = StreamBot()

# --------------------------------------------------------------------------
# Menu de Streamers (UI)
# --------------------------------------------------------------------------

class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    twitch_username = ui.TextInput(
        label="Nome na Twitch",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )
    
    discord_user = ui.TextInput(
        label="Usuário do Discord",
        placeholder="Mencione ou digite o ID",
        min_length=3,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # Processa o nome da Twitch
            twitch_name = str(self.twitch_username).lower().strip()
            if not re.match(r'^[a-z0-9_]{3,25}$', twitch_name):
                return await interaction.followup.send("❌ Nome da Twitch inválido!", ephemeral=True)

            # Processa o usuário do Discord
            discord_id = re.sub(r'\D', '', str(self.discord_user))
            if not discord_id.isdigit() or len(discord_id) < 17:
                return await interaction.followup.send("❌ ID do Discord inválido!", ephemeral=True)

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                return await interaction.followup.send("❌ Membro não encontrado no servidor!", ephemeral=True)

            # Adiciona ao banco de dados
            guild_id = str(interaction.guild.id)
            if guild_id not in bot.streamers_data:
                bot.streamers_data[guild_id] = {}

            if twitch_name in bot.streamers_data[guild_id]:
                return await interaction.followup.send("⚠️ Este streamer já está registrado!", ephemeral=True)

            bot.streamers_data[guild_id][twitch_name] = discord_id
            await interaction.followup.send(
                f"✅ {member.mention} vinculado ao streamer Twitch: `{twitch_name}`",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Erro ao adicionar streamer: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao processar sua solicitação.", ephemeral=True)

@bot.tree.command(name="streamers", description="Gerenciar streamers")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    """Menu principal de gerenciamento de streamers"""
    try:
        embed = discord.Embed(
            title="🎮 Gerenciamento de Streamers",
            description="Use os botões abaixo para gerenciar os streamers",
            color=0x9147FF
        )
        
        view = ui.View()
        
        # Botão para adicionar streamer
        add_button = ui.Button(
            style=discord.ButtonStyle.green,
            label="Adicionar Streamer",
            emoji="➕"
        )
        
        async def add_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(AddStreamerModal())
            
        add_button.callback = add_callback
        view.add_item(add_button)
        
        # Botão para listar streamers
        list_button = ui.Button(
            style=discord.ButtonStyle.blurple,
            label="Listar Streamers",
            emoji="📋"
        )
        
        async def list_callback(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            guild_id = str(interaction.guild.id)
            
            if guild_id not in bot.streamers_data or not bot.streamers_data[guild_id]:
                return await interaction.followup.send("ℹ️ Nenhum streamer registrado neste servidor.", ephemeral=True)
            
            embed = discord.Embed(title="📋 Streamers Registrados", color=0x9147FF)
            
            for twitch_name, discord_id in bot.streamers_data[guild_id].items():
                member = interaction.guild.get_member(int(discord_id))
                embed.add_field(
                    name=f"🔹 {twitch_name}",
                    value=f"Discord: {member.mention if member else '❌ Usuário não encontrado'}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        list_button.callback = list_callback
        view.add_item(list_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Erro no comando streamers: {e}")
        await interaction.followup.send("❌ Ocorreu um erro ao abrir o menu.", ephemeral=True)

# --------------------------------------------------------------------------
# Sistema de Cargos
# --------------------------------------------------------------------------

async def get_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Obtém o cargo 'Ao Vivo' se existir"""
    return discord.utils.get(guild.roles, name=bot.live_role_name)

async def ensure_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Garante que o cargo 'Ao Vivo' existe"""
    # Verifica se já existe
    role = await get_live_role(guild)
    if role:
        return role
    
    # Tenta criar se não existir
    try:
        if not guild.me.guild_permissions.manage_roles:
            logger.warning(f"Sem permissões para criar cargo em {guild.name}")
            return None
            
        role = await guild.create_role(
            name=bot.live_role_name,
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True,
            reason="Cargo para streamers ao vivo"
        )
        
        # Tenta posicionar o cargo abaixo do cargo do bot
        try:
            await role.edit(position=guild.me.top_role.position - 1)
        except:
            pass
            
        return role
        
    except Exception as e:
        logger.error(f"Erro ao criar cargo em {guild.name}: {e}")
        return None

# --------------------------------------------------------------------------
# Verificação de Lives (Simulada)
# --------------------------------------------------------------------------

@tasks.loop(minutes=1)
async def check_live_streamers():
    """Verifica quais streamers estão ao vivo a cada 1 minuto"""
    logger.info("🔍 Verificando streamers ao vivo...")
    
    # Simulação - na implementação real, substitua por chamada à API da Twitch
    live_streamers = set()  # Este set conteria os nomes dos streamers ao vivo
    
    for guild_id, streamers in bot.streamers_data.items():
        guild = bot.get_guild(int(guild_id))
        if not guild:
            continue
            
        live_role = await get_live_role(guild)
        if not live_role:
            continue
            
        for twitch_name, discord_id in streamers.items():
            try:
                member = guild.get_member(int(discord_id))
                if not member:
                    continue
                    
                # Simulação: 20% de chance de estar "ao vivo" para teste
                is_live = twitch_name in live_streamers or datetime.now().second % 5 == 0
                has_role = live_role in member.roles
                
                if is_live and not has_role:
                    await member.add_roles(live_role)
                    logger.info(f"➕ Cargo dado para {twitch_name} em {guild.name}")
                elif not is_live and has_role:
                    await member.remove_roles(live_role)
                    logger.info(f"➖ Cargo removido de {twitch_name} em {guild.name}")
                    
            except Exception as e:
                logger.error(f"Erro ao atualizar cargo para {twitch_name}: {e}")

# --------------------------------------------------------------------------
# Eventos do Bot
# --------------------------------------------------------------------------

@bot.event
async def on_ready():
    """Executado quando o bot está pronto"""
    logger.info(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    logger.info(f"📊 Servidores: {len(bot.guilds)}")
    
    # Sincroniza comandos slash
    try:
        synced = await bot.tree.sync()
        logger.info(f"🔄 {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar comandos: {e}")
    
    # Inicia a verificação de lives
    if not check_live_streamers.is_running():
        check_live_streamers.start()

@bot.event
async def on_guild_join(guild):
    """Executado quando o bot entra em um servidor"""
    logger.info(f"➕ Entrou no servidor: {guild.name} (ID: {guild.id})")
    await ensure_live_role(guild)

# --------------------------------------------------------------------------
# Comandos Adicionais
# --------------------------------------------------------------------------

@bot.tree.command(name="status", description="Verifica o status do bot")
async def status(interaction: discord.Interaction):
    """Mostra informações do bot"""
    try:
        await interaction.response.defer(ephemeral=True)
        
        uptime = datetime.now() - bot.start_time
        guild_count = len(bot.guilds)
        streamer_count = sum(len(g) for g in bot.streamers_data.values())
        
        embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
        embed.add_field(name="⏱ Tempo ativo", value=str(uptime).split('.')[0], inline=False)
        embed.add_field(name="📊 Servidores", value=guild_count, inline=True)
        embed.add_field(name="🎮 Streamers", value=streamer_count, inline=True)
        embed.add_field(name="📶 Latência", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Erro no comando status: {e}")
        await interaction.followup.send("❌ Erro ao verificar status.", ephemeral=True)

# --------------------------------------------------------------------------
# Inicialização
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        bot.run(os.getenv("DISCORD_TOKEN"))
    except Exception as e:
        logger.error(f"Falha ao iniciar bot: {e}")
