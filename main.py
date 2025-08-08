import discord
from discord.ext import commands
from discord import app_commands, ui
import aiohttp
import asyncio
import json
import os
import sys
import time
import logging
import threading
import re
from datetime import datetime, timedelta
from flask import Flask, jsonify
import requests

# ========== CONFIGURAÇÃO INICIAL ==========
print("╔════════════════════════════════════════════╗")
print("║       BOT DE NOTIFICAÇÕES DA TWITCH        ║")
print("╚════════════════════════════════════════════╝")

# Configuração de logging avançada
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Verifica variáveis de ambiente necessárias
REQUIRED_ENV = ["DISCORD_TOKEN", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"]
missing = [var for var in REQUIRED_ENV if var not in os.environ]

if missing:
    logger.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

# Configurações globais
TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
DATA_FILE = "streamers.json"
CHECK_INTERVAL = 55
START_TIME = datetime.now()

# ========== SERVIDOR FLASK PARA HEALTH CHECKS ==========
app = Flask(__name__)
last_ping_time = time.time()
bot_ready = False

@app.route('/')
def home():
    return "🤖 Bot Twitch Online! Use /ping para status."

@app.route('/ping')
def ping():
    global last_ping_time
    last_ping_time = time.time()
    return jsonify({
        "status": "online",
        "bot_ready": bot_ready,
        "uptime": str(datetime.now() - START_TIME),
        "last_check": getattr(bot, '_last_check', 'N/A')
    }), 200

def run_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True, use_reloader=False)

# ========== CONFIGURAÇÃO DO BOT DISCORD ==========
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Streamers da Twitch"
    )
)

# ========== GERENCIAMENTO DE DADOS ==========
def load_data():
    try:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w", encoding='utf-8') as f:
                json.dump({}, f)
            return {}

        with open(DATA_FILE, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error("Erro ao carregar dados: %s", e)
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Erro ao salvar dados: %s", e)

# ========== INTEGRAÇÃO COM TWITCH API ==========
class TwitchAPI:
    def __init__(self):
        self.token = None
        self.token_expiry = None
        bot._twitch_token_valid = False

    async def get_token(self, retries=3):
        for attempt in range(retries):
            try:
                if self.token and self.token_expiry and datetime.now() < self.token_expiry:
                    return self.token

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://id.twitch.tv/oauth2/token",
                        params={
                            "client_id": TWITCH_CLIENT_ID,
                            "client_secret": TWITCH_SECRET,
                            "grant_type": "client_credentials"
                        },
                        timeout=10
                    ) as response:
                        data = await response.json()
                        self.token = data["access_token"]
                        self.token_expiry = datetime.now() + timedelta(seconds=3300)
                        bot._twitch_token_valid = True
                        return self.token
            except Exception as e:
                logger.error(f"Erro ao obter token (tentativa {attempt+1}): {e}")
                await asyncio.sleep(5 * (attempt + 1))
        return None

    async def validate_streamer(self, username):
        token = await self.get_token()
        if not token:
            return False

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.twitch.tv/helix/users?login={username}",
                    headers=headers,
                    timeout=10
                ) as response:
                    data = await response.json()
                    return len(data.get("data", [])) > 0
        except Exception:
            return False

    async def check_live_streams(self, usernames):
        token = await self.get_token()
        if not token:
            return set()

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }

        live_streamers = set()
        batch_size = 100
        usernames_list = list(usernames)
        
        for i in range(0, len(usernames_list), batch_size):
            batch = usernames_list[i:i + batch_size]
            url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(batch)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as response:
                    data = await response.json()
                    bot._last_check = datetime.now().isoformat()
                    live_streamers.update({s["user_login"].lower() for s in data.get("data", [])})
            
            await asyncio.sleep(1)
            
        return live_streamers

twitch_api = TwitchAPI()

# ========== INTERFACE DO DISCORD ==========
class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    twitch_name = ui.TextInput(
        label="Nome na Twitch",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )
    
    discord_id = ui.TextInput(
        label="ID do Membro do Discord",
        placeholder="Digite o ID (18 dígitos) ou mencione (@usuário)",
        min_length=3,
        max_length=32
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Apenas administradores podem adicionar streamers!",
                    ephemeral=True
                )
                return

            twitch_username = self.twitch_name.value.lower().strip()
            discord_input = self.discord_id.value.strip()
            
            # Validação do nome Twitch
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message(
                    "❌ Nome inválido! Use apenas letras, números e underscores.",
                    ephemeral=True
                )
                return
                
            if not await twitch_api.validate_streamer(twitch_username):
                await interaction.response.send_message(
                    f"❌ Streamer '{twitch_username}' não encontrado na Twitch!",
                    ephemeral=True
                )
                return

            # EXTRAÇÃO CORRIGIDA DO ID DISCORD
            discord_id = None
            if discord_input.startswith('<@') and discord_input.endswith('>'):  # Menção
                discord_id = re.sub(r'\D', '', discord_input)  # Extrai apenas números
            elif discord_input.isdigit():  # ID direto
                discord_id = discord_input
            else:
                await interaction.response.send_message(
                    "❌ Formato inválido! Use ID (18 dígitos) ou @usuário",
                    ephemeral=True
                )
                return
                
            if len(discord_id) != 18:
                await interaction.response.send_message(
                    "❌ ID deve ter exatamente 18 dígitos!",
                    ephemeral=True
                )
                return

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                await interaction.response.send_message(
                    "❌ Usuário não encontrado! Verifique:\n"
                    "1. Se o usuário está no servidor\n"
                    "2. Se o ID está correto\n"
                    "3. Permissões do bot",
                    ephemeral=True
                )
                return

            data = load_data()
            guild_id = str(interaction.guild.id)
            
            if guild_id not in data:
                data[guild_id] = {}
                
            if twitch_username in data[guild_id]:
                existing_id = data[guild_id][twitch_username]
                await interaction.response.send_message(
                    f"⚠️ Já vinculado a <@{existing_id}>",
                    ephemeral=True
                )
                return
                
            data[guild_id][twitch_username] = discord_id
            save_data(data)
            
            await interaction.response.send_message(
                f"✅ {member.mention} vinculado a `{twitch_username}`",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Erro ao adicionar: {str(e)}", exc_info=True)
            await interaction.response.send_message(
                "❌ Erro interno ao processar!",
                ephemeral=True
            )

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

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_streamer(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        data = load_data()
        guild_streamers = data.get(str(interaction.guild.id), {})

        if not guild_streamers:
            await interaction.response.send_message("❌ Nenhum streamer registrado!", ephemeral=True)
            return

        select = ui.Select(placeholder="Selecione um streamer para remover...")
        
        for streamer, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            select.add_option(
                label=f"{streamer}",
                description=f"Vinculado a: {member.display_name if member else 'Não encontrado'}",
                value=streamer
            )

        async def callback(interaction: discord.Interaction):
            data = load_data()
            guild_id = str(interaction.guild.id)

            if guild_id in data and select.values[0] in data[guild_id]:
                removed_user = select.values[0]
                del data[guild_id][removed_user]
                save_data(data)
                
                await interaction.response.send_message(
                    f"✅ `{removed_user}` removido com sucesso!",
                    ephemeral=True
                )

        select.callback = callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_streamers(self, interaction: discord.Interaction, button: ui.Button):
        data = load_data()
        guild_streamers = data.get(str(interaction.guild.id), {})

        if not guild_streamers:
            await interaction.response.send_message("📭 Nenhum streamer registrado!", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Streamers Vinculados", color=0x9147FF)
        
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(
                name=f"🔹 {twitch_user}",
                value=f"Discord: {member.mention if member else '🚨 Usuário não encontrado'}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== VERIFICADOR DE STREAMS ==========
async def check_streams():
    while True:
        try:
            data = load_data()
            if not data:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            all_streamers = set()
            for guild_streamers in data.values():
                all_streamers.update(guild_streamers.keys())

            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            live_streamers = await twitch_api.check_live_streams(all_streamers)

            for guild_id, streamers in data.items():
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue

                live_role = discord.utils.get(guild.roles, name="Ao Vivo")
                if not live_role:
                    try:
                        live_role = await guild.create_role(
                            name="Ao Vivo",
                            color=discord.Color.purple(),
                            hoist=True,
                            mentionable=True
                        )
                    except Exception as e:
                        logger.error(f"Erro ao criar cargo: {e}")
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
                            
                            channel = guild.system_channel or discord.utils.get(guild.text_channels, name="geral")
                            if channel and channel.permissions_for(guild.me).send_messages:
                                await channel.send(
                                    f"🎥 {member.mention} está ao vivo na Twitch!",
                                    allowed_mentions=discord.AllowedMentions(users=True))
                            
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                            
                    except Exception as e:
                        logger.error(f"Erro ao atualizar cargo: {e}")

        except Exception as e:
            logger.error(f"Erro no verificador: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# ========== COMANDOS SLASH ==========
@bot.tree.command(name="streamers", description="Gerenciar notificações de streamers (Apenas ADMs)")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🎮 Painel de Streamers** - Escolha uma opção:",
        view=StreamersView(),
        ephemeral=True
    )

@bot.tree.command(name="ajuda", description="Mostra informações sobre o bot")
async def ajuda(interaction: discord.Interaction):
    embed = discord.Embed(title="Ajuda do Bot de Twitch", color=0x9147FF)
    embed.add_field(
        name="/streamers", 
        value="Gerencia os streamers monitorados (apenas administradores)", 
        inline=False
    )
    embed.add_field(
        name="Como funciona",
        value="O bot verifica a cada minuto quem está ao vivo e atribui o cargo 'Ao Vivo'",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Você precisa ser **Administrador** para usar este comando!",
            ephemeral=True
        )
    else:
        logger.error(f"Erro no comando: {error}")
        await interaction.response.send_message(
            "❌ Ocorreu um erro ao executar este comando!",
            ephemeral=True
        )

# ========== EVENTOS DO BOT ==========
@bot.event
async def on_ready():
    global bot_ready
    bot_ready = True
    
    logger.info(f"✅ Bot conectado como {bot.user}")
    logger.info(f"🌐 Servidores: {len(bot.guilds)}")

    bot.add_view(StreamersView())
    bot.loop.create_task(check_streams())
    threading.Thread(target=background_pinger, daemon=True).start()

    try:
        synced = await bot.tree.sync()
        logger.info(f"🔗 {len(synced)} comandos sincronizados")
    except Exception as e:
        logger.error(f"⚠️ Erro ao sincronizar: {e}")

def background_pinger():
    while True:
        try:
            with app.test_client() as client:
                client.get('/ping')
            if 'RENDER_EXTERNAL_URL' in os.environ:
                requests.get(f"{os.environ['RENDER_EXTERNAL_URL']}/ping", timeout=10)
        except Exception as e:
            logger.error(f"Erro no pinger: {e}")
        time.sleep(45)

def run_bot():
    restart_count = 0
    max_restarts = 10
    restart_delay = 30

    while restart_count < max_restarts:
        try:
            logger.info(f"🚀 Iniciando bot (Tentativa {restart_count + 1}/{max_restarts})")
            flask_thread = threading.Thread(target=run_flask, daemon=True)
            flask_thread.start()
            bot.run(TOKEN)
            restart_count = 0
        except discord.LoginError as e:
            logger.critical("❌ ERRO FATAL: Token do Discord inválido!")
            break
        except Exception as e:
            logger.error(f"⚠️ Erro na execução: {type(e).__name__} - {str(e)}")
            restart_count += 1
            if restart_count >= max_restarts:
                logger.critical("🔴 Máximo de reinícios atingido! Encerrando...")
                break
            delay = min(restart_delay * (2 ** (restart_count - 1)), 300)
            logger.info(f"⏳ Reiniciando em {delay} segundos...")
            time.sleep(delay)

if __name__ == '__main__':
    run_bot()
