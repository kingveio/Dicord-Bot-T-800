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
import shutil
from datetime import datetime, timedelta
from flask import Flask, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

# ========== CONFIGURAÇÃO INICIAL ==========
print("╔════════════════════════════════════════════╗")
print("║       BOT DE NOTIFICAÇÕES DA TWITCH        ║")
print("╚════════════════════════════════════════════╝")

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Verifica variáveis de ambiente
REQUIRED_ENV = [
    "DISCORD_TOKEN", 
    "TWITCH_CLIENT_ID", 
    "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID",
    "DRIVE_PRIVATE_KEY_ID",
    "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID"
]
missing = [var for var in REQUIRED_ENV if var not in os.environ]

if missing:
    logger.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

# Configurações globais
TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
DATA_FILE = "streamers.json"
CHECK_INTERVAL = 55
START_TIME = datetime.now()

# ========== SERVIÇO WEB PARA HEALTH CHECKS ==========
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "uptime": str(datetime.now() - START_TIME),
        "bot": "running"
    }), 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ========== SERVIÇO DO GOOGLE DRIVE ==========
class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        self.service_account_info = {
            "type": "service_account",
            "project_id": "bot-t-800",
            "private_key_id": os.environ["DRIVE_PRIVATE_KEY_ID"],
            "private_key": os.environ["DRIVE_PRIVATE_KEY"].replace('\\n', '\n'),
            "client_email": "discord-bot-t-800@bot-t-800.iam.gserviceaccount.com",
            "client_id": os.environ["DRIVE_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/discord-bot-t-800%40bot-t-800.iam.gserviceaccount.com"
        }
        self.service = self._authenticate()

    def _authenticate(self):
        creds = service_account.Credentials.from_service_account_info(
            self.service_account_info,
            scopes=self.SCOPES
        )
        return build('drive', 'v3', credentials=creds)

    def upload_file(self, file_path, file_name):
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, mimetype='application/json')
        
        try:
            existing = self._find_file(file_name)
            if existing:
                file = self.service.files().update(
                    fileId=existing['id'],
                    media_body=media
                ).execute()
            else:
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            logger.info(f"📤 Upload realizado: {file_name} (ID: {file.get('id')})")
            return True
        except Exception as e:
            logger.error(f"❌ Falha no upload: {str(e)}")
            return False

    def download_file(self, file_name, save_path):
        try:
            file = self._find_file(file_name)
            if not file:
                return False
                
            request = self.service.files().get_media(fileId=file['id'])
            fh = io.FileIO(save_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            logger.info(f"📥 Download realizado: {file_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Falha no download: {str(e)}")
            return False

    def _find_file(self, file_name):
        query = f"name='{file_name}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        return results.get('files', [None])[0]

drive_service = GoogleDriveService()

# ========== GERENCIAMENTO DE DADOS ==========
def validate_data_structure(data):
    """Valida a estrutura dos dados"""
    if not isinstance(data, dict):
        return False
    for guild_id, streamers in data.items():
        if not isinstance(guild_id, str) or not isinstance(streamers, dict):
            return False
        for twitch_user, discord_id in streamers.items():
            if not isinstance(twitch_user, str) or not isinstance(discord_id, str):
                return False
    return True

def backup_data():
    """Cria backup dos dados"""
    try:
        if os.path.exists(DATA_FILE):
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"{DATA_FILE}.{timestamp}")
            shutil.copy(DATA_FILE, backup_file)
            logger.info(f"✅ Backup criado: {backup_file}")
    except Exception as e:
        logger.error(f"❌ Erro no backup: {str(e)}")

def load_data():
    """Carrega dados com tratamento robusto de erros"""
    try:
        # Tenta baixar do Drive primeiro
        if not drive_service.download_file(DATA_FILE, DATA_FILE):
            logger.warning("⚠️ Arquivo não encontrado no Drive, usando local")
        
        # Verifica se o arquivo existe localmente
        if not os.path.exists(DATA_FILE):
            logger.info("ℹ️ Criando novo arquivo de dados")
            return {}
            
        # Lê e valida o conteúdo
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                logger.warning("⚠️ Arquivo vazio, retornando dados padrão")
                return {}
                
            data = json.loads(content)
            if not validate_data_structure(data):
                raise ValueError("Estrutura de dados inválida")
            return data
            
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON inválido: {str(e)}")
        backup_data()  # Faz backup do arquivo corrompido
        return {}
    except Exception as e:
        logger.error(f"❌ Erro ao carregar dados: {str(e)}")
        return {}

def save_data(data):
    """Salva dados com validação completa"""
    try:
        if not validate_data_structure(data):
            raise ValueError("Dados não passaram na validação de estrutura")
            
        backup_data()  # Faz backup antes de salvar
        
        # Salva localmente
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        # Envia para o Drive
        if not drive_service.upload_file(DATA_FILE, DATA_FILE):
            logger.error("❌ Falha ao enviar para o Google Drive")
            
    except Exception as e:
        logger.error(f"❌ Erro crítico ao salvar dados: {str(e)}")
        raise

# ========== TWITCH API ==========
class TwitchAPI:
    def __init__(self):
        self.token = None
        self.token_expiry = None
        self.user_cache = {}
        self.cache_expiry = timedelta(hours=1)

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
                        }
                    ) as response:
                        data = await response.json()
                        self.token = data["access_token"]
                        self.token_expiry = datetime.now() + timedelta(seconds=3300)
                        return self.token
            except Exception as e:
                logger.error(f"Erro ao obter token (tentativa {attempt+1}): {e}")
                await asyncio.sleep(2)
        return None

    async def validate_streamer(self, username):
        username = username.lower()
        if username in self.user_cache:
            cached_time, is_valid = self.user_cache[username]
            if datetime.now() - cached_time < self.cache_expiry:
                return is_valid
        
        is_valid = await self._validate_streamer_api(username)
        self.user_cache[username] = (datetime.now(), is_valid)
        return is_valid

    async def _validate_streamer_api(self, username):
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
                    headers=headers
                ) as response:
                    data = await response.json()
                    return len(data.get("data", [])) > 0
        except Exception as e:
            logger.error(f"Erro ao validar streamer: {e}")
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
        
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i + batch_size]
            url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(batch)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        data = await response.json()
                        live_streamers.update({s["user_login"].lower() for s in data.get("data", [])})
            except Exception as e:
                logger.error(f"Erro ao verificar lives: {e}")

            await asyncio.sleep(1)
            
        return live_streamers

twitch_api = TwitchAPI()

# ========== DISCORD BOT ==========
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

# ========== STREAMERS MODAL ==========
class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    twitch_name = ui.TextInput(
        label="Nome na Twitch",
        placeholder="ex: alanzoka",
        min_length=3,
        max_length=25
    )
    
    discord_id = ui.TextInput(
        label="ID/Menção do Discord",
        placeholder="Digite o ID ou @usuário",
        min_length=3,
        max_length=32
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Apenas administradores podem usar este comando!",
                    ephemeral=True
                )
                return

            twitch_username = self.twitch_name.value.lower().strip()
            discord_input = self.discord_id.value.strip()

            # Validação Twitch
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message(
                    "❌ Nome inválido na Twitch! Use apenas letras, números e _",
                    ephemeral=True
                )
                return

            if not await twitch_api.validate_streamer(twitch_username):
                await interaction.response.send_message(
                    f"❌ Streamer '{twitch_username}' não encontrado na Twitch!",
                    ephemeral=True
                )
                return

            # Processa ID Discord
            discord_id = re.sub(r'\D', '', discord_input)  # Extrai apenas números
            if len(discord_id) != 18:
                await interaction.response.send_message(
                    "❌ ID Discord inválido! Deve ter 18 dígitos.",
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

            # Salva os dados
            data = load_data()
            guild_id = str(interaction.guild.id)

            if guild_id not in data:
                data[guild_id] = {}

            if twitch_username in data[guild_id]:
                await interaction.response.send_message(
                    f"⚠️ O streamer '{twitch_username}' já está vinculado!",
                    ephemeral=True
                )
                return

            data[guild_id][twitch_username] = discord_id
            save_data(data)

            await interaction.response.send_message(
                f"✅ {member.mention} vinculado ao Twitch: `{twitch_username}`",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Erro ao adicionar streamer: {e}")
            await interaction.response.send_message(
                "❌ Erro interno ao processar!",
                ephemeral=True
            )

# ========== STREAMERS VIEW ==========
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
            await interaction.response.send_message(
                "❌ Nenhum streamer vinculado neste servidor!",
                ephemeral=True
            )
            return

        select = ui.Select(placeholder="Selecione um streamer para remover...")
        
        for streamer, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            select.add_option(
                label=streamer,
                description=f"Vinculado a: {member.display_name if member else 'Não encontrado'}",
                value=streamer
            )

        async def callback(interaction: discord.Interaction):
            data = load_data()
            guild_id = str(interaction.guild.id)

            if select.values[0] in data.get(guild_id, {}):
                del data[guild_id][select.values[0]]
                save_data(data)
                await interaction.response.send_message(
                    f"✅ Streamer '{select.values[0]}' removido!",
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
            await interaction.response.send_message(
                "📭 Nenhum streamer vinculado neste servidor!",
                ephemeral=True
            )
            return

        embed = discord.Embed(title="🎮 Streamers Vinculados", color=0x9147FF)
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(
                name=f"🔹 {twitch_user}",
                value=f"Discord: {member.mention if member else '🚨 Não encontrado'}",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== COMANDOS ==========
@bot.tree.command(name="streamers", description="Gerenciar streamers vinculados")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**🎮 Painel de Streamers** - Escolha uma opção:",
        view=StreamersView(),
        ephemeral=True
    )

@bot.tree.command(name="status", description="Verifica o status do bot")
async def status_command(interaction: discord.Interaction):
    uptime = datetime.now() - START_TIME
    data = load_data()
    total_streamers = sum(len(g) for g in data.values())
    
    embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
    embed.add_field(name="⏱ Uptime", value=str(uptime).split('.')[0], inline=False)
    embed.add_field(name="📊 Streamers monitorados", value=f"{total_streamers} em {len(data)} servidores", inline=False)
    embed.add_field(name="🔄 Última verificação", value=datetime.now().strftime("%H:%M:%S"), inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== VERIFICAÇÃO DE LIVES ==========
async def check_streams():
    while True:
        try:
            data = load_data()
            all_streamers = {
                twitch_user 
                for guild_data in data.values() 
                for twitch_user in guild_data.keys()
            }

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
                            if channel:
                                await channel.send(
                                    f"🎥 {member.mention} está ao vivo na Twitch como `{twitch_user}`!",
                                    allowed_mentions=discord.AllowedMentions(users=True)
                                )

                        elif not is_live and has_role:
                            await member.remove_roles(live_role)

                    except Exception as e:
                        logger.error(f"Erro ao atualizar cargo: {e}")

        except Exception as e:
            logger.error(f"Erro no verificador: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)

# ========== EVENTOS ==========
@bot.event
async def on_ready():
    logger.info(f"✅ Bot conectado como {bot.user.name}")
    
    # Verificação inicial do sistema de dados
    try:
        test_data = load_data()
        if not isinstance(test_data, dict):
            logger.error("❌ Dados inválidos detectados, resetando...")
            save_data({})
        logger.info("✅ Sistema de dados verificado")
    except Exception as e:
        logger.error(f"❌ Falha crítica na verificação de dados: {e}")
        save_data({})  # Força reset

    # Sincroniza comandos e inicia tasks
    try:
        await bot.tree.sync()
        bot.loop.create_task(check_streams())
        logger.info("✅ Comandos sincronizados e tasks iniciadas")
    except Exception as e:
        logger.error(f"❌ Falha ao iniciar tasks: {e}")

# ========== INICIALIZAÇÃO ==========
def run_bot():
    # Cria arquivo de dados inicial se não existir
    if not os.path.exists(DATA_FILE):
        save_data({})
    
    # Inicia o bot
    bot.run(TOKEN)

if __name__ == '__main__':
    # Inicia o servidor Flask em uma thread separada
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Inicia o bot Discord
    run_bot()
