import os
import sys
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict

import discord
from discord.ext import commands
from discord import app_commands, ui

# Configuração básica de logging
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
        self.check_interval = int(os.environ.get("CHECK_INTERVAL", 300))
        self.check_task = None
        self.cached_data = {"streamers": {}}

bot = StreamBot()

# --------------------------------------------------------------------------
# Componentes UI
# --------------------------------------------------------------------------

class AddStreamerDiscordModal(ui.Modal, title="Vincular Usuário Discord"):
    discord_id = ui.TextInput(
        label="ID do Discord",
        placeholder="Digite o ID ou @mencione",
        min_length=3,
        max_length=32
    )

    def __init__(self, twitch_username: str):
        super().__init__()
        self.twitch_username = twitch_username

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            discord_id = re.sub(r'\D', '', str(self.discord_id.value))
            if not (17 <= len(discord_id) <= 19):
                return await interaction.followup.send("❌ ID inválido!", ephemeral=True)

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                return await interaction.followup.send("❌ Membro não encontrado!", ephemeral=True)

            guild_id = str(interaction.guild.id)
            
            if guild_id not in bot.cached_data["streamers"]:
                bot.cached_data["streamers"][guild_id] = {}

            if self.twitch_username in bot.cached_data["streamers"][guild_id]:
                return await interaction.followup.send("⚠️ Streamer já vinculado!", ephemeral=True)

            bot.cached_data["streamers"][guild_id][self.twitch_username] = discord_id
            await interaction.followup.send(
                f"✅ {member.mention} vinculado a `{self.twitch_username}`",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Erro no modal: {str(e)}")
            await interaction.followup.send("❌ Erro interno!", ephemeral=True)

class AddStreamerTwitchModal(ui.Modal, title="Adicionar Streamer Twitch"):
    twitch_name = ui.TextInput(
        label="Nome na Twitch",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            username = str(self.twitch_name.value).lower().strip()
            if not re.match(r'^[a-z0-9_]{3,25}$', username):
                return await interaction.followup.send("❌ Nome inválido! Use apenas letras, números e underscores.", ephemeral=True)
            
            await interaction.followup.send_modal(AddStreamerDiscordModal(username))
        except Exception as e:
            logger.error(f"Erro no modal Twitch: {str(e)}")
            await interaction.followup.send("❌ Erro interno!", ephemeral=True)

class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerTwitchModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild_streamers = bot.cached_data.get("streamers", {}).get(str(interaction.guild.id), {})
        
        if not guild_streamers:
            return await interaction.followup.send("❌ Nenhum streamer vinculado!", ephemeral=True)

        options = [
            discord.SelectOption(label=name, description=f"Vinculado a: {discord_id}")
            for name, discord_id in guild_streamers.items()
        ]

        select = ui.Select(placeholder="Selecione para remover...", options=options)

        async def callback(inner_interaction: discord.Interaction):
            await inner_interaction.response.defer(ephemeral=True)
            selected = select.values[0]
            del bot.cached_data["streamers"][str(inner_interaction.guild.id)][selected]
            await inner_interaction.followup.send(f"✅ {selected} removido!", ephemeral=True)

        select.callback = callback
        view = ui.View().add_item(select)
        await interaction.followup.send("Selecione para remover:", view=view, ephemeral=True)

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        guild_streamers = bot.cached_data.get("streamers", {}).get(str(interaction.guild.id), {})

        embed = discord.Embed(title="📋 Streamers Vinculados", color=0x9147FF)
        for name, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(
                name=f"🔹 {name}",
                value=f"Discord: {member.mention if member else '❌ Não encontrado'}",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

# --------------------------------------------------------------------------
# Comandos
# --------------------------------------------------------------------------

@bot.tree.command(name="streamers", description="Gerenciar streamers vinculados")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    """Painel de gerenciamento de streamers"""
    try:
        await interaction.response.send_message(
            "**🎮 Painel de Streamers** - Escolha uma opção:",
            view=StreamersView(),
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Erro no /streamers: {str(e)}")
        await interaction.followup.send("❌ Erro ao abrir painel!", ephemeral=True)

@bot.tree.command(name="status", description="Verificar status do bot")
async def status_command(interaction: discord.Interaction):
    """Mostra o status atual do bot"""
    try:
        await interaction.response.defer(ephemeral=True)
        
        uptime = datetime.now() - bot.start_time
        
        embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
        embed.add_field(name="⏱ Uptime", value=str(uptime).split('.')[0], inline=False)
        embed.add_field(
            name="📊 Streamers", 
            value=f"{sum(len(g) for g in bot.cached_data.get('streamers', {}).values())} em {len(bot.cached_data.get('streamers', {}))} servidores", 
            inline=False
        )
        embed.add_field(name="📶 Latência", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Erro no /status: {str(e)}")
        await interaction.followup.send("❌ Erro ao verificar status!", ephemeral=True)

@bot.command()
@commands.is_owner()
async def debug(ctx):
    """🔧 Mostra informações técnicas detalhadas (apenas dono)"""
    try:
        uptime = datetime.now() - bot.start_time
        
        embed = discord.Embed(
            title="🛠️ DEBUG - Informações Técnicas",
            color=0xFFA500,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="🕒 Uptime", value=str(uptime).split('.')[0], inline=False)
        embed.add_field(name="📶 Latência", value=f"{round(bot.latency * 1000, 2)}ms", inline=True)
        embed.add_field(name="📊 Servidores", value=len(bot.guilds), inline=True)
        embed.add_field(
            name="🎮 Streamers", 
            value=f"{sum(len(g) for g in bot.cached_data.get('streamers', {}).values())} em {len(bot.cached_data.get('streamers', {}))} servidores", 
            inline=False
        )
        embed.add_field(name="🐍 Python", value=sys.version.split()[0], inline=True)
        embed.add_field(name="💾 Memória", value=f"{sys.getsizeof(bot.cached_data) / 1024:.2f} KB", inline=True)
        
        await ctx.send(embed=embed)
        logger.info(f"Debug executado por {ctx.author.name}")
    except Exception as e:
        logger.error(f"Erro no debug: {str(e)}")
        await ctx.send("❌ Falha ao gerar relatório de debug!")

# --------------------------------------------------------------------------
# Sistema de Cargos
# --------------------------------------------------------------------------

async def get_or_create_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Obtém ou cria o cargo 'Ao Vivo'"""
    try:
        existing = discord.utils.find(lambda r: r.name.lower() == "ao vivo", guild.roles)
        if existing:
            return existing

        if not guild.me.guild_permissions.manage_roles:
            logger.error(f"Sem permissões em {guild.name}")
            return None

        role = await guild.create_role(
            name="Ao Vivo",
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True,
            reason="Criado automaticamente para streamers ao vivo"
        )
        
        try:
            await role.edit(position=guild.me.top_role.position - 1)
        except:
            pass
            
        return role
    except Exception as e:
        logger.error(f"Erro ao criar cargo: {str(e)}")
        return None

# --------------------------------------------------------------------------
# Verificação de Lives
# --------------------------------------------------------------------------

async def check_streams_task():
    """Verifica periodicamente os streamers ao vivo"""
    await bot.wait_until_ready()
    logger.info("🔍 Iniciando verificador de lives...")
    
    while not bot.is_closed():
        try:
            all_streamers = {
                s.lower() 
                for g in bot.cached_data.get("streamers", {}).values() 
                for s in g.keys()
            }
            
            if not all_streamers:
                await asyncio.sleep(bot.check_interval)
                continue
                
            # Simulação da API da Twitch - implemente sua lógica real aqui
            live_streamers = set()  # Substituir por chamada real à API
            
            for guild_id, streamers in bot.cached_data.get("streamers", {}).items():
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue
                    
                live_role = await get_or_create_live_role(guild)
                if not live_role:
                    continue
                    
                for twitch_user, discord_id in streamers.items():
                    try:
                        member = guild.get_member(int(discord_id))
                        if not member:
                            continue
                            
                        is_live = twitch_user.lower() in live_streamers
                        has_role = live_role in member.roles
                        
                        if is_live and not has_role:
                            await member.add_roles(live_role)
                            logger.info(f"➕ Cargo dado para {twitch_user}")
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                            logger.info(f"➖ Cargo removido de {twitch_user}")
                    except Exception as e:
                        logger.error(f"Erro em {twitch_user}: {str(e)}")
                        
            await asyncio.sleep(bot.check_interval)
        except Exception as e:
            logger.error(f"Erro na verificação: {str(e)}")
            await asyncio.sleep(60)

# --------------------------------------------------------------------------
# Eventos
# --------------------------------------------------------------------------

@bot.event
async def on_ready():
    """Executado quando o bot está pronto"""
    logger.info(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    logger.info(f"📊 Conectado em {len(bot.guilds)} servidores")
    
    try:
        bot.add_view(StreamersView())
        synced = await bot.tree.sync()
        logger.info(f"🔄 {len(synced)} comandos slash sincronizados")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar comandos: {str(e)}")
    
    if bot.check_task is None or bot.check_task.done():
        bot.check_task = bot.loop.create_task(check_streams_task())

@bot.event
async def on_guild_join(guild):
    """Executado quando o bot entra em um novo servidor"""
    logger.info(f"➕ Entrou no servidor: {guild.name} (ID: {guild.id})")
    await get_or_create_live_role(guild)

@bot.event
async def on_command_error(ctx, error):
    """Tratamento de erros para comandos prefixados"""
    if isinstance(error, commands.NotOwner):
        await ctx.send("❌ Apenas o dono pode usar este comando!")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("⚠️ Você não tem permissões suficientes!")
    else:
        logger.error(f"Erro no comando {ctx.command}: {str(error)}")

# --------------------------------------------------------------------------
# Inicialização
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        bot.run(os.getenv("DISCORD_TOKEN"))
    except Exception as e:
        logger.error(f"Erro ao iniciar bot: {str(e)}")
