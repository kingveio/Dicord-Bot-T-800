import os
import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, Dict

import discord
from discord.ext import commands
from discord import app_commands, ui

logger = logging.getLogger(__name__)

# Configuração do Bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(
        type=discord.ActivityType.watching, 
        name="Exterminador do Futuro 2"
    )
)

# Variáveis globais
START_TIME = datetime.now()
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))  # 5 minutos
CHECK_TASK = None

# Classe para o Modal de Adicionar Streamer
class AddStreamerDiscordModal(ui.Modal, title="Vincular Usuário Discord"):
    discord_id = ui.TextInput(
        label="ID do Discord", 
        placeholder="Digite o ID ou @mencione um usuário",
        min_length=3,
        max_length=32
    )

    def __init__(self, twitch_username: str):
        super().__init__()
        self.twitch_username = twitch_username

    async def on_submit(self, interaction: discord.Interaction):
        try:
            discord_input = str(self.discord_id).strip()
            discord_id = re.sub(r'\D', '', discord_input)
            
            if not discord_id.isdigit() or not (17 <= len(discord_id) <= 19):
                await interaction.response.send_message(
                    "❌ ID do Discord inválido! Deve ter entre 17 e 19 dígitos.",
                    ephemeral=True
                )
                return

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                await interaction.response.send_message(
                    "❌ Membro não encontrado no servidor!",
                    ephemeral=True
                )
                return

            data = await get_cached_data()
            guild_id = str(interaction.guild.id)
            
            if guild_id not in data["streamers"]:
                data["streamers"][guild_id] = {}
            
            if self.twitch_username in data["streamers"][guild_id]:
                await interaction.response.send_message(
                    f"⚠️ O streamer '{self.twitch_username}' já está vinculado!",
                    ephemeral=True
                )
                return

            data["streamers"][guild_id][self.twitch_username] = discord_id
            await set_cached_data(data, bot.drive_service, persist=True)

            await interaction.response.send_message(
                f"✅ {member.mention} vinculado ao Twitch: `{self.twitch_username}`",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Erro ao vincular Discord: {str(e)}")
            await interaction.response.send_message(
                "❌ Erro interno ao processar!",
                ephemeral=True
            )

# Classe para o Modal de Twitch
class AddStreamerTwitchModal(ui.Modal, title="Adicionar Streamer Twitch"):
    twitch_name = ui.TextInput(
        label="Nome do Canal na Twitch",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            twitch_username = str(self.twitch_name).lower().strip()
            
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message(
                    "❌ Nome inválido na Twitch! Use apenas letras, números e _.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(
                AddStreamerDiscordModal(twitch_username)
            )

        except Exception as e:
            logger.error(f"Erro no modal Twitch: {str(e)}")
            await interaction.response.send_message(
                "❌ Erro interno ao processar!",
                ephemeral=True
            )

# View com os botões interativos
class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Apenas administradores podem usar este painel!",
                ephemeral=True
            )
            return False
        return True

    @ui.button(
        label="Adicionar",
        style=discord.ButtonStyle.green,
        emoji="➕",
        custom_id="add_streamer"
    )
    async def add_streamer(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerTwitchModal())

    @ui.button(
        label="Remover", 
        style=discord.ButtonStyle.red,
        emoji="➖",
        custom_id="remove_streamer"
    )
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get("streamers", {}).get(str(interaction.guild.id), {})
        
        if not guild_streamers:
            await interaction.response.send_message(
                "❌ Nenhum streamer vinculado neste servidor!",
                ephemeral=True
            )
            return

        options = []
        for streamer, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            desc = f"Vinculado a: {member.display_name if member else 'Não encontrado'}"
            options.append(discord.SelectOption(
                label=streamer,
                description=desc,
                value=streamer
            ))

        select = ui.Select(
            placeholder="Selecione um streamer para remover...",
            options=options,
            custom_id="select_remove_streamer"
        )

        async def callback(inner_interaction: discord.Interaction):
            try:
                selected = select.values[0]
                data = await get_cached_data()
                guild_id = str(inner_interaction.guild.id)
                
                if selected in data.get("streamers", {}).get(guild_id, {}):
                    del data["streamers"][guild_id][selected]
                    await set_cached_data(data, bot.drive_service, persist=True)
                    await inner_interaction.response.send_message(
                        f"✅ Streamer '{selected}' removido!",
                        ephemeral=True
                    )
                else:
                    await inner_interaction.response.send_message(
                        "❌ Streamer não encontrado!",
                        ephemeral=True
                    )
            except Exception as e:
                logger.error(f"Erro ao remover: {str(e)}")
                await inner_interaction.response.send_message(
                    "❌ Erro ao remover streamer!",
                    ephemeral=True
                )

        select.callback = callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(
        label="Listar",
        style=discord.ButtonStyle.blurple,
        emoji="📜",
        custom_id="list_streamers"
    )
    async def list_streamers(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get("streamers", {}).get(str(interaction.guild.id), {})
        
        if not guild_streamers:
            await interaction.response.send_message(
                "📭 Nenhum streamer vinculado neste servidor!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎮 Streamers Vinculados",
            color=0x9147FF
        )
        
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(
                name=f"🔹 {twitch_user}",
                value=f"Discord: {member.mention if member else '🚨 Não encontrado'}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# Comandos de Slash
@bot.tree.command(name="streamers", description="Gerenciar streamers vinculados")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    """Comando principal para gerenciamento de streamers"""
    try:
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "⚠️ Eu preciso da permissão **Gerenciar Cargos** para funcionar!",
                ephemeral=True
            )
            return

        view = StreamersView()
        await interaction.response.send_message(
            "**🎮 Painel de Streamers** - Escolha uma opção:",
            view=view,
            ephemeral=True
        )
        logger.info(f"Painel aberto por {interaction.user.name}")
    except Exception as e:
        logger.error(f"Erro no /streamers: {str(e)}")
        await interaction.response.send_message(
            "❌ Erro ao abrir o painel!",
            ephemeral=True
        )

@bot.tree.command(name="status", description="Ver status do bot")
async def status_command(interaction: discord.Interaction):
    uptime = datetime.now() - START_TIME
    data = await get_cached_data()
    
    total_streamers = sum(
        len(g) for g in data.get("streamers", {}).values()
    )
    
    embed = discord.Embed(
        title="🤖 Status do Bot",
        color=0x00FF00
    )
    embed.add_field(
        name="⏱ Uptime",
        value=str(uptime).split('.')[0],
        inline=False
    )
    embed.add_field(
        name="📊 Streamers",
        value=f"{total_streamers} em {len(data.get('streamers', {}))} servidores",
        inline=False
    )
    embed.add_field(
        name="🔄 Última verificação",
        value=datetime.now().strftime("%d/%m %H:%M:%S"),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="sync", description="Sincronizar comandos")
@commands.is_owner()
async def sync_command(interaction: discord.Interaction):
    try:
        await bot.tree.sync()
        logger.info("Comandos sincronizados")
        await interaction.response.send_message(
            "✅ Comandos sincronizados!",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"Erro ao sincronizar: {str(e)}")
        await interaction.response.send_message(
            f"❌ Erro ao sincronizar: {str(e)}",
            ephemeral=True
        )

# Sistema de Cargos
async def get_or_create_live_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Obtém ou cria o cargo 'Ao Vivo' com verificação robusta"""
    existing_role = discord.utils.find(
        lambda r: r.name.lower() == "ao vivo",
        guild.roles
    )
    
    if existing_role:
        logger.debug(f"Cargo existente: {existing_role.id}")
        return existing_role

    try:
        if not guild.me.guild_permissions.manage_roles:
            logger.error(f"Sem permissão em {guild.name}")
            return None

        new_role = await guild.create_role(
            name="Ao Vivo",
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True,
            reason="Cargo para streamers ao vivo"
        )
        
        logger.info(f"Criado cargo em {guild.name}")
        return new_role
    except Exception as e:
        logger.error(f"Erro ao criar cargo: {str(e)}")
        return None

# Verificação de Lives
async def check_streams_task():
    await bot.wait_until_ready()
    logger.info("✅ Iniciando verificador de lives")
    
    while not bot.is_closed():
        try:
            data = await get_cached_data()
            all_streamers = {
                s.lower() 
                for g in data.get("streamers", {}).values() 
                for s in g.keys()
            }
            
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
                    continue
                    
                for twitch_user, discord_id in streamers.items():
                    member = guild.get_member(int(discord_id))
                    if not member:
                        continue
                        
                    is_live = twitch_user.lower() in live_streamers
                    has_role = live_role in member.roles
                    
                    if is_live and not has_role:
                        await member.add_roles(live_role)
                        logger.info(f"➕ {twitch_user} entrou em live")
                    elif not is_live and has_role:
                        await member.remove_roles(live_role)
                        logger.info(f"➖ {twitch_user} saiu da live")
                        
        except Exception as e:
            logger.error(f"Erro na verificação: {str(e)}")
            
        await asyncio.sleep(CHECK_INTERVAL)

# Eventos
@bot.event
async def on_ready():
    logger.info(f"✅ Bot online como {bot.user}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar: {str(e)}")
    
    global CHECK_TASK
    if CHECK_TASK is None or CHECK_TASK.done():
        CHECK_TASK = bot.loop.create_task(check_streams_task())

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    logger.error(f"Erro no comando: {str(error)}")
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Você precisa ser administrador!",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ Ocorreu um erro interno!",
            ephemeral=True
        )

# Inicialização
def setup(bot):
    bot.add_view(StreamersView())
