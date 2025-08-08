# bot_twitch_drive.py
import os
import sys
import json
import io
import shutil
import logging
import threading
import re
import asyncio
from datetime import datetime, timedelta

import aiohttp
import aiofiles
import discord
from discord.ext import commands
from discord import app_commands, ui
from flask import Flask, jsonify

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# ================= CONFIGURAÇÕES INICIAIS =================
os.environ.setdefault('DISABLE_VOICE', 'true')  # Desativa módulos de voz se existir

print("╔════════════════════════════════════════════╗")
print("║       BOT DE NOTIFICAÇÕES DA TWITCH        ║")
print("╚════════════════════════════════════════════╝")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Variáveis de ambiente obrigatórias
REQUIRED_ENV = [
    "DISCORD_TOKEN",
    "TWITCH_CLIENT_ID",
    "TWITCH_CLIENT_SECRET",
    "DRIVE_FOLDER_ID",
    "DRIVE_PRIVATE_KEY_ID",
    "DRIVE_PRIVATE_KEY",
    "DRIVE_CLIENT_ID"
]
missing = [v for v in REQUIRED_ENV if v not in os.environ]
if missing:
    logger.error("❌ Variáveis de ambiente faltando: %s", missing)
    sys.exit(1)

TOKEN = os.environ["DISCORD_TOKEN"]
TWITCH_CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
TWITCH_SECRET = os.environ["TWITCH_CLIENT_SECRET"]
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
DATA_FILE = "streamers.json"
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 55))
START_TIME = datetime.now()

# ================= FLASK (health check) =================
app = Flask(__name__)

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "uptime": str(datetime.now() - START_TIME),
        "bot": "running"
    }), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ================= GOOGLE DRIVE SERVICE (síncrono) =================
class GoogleDriveService:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/drive']
        # Monta o dict com credenciais baseado nas env vars
        self.service_account_info = {
            "type": "service_account",
            "project_id": os.environ.get("DRIVE_PROJECT_ID", "bot-t-800"),
            "private_key_id": os.environ["DRIVE_PRIVATE_KEY_ID"],
            "private_key": os.environ["DRIVE_PRIVATE_KEY"].replace('\\n', '\n'),
            "client_email": os.environ.get("DRIVE_CLIENT_EMAIL", "discord-bot-t-800@bot-t-800.iam.gserviceaccount.com"),
            "client_id": os.environ["DRIVE_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get("DRIVE_CLIENT_X509", "")
        }
        self.service = self._authenticate()

    def _authenticate(self):
        creds = service_account.Credentials.from_service_account_info(
            self.service_account_info,
            scopes=self.SCOPES
        )
        return build('drive', 'v3', credentials=creds)

    # MÉTODOS SÍNCRONOS — serão executados via asyncio.to_thread no código async
    def _find_file(self, file_name):
        query = f"name='{file_name}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        files = results.get('files', [])
        return files[0] if files else None

    def download_file(self, file_name, save_path):
        file = self._find_file(file_name)
        if not file:
            return False
        request = self.service.files().get_media(fileId=file['id'])
        fh = io.FileIO(save_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return True

    def upload_file(self, file_path, file_name):
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, mimetype='application/json', resumable=True)
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
        return file.get('id')

drive_service = GoogleDriveService()

# ================= GERENCIAMENTO DE DADOS (cache em memória) =================
DATA_CACHE = {}
DATA_LOCK = asyncio.Lock()  # protege o cache em concorrência

def validate_data_structure_sync(data):
    if not isinstance(data, dict):
        return False
    for guild_id, streamers in data.items():
        if not isinstance(guild_id, str) or not isinstance(streamers, dict):
            return False
        for twitch_user, discord_id in streamers.items():
            if not isinstance(twitch_user, str) or not isinstance(discord_id, str):
                return False
    return True

def backup_data_sync():
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

async def load_data_from_drive_if_exists():
    """Baixa do Drive (se existir) e carrega no DATA_CACHE. Executa bloqueante via to_thread"""
    global DATA_CACHE
    async with DATA_LOCK:
        # tenta baixar do Drive (blocking)
        try:
            downloaded = await asyncio.to_thread(drive_service.download_file, DATA_FILE, DATA_FILE)
            if downloaded:
                # leitura assíncrona do arquivo local
                async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                    content = (await f.read()).strip()
                if not content:
                    DATA_CACHE = {}
                    logger.warning("⚠️ Arquivo do Drive vazio, usando {}")
                else:
                    data = json.loads(content)
                    if not validate_data_structure_sync(data):
                        raise ValueError("Estrutura de dados inválida no Drive")
                    DATA_CACHE = data
                    logger.info("✅ Dados carregados do Drive para cache")
            else:
                # arquivo não existe no Drive: se existir local, carrega; senão cria vazio
                if os.path.exists(DATA_FILE):
                    async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                        content = (await f.read()).strip()
                    DATA_CACHE = json.loads(content) if content else {}
                    logger.info("ℹ️ Dados carregados do arquivo local para cache")
                else:
                    DATA_CACHE = {}
                    logger.info("ℹ️ Nenhum arquivo de dados encontrado; cache inicializado vazio")
        except Exception as e:
            logger.error(f"❌ Falha ao carregar dados do Drive: {e}")
            # fallback: tenta abrir local
            try:
                if os.path.exists(DATA_FILE):
                    async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                        content = (await f.read()).strip()
                    DATA_CACHE = json.loads(content) if content else {}
                    logger.info("ℹ️ Fallback para arquivo local realizado")
                else:
                    DATA_CACHE = {}
            except Exception as e2:
                logger.error(f"❌ Fallback local falhou: {e2}")
                DATA_CACHE = {}

async def save_data_to_drive(data):
    """Salva DATA_CACHE em disco e envia para Drive (upload blocking via to_thread)"""
    async with DATA_LOCK:
        if not validate_data_structure_sync(data):
            raise ValueError("Dados não passaram na validação de estrutura")
        # backup síncrono em thread
        await asyncio.to_thread(backup_data_sync)
        # gravação assíncrona do arquivo local
        async with aiofiles.open(DATA_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        # upload para Drive (blocking) via to_thread
        try:
            file_id = await asyncio.to_thread(drive_service.upload_file, DATA_FILE, DATA_FILE)
            logger.info(f"📤 Upload concluído (file id: {file_id})")
        except Exception as e:
            logger.error(f"❌ Falha ao enviar para o Google Drive: {e}")
            # não raise — queremos que o bot continue funcionando mesmo se o upload falhar

# Funções utilitárias para manipular cache
async def get_cached_data():
    async with DATA_LOCK:
        # devolve uma cópia para evitar alterações acidentais
        return json.loads(json.dumps(DATA_CACHE))

async def set_cached_data(new_data, persist=True):
    global DATA_CACHE
    async with DATA_LOCK:
        DATA_CACHE = new_data
    if persist:
        await save_data_to_drive(new_data)

# ================= TWITCH API (usa sessão aiohttp persistente) =================
class TwitchAPI:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.token = None
        self.token_expiry = None
        self.lock = asyncio.Lock()

    async def get_token(self, retries=3):
        async with self.lock:
            # se token válido, retorna
            if self.token and self.token_expiry and datetime.now() < self.token_expiry:
                return self.token
            for attempt in range(retries):
                try:
                    url = "https://id.twitch.tv/oauth2/token"
                    params = {
                        "client_id": TWITCH_CLIENT_ID,
                        "client_secret": TWITCH_SECRET,
                        "grant_type": "client_credentials"
                    }
                    async with self.session.post(url, params=params, timeout=15) as resp:
                        data = await resp.json()
                        if resp.status != 200 or "access_token" not in data:
                            logger.error(f"Falha ao obter token da Twitch: {resp.status} - {data}")
                            await asyncio.sleep(2)
                            continue
                        self.token = data["access_token"]
                        # normalmente token expira em 3600s, usamos margem
                        self.token_expiry = datetime.now() + timedelta(seconds=3300)
                        logger.info("✅ Token da Twitch obtido")
                        return self.token
                except Exception as e:
                    logger.error(f"Erro ao obter token (tentativa {attempt+1}): {e}")
                    await asyncio.sleep(2)
            logger.error("❌ Não foi possível obter token da Twitch após tentativas")
            return None

    async def validate_streamer(self, username: str) -> bool:
        token = await self.get_token()
        if not token:
            return False
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }
        try:
            url = f"https://api.twitch.tv/helix/users?login={username}"
            async with self.session.get(url, headers=headers, timeout=15) as resp:
                data = await resp.json()
                return len(data.get("data", [])) > 0
        except Exception as e:
            logger.error(f"Erro ao validar streamer '{username}': {e}")
            return False

    async def check_live_streams(self, usernames):
        """Recebe um iterable de usernames (lowercase) e retorna set de quem está live"""
        token = await self.get_token()
        if not token:
            return set()
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }
        live = set()
        batch_size = 100
        usernames = list(usernames)
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i:i+batch_size]
            url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(batch)
            try:
                async with self.session.get(url, headers=headers, timeout=20) as resp:
                    data = await resp.json()
                    live.update({s["user_login"].lower() for s in data.get("data", [])})
            except Exception as e:
                logger.error(f"Erro ao checar lives (batch starting {i}): {e}")
            await asyncio.sleep(0.8)  # throttle leve
        return live

# ================= DISCORD BOT =================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="Streamers da Twitch")
)

# Variáveis que serão inicializadas em on_ready
HTTP_SESSION = None
twitch_api = None
CHECK_TASK = None

# Utilitários do bot
async def get_or_create_live_role(guild: discord.Guild):
    role = discord.utils.get(guild.roles, name="Ao Vivo")
    if role:
        return role
    try:
        role = await guild.create_role(
            name="Ao Vivo",
            color=discord.Color.purple(),
            hoist=True,
            mentionable=True
        )
        return role
    except Exception as e:
        logger.error(f"Erro ao criar cargo 'Ao Vivo' no guild {guild.id}: {e}")
        return None

def sanitize_discord_id(input_str: str) -> str:
    digits = re.sub(r'\D', '', input_str)
    if not digits.isdigit() or not (17 <= len(digits) <= 19):
        return ""
    return digits

# ================= UI (modal, view) =================
class AddStreamerModal(ui.Modal, title="Adicionar Streamer"):
    twitch_name = ui.TextInput(label="Nome na Twitch", placeholder="ex: alanzoka", min_length=3, max_length=25)
    discord_id = ui.TextInput(label="ID/Menção do Discord", placeholder="Digite o ID ou @usuário", min_length=3, max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Apenas administradores podem usar este comando!", ephemeral=True)
                return

            twitch_username = self.twitch_name.value.lower().strip()
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message("❌ Nome inválido na Twitch! Use apenas letras, números e _", ephemeral=True)
                return

            # valida Twitch via API
            if not await twitch_api.validate_streamer(twitch_username):
                await interaction.response.send_message(f"❌ Streamer '{twitch_username}' não encontrado na Twitch!", ephemeral=True)
                return

            discord_input = self.discord_id.value.strip()
            discord_id = sanitize_discord_id(discord_input)
            if not discord_id:
                await interaction.response.send_message("❌ ID Discord inválido! Deve ter entre 17 e 19 dígitos.", ephemeral=True)
                return

            member = interaction.guild.get_member(int(discord_id))
            if not member:
                await interaction.response.send_message("❌ Membro não encontrado no servidor!", ephemeral=True)
                return

            # atualiza cache e persiste
            data = await get_cached_data()
            guild_id = str(interaction.guild.id)
            if guild_id not in data:
                data[guild_id] = {}

            if twitch_username in data[guild_id]:
                await interaction.response.send_message(f"⚠️ O streamer '{twitch_username}' já está vinculado!", ephemeral=True)
                return

            data[guild_id][twitch_username] = discord_id
            await set_cached_data(data, persist=True)

            await interaction.response.send_message(f"✅ {member.mention} vinculado ao Twitch: `{twitch_username}`", ephemeral=True)

        except Exception as e:
            logger.error(f"Erro ao adicionar streamer: {e}")
            await interaction.response.send_message("❌ Erro interno ao processar!", ephemeral=True)

class StreamersView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Apenas administradores podem usar este painel!", ephemeral=True)
            return False
        return True

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_streamer(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddStreamerModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get(str(interaction.guild.id), {})
        if not guild_streamers:
            await interaction.response.send_message("❌ Nenhum streamer vinculado neste servidor!", ephemeral=True)
            return

        options = []
        for streamer, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            desc = f"Vinculado a: {member.display_name if member else 'Não encontrado'}"
            options.append(discord.SelectOption(label=streamer, description=desc, value=streamer))

        select = ui.Select(placeholder="Selecione um streamer para remover...", options=options, custom_id="select_remove_streamer")

        async def callback(inner_interaction: discord.Interaction):
            try:
                selected = select.values[0]
                data_local = await get_cached_data()
                guild_id = str(inner_interaction.guild.id)
                if selected in data_local.get(guild_id, {}):
                    del data_local[guild_id][selected]
                    await set_cached_data(data_local, persist=True)
                    await inner_interaction.response.send_message(f"✅ Streamer '{selected}' removido!", ephemeral=True)
                else:
                    await inner_interaction.response.send_message("❌ Streamer não encontrado (provavelmente já removido).", ephemeral=True)
            except Exception as e:
                logger.error(f"Erro no callback de remoção: {e}")
                await inner_interaction.response.send_message("❌ Erro ao remover streamer.", ephemeral=True)

        select.callback = callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_streamers(self, interaction: discord.Interaction, button: ui.Button):
        data = await get_cached_data()
        guild_streamers = data.get(str(interaction.guild.id), {})
        if not guild_streamers:
            await interaction.response.send_message("📭 Nenhum streamer vinculado neste servidor!", ephemeral=True)
            return

        embed = discord.Embed(title="🎮 Streamers Vinculados", color=0x9147FF)
        for twitch_user, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            embed.add_field(name=f"🔹 {twitch_user}", value=f"Discord: {member.mention if member else '🚨 Não encontrado'}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ================= COMANDOS DO BOT =================
@bot.tree.command(name="streamers", description="Gerenciar streamers vinculados")
@app_commands.checks.has_permissions(administrator=True)
async def streamers_command(interaction: discord.Interaction):
    await interaction.response.send_message("**🎮 Painel de Streamers** - Escolha uma opção:", view=StreamersView(), ephemeral=True)

@bot.tree.command(name="status", description="Verifica o status do bot")
async def status_command(interaction: discord.Interaction):
    uptime = datetime.now() - START_TIME
    data = await get_cached_data()
    total_streamers = sum(len(g) for g in data.values())
    embed = discord.Embed(title="🤖 Status do Bot", color=0x00FF00)
    embed.add_field(name="⏱ Uptime", value=str(uptime).split('.')[0], inline=False)
    embed.add_field(name="📊 Streamers monitorados", value=f"{total_streamers} em {len(data)} servidores", inline=False)
    embed.add_field(name="🔄 Última verificação", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ================= TASK: CHECK STREAMS =================
async def check_streams_task():
    await bot.wait_until_ready()
    logger.info("✅ Task de checagem iniciada")
    while not bot.is_closed():
        try:
            data = await get_cached_data()
            all_streamers = {twitch_user for guild_data in data.values() for twitch_user in guild_data.keys()}
            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            live_streamers = await twitch_api.check_live_streams(all_streamers)

            for guild_id, streamers in data.items():
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue

                live_role = await get_or_create_live_role(guild)
                if live_role is None:
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
                        logger.error(f"Erro ao atualizar cargo para {twitch_user} ({discord_id}): {e}")

        except Exception as e:
            logger.error(f"Erro no verificador principal: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# ================= EVENTOS =================
@bot.event
async def on_ready():
    global HTTP_SESSION, twitch_api, CHECK_TASK
    logger.info(f"✅ Bot conectado como {bot.user} (id={bot.user.id})")
    # inicializa sessão aiohttp e TwitchAPI (se ainda não)
    if HTTP_SESSION is None:
        # cria sessão com connector padrão
        bot.loop.create_task(initialize_services())

    # sincroniza comandos e garante task única
    try:
        await bot.tree.sync()
        logger.info("✅ Comandos sincronizados")
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos: {e}")

    # inicia task de checagem se não estiver
    if CHECK_TASK is None or CHECK_TASK.done():
        CHECK_TASK = bot.loop.create_task(check_streams_task())

async def initialize_services():
    global HTTP_SESSION, twitch_api
    if HTTP_SESSION is None:
        HTTP_SESSION = aiohttp.ClientSession()
        twitch_api = TwitchAPI(HTTP_SESSION)
    # carrega dados do Drive para cache
    await load_data_from_drive_if_exists()

# ================= SHUTDOWN LIMPO =================
async def graceful_shutdown():
    global HTTP_SESSION, CHECK_TASK
    logger.info("🔻 Iniciando shutdown limpo")
    if CHECK_TASK:
        CHECK_TASK.cancel()
    if HTTP_SESSION:
        await HTTP_SESSION.close()
        logger.info("✅ Sessão HTTP fechada")
    await asyncio.sleep(0.5)

# captura sinal de desligamento do bot
@bot.event
async def on_disconnect():
    await graceful_shutdown()

# ================= INICIALIZAÇÃO MAIN =================
def run_bot():
    # garante que exista um arquivo local inicial (não obrigatório)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

    # inicia Flask em thread daemon
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    # roda bot (bloqueante)
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao rodar bot: {e}")

if __name__ == '__main__':
    run_bot()
