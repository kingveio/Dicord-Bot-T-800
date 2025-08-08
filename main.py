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
DATA_FILE = "streamers.json"  # Arquivo para armazenar os streamers vinculados
CHECK_INTERVAL = 55  # Intervalo de verificação de streams (em segundos)
START_TIME = datetime.now()  # Tempo de inicialização do bot

# ========== SERVIDOR FLASK PARA HEALTH CHECKS ==========
app = Flask(__name__)

# Variáveis globais para monitoramento
last_ping_time = time.time()
bot_ready = False

@app.route('/')
def home():
    """Rota principal para verificar se o bot está online"""
    return "🤖 Bot Twitch Online! Use /ping para status."

@app.route('/ping')
def ping():
    """Rota para health checks e manter o bot ativo"""
    global last_ping_time
    last_ping_time = time.time()
    return jsonify({
        "status": "online",
        "bot_ready": bot_ready,
        "uptime": str(datetime.now() - START_TIME),
        "last_check": getattr(bot, '_last_check', 'N/A')
    }), 200

@app.route('/status')
def status():
    """Rota detalhada de status dos serviços"""
    return jsonify({
        "status": "online",
        "services": {
            "discord_bot": bot_ready,
            "twitch_api": hasattr(bot, '_twitch_token_valid'),
            "last_stream_check": getattr(bot, '_last_check', 'N/A')
        },
        "timestamp": datetime.now().isoformat()
    }), 200

def run_flask():
    """Inicia o servidor Flask em uma thread separada"""
    app.run(host='0.0.0.0', port=8080, threaded=True, use_reloader=False)

# ========== CONFIGURAÇÃO DO BOT DISCORD ==========
intents = discord.Intents.default()
intents.members = True  # Necessário para verificar membros
intents.message_content = True  # Necessário para comandos de mensagem

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Exterminador do Futuro 2"
    )
)

# ========== GERENCIAMENTO DE DADOS DOS STREAMERS ==========
def load_data():
    """Carrega os dados dos streamers do arquivo JSON"""
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
    """Salva os dados dos streamers no arquivo JSON"""
    try:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Erro ao salvar dados: %s", e)

# ========== INTEGRAÇÃO COM A API DA TWITCH ==========
class TwitchAPI:
    """Classe para gerenciar a integração com a API da Twitch"""
    def __init__(self):
        self.token = None
        self.token_expiry = None
        bot._twitch_token_valid = False

    async def get_token(self, retries=3):
        """Obtém um token de acesso da API Twitch com retentativas"""
        for attempt in range(retries):
            try:
                # Se já temos um token válido, retorna ele
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
                        if response.status != 200:
                            raise Exception(f"Status code: {response.status}")
                            
                        data = await response.json()
                        self.token = data["access_token"]
                        # Token expira em 1 hora, mas renovamos em 55 minutos
                        self.token_expiry = datetime.now() + timedelta(seconds=3300)
                        bot._twitch_token_valid = True
                        logger.info("🔑 Novo token Twitch obtido")
                        return self.token
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Erro ao obter token Twitch (tentativa {attempt+1}/{retries}): {e}")
                    bot._twitch_token_valid = False
                await asyncio.sleep(5 * (attempt + 1))
        return None

    async def validate_streamer(self, username):
        """Verifica se um streamer existe na Twitch"""
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
                    if response.status != 200:
                        return False
                    data = await response.json()
                    return len(data.get("data", [])) > 0
        except Exception:
            return False

    async def check_live_streams(self, usernames):
        """Verifica quais streamers estão ao vivo"""
        token = await self.get_token()
        if not token:
            return set()

        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {token}"
        }

        try:
            # Processa em lotes de 100 streamers (limite da API Twitch)
            live_streamers = set()
            batch_size = 100
            usernames_list = list(usernames)
            
            for i in range(0, len(usernames_list), batch_size):
                batch = usernames_list[i:i + batch_size]
                url = "https://api.twitch.tv/helix/streams?user_login=" + "&user_login=".join(batch)
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=15) as response:
                        if response.status != 200:
                            logger.error("Erro na API Twitch: %s", response.status)
                            continue

                        data = await response.json()
                        bot._last_check = datetime.now().isoformat()
                        live_streamers.update({s["user_login"].lower() for s in data.get("data", [])})
                        
                # Pequena pausa entre lotes para evitar rate limits
                await asyncio.sleep(1)
                
            return live_streamers
        except Exception as e:
            logger.error("Erro ao verificar streams: %s", e)
            return set()

twitch_api = TwitchAPI()

# ========== INTERFACE DO DISCORD (MODAL PARA ADICIONAR STREAMERS) ==========
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
        """Processa o formulário quando enviado"""
        try:
            # Verifica se o usuário é administrador
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ Apenas administradores podem adicionar streamers!",
                    ephemeral=True
                )
                return

            twitch_username = self.twitch_name.value.lower().strip()
            discord_input = self.discord_id.value.strip()
            
            # Debug (opcional - pode remover depois)
            logger.debug(f"Input recebido - Twitch: {twitch_username} | Discord: {discord_input}")
            
            # Validação do nome Twitch
            if not re.match(r'^[a-zA-Z0-9_]{3,25}$', twitch_username):
                await interaction.response.send_message(
                    "❌ Nome de usuário inválido! Use apenas letras, números e underscores.",
                    ephemeral=True
                )
                return
                
            # Verifica se o streamer existe na Twitch
            if not await twitch_api.validate_streamer(twitch_username):
                await interaction.response.send_message(
                    f"❌ Não foi possível encontrar '{twitch_username}' na Twitch!",
                    ephemeral=True
                )
                return

            # EXTRAÇÃO E VALIDAÇÃO DO ID DISCORD (PARTE CRÍTICA)
            discord_id = None
            
            # Caso 1: É uma menção (@usuário)
            if discord_input.startswith('<@') and discord_input.endswith('>'):
                discord_id = ''.join(c for c in discord_input if c.isdigit())
                # Remove o '!' que pode aparecer em algumas menções
                discord_id = discord_id.replace('!', '')
                
            # Caso 2: É um ID numérico
            elif discord_input.isdigit():
                discord_id = discord_input
                
            # Caso 3: Formato inválido
            else:
                await interaction.response.send_message(
                    "❌ Formato inválido! Use:\n• ID (18 dígitos)\n• Ou mencione (@usuário)",
                    ephemeral=True
                )
                return
                
            # Verifica se o ID tem 18 dígitos
            if len(discord_id) != 18:
                await interaction.response.send_message(
                    "❌ ID do Discord deve ter exatamente 18 dígitos!",
                    ephemeral=True
                )
                return

            # Verifica se o usuário existe no servidor
            member = interaction.guild.get_member(int(discord_id))
            if not member:
                await interaction.response.send_message(
                    "❌ Usuário não encontrado no servidor! Verifique se:"
                    "\n1. O ID está correto"
                    "\n2. O usuário está no servidor"
                    "\n3. O bot tem permissão para ver membros",
                    ephemeral=True
                )
                return

            # Verifica se o streamer já está cadastrado
            data = load_data()
            guild_id = str(interaction.guild.id)

            if guild_id not in data:
                data[guild_id] = {}

            if twitch_username in data[guild_id]:
                existing_user_id = data[guild_id][twitch_username]
                await interaction.response.send_message(
                    f"⚠️ O streamer '{twitch_username}' já está vinculado a <@{existing_user_id}>",
                    ephemeral=True
                )
                return

            # Salva os dados
            data[guild_id][twitch_username] = discord_id
            save_data(data)

            await interaction.response.send_message(
                f"✅ {member.mention} vinculado ao Twitch: `{twitch_username}`",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Erro ao adicionar streamer: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Ocorreu um erro interno ao processar sua solicitação",
                ephemeral=True
            )

# ========== INTERFACE DO DISCORD (VIEW COM BOTÕES) ==========
class StreamersView(ui.View):
    """View com botões para gerenciar streamers"""
    def __init__(self):
        super().__init__(timeout=None)  # Timeout None para persistência

    @ui.button(label="Adicionar", style=discord.ButtonStyle.green, emoji="➕", custom_id="add_streamer")
    async def add_streamer(self, interaction: discord.Interaction, button: ui.Button):
        """Abre o modal para adicionar um novo streamer"""
        await interaction.response.send_modal(AddStreamerModal())

    @ui.button(label="Remover", style=discord.ButtonStyle.red, emoji="➖", custom_id="remove_streamer")
    async def remove_streamer(self, interaction: discord.Interaction, button: ui.Button):
        """Mostra um menu para remover streamers"""
        data = load_data()
        guild_streamers = data.get(str(interaction.guild.id), {})

        if not guild_streamers:
            await interaction.response.send_message("❌ Nenhum streamer registrado!", ephemeral=True)
            return

        # Cria um menu dropdown para selecionar qual streamer remover
        select = ui.Select(placeholder="Selecione um streamer para remover...")
        
        for streamer, discord_id in guild_streamers.items():
            member = interaction.guild.get_member(int(discord_id))
            select.add_option(
                label=f"{streamer}",
                description=f"Vinculado a: {member.display_name if member else 'Não encontrado'}",
                value=streamer
            )

        async def callback(interaction: discord.Interaction):
            """Callback quando um streamer é selecionado para remoção"""
            data = load_data()
            guild_id = str(interaction.guild.id)

            if guild_id in data and select.values[0] in data[guild_id]:
                removed_user = select.values[0]
                member_id = data[guild_id][removed_user]
                member = interaction.guild.get_member(int(member_id))
                
                del data[guild_id][removed_user]
                save_data(data)
                
                await interaction.response.send_message(
                    f"✅ Removido: `{removed_user}` (vinculado a {member.mention if member else 'usuário desconhecido'})",
                    ephemeral=True
                )

        select.callback = callback
        view = ui.View()
        view.add_item(select)
        await interaction.response.send_message(view=view, ephemeral=True)

    @ui.button(label="Listar", style=discord.ButtonStyle.blurple, emoji="📜", custom_id="list_streamers")
    async def list_streamers(self, interaction: discord.Interaction, button: ui.Button):
        """Mostra a lista de todos os streamers vinculados"""
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
    """Verifica periodicamente quais streamers estão ao vivo"""
    while True:
        try:
            data = load_data()
            if not data:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # Coleta todos os streamers de todas as guildas
            all_streamers = set()
            for guild_streamers in data.values():
                all_streamers.update(guild_streamers.keys())

            if not all_streamers:
                await asyncio.sleep(CHECK_INTERVAL)
                continue

            # Verifica quais estão ao vivo
            live_streamers = await twitch_api.check_live_streams(all_streamers)

            # Processa cada guilda separadamente
            for guild_id, streamers in data.items():
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue

                # Obtém ou cria o cargo "Ao Vivo"
                live_role = discord.utils.get(guild.roles, name="Ao Vivo")
                if not live_role:
                    try:
                        live_role = await guild.create_role(
                            name="Ao Vivo",
                            color=discord.Color.purple(),
                            hoist=True,
                            mentionable=True
                        )
                        logger.info(f"✅ Cargo 'Ao Vivo' criado em {guild.name}")
                    except Exception as e:
                        logger.error(f"Erro ao criar cargo em {guild.name}: {e}")
                        continue

                # Processa cada streamer da guilda
                for twitch_user, discord_id in streamers.items():
                    try:
                        member = guild.get_member(int(discord_id))
                        if not member:
                            continue

                        is_live = twitch_user.lower() in live_streamers
                        has_role = live_role in member.roles

                        # Atualiza os cargos conforme necessário
                        if is_live and not has_role:
                            await member.add_roles(live_role)
                            logger.info(f"➕ Cargo adicionado para {member} ({twitch_user})")
                            
                            # Envia notificação se possível
                            channel = guild.system_channel or discord.utils.get(guild.text_channels, name="geral")
                            if channel and channel.permissions_for(guild.me).send_messages:
                                try:
                                    await channel.send(
                                        f"🎥 {member.mention} está ao vivo na Twitch como `{twitch_user}`!",
                                        allowed_mentions=discord.AllowedMentions(users=True))
                                except Exception as e:
                                    logger.error(f"Erro ao enviar mensagem em {guild.name}: {e}")
                            
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                            logger.info(f"➖ Cargo removido de {member} ({twitch_user})")
                            
                    except Exception as e:
                        logger.error(f"Erro ao atualizar cargo em {guild.name}: {e}")

        except Exception as e:
            logger.error(f"Erro no verificador de streams: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# ========== SISTEMA DE PING PARA MANTER O BOT ATIVO ==========
def background_pinger():
    """Faz ping periódico para evitar dormência em serviços como Render"""
    while True:
        try:
            # Ping interno
            with app.test_client() as client:
                client.get('/ping')

            # Ping externo se estiver no Render
            if 'RENDER_EXTERNAL_URL' in os.environ:
                requests.get(f"{os.environ['RENDER_EXTERNAL_URL']}/ping", timeout=10)
                
        except Exception as e:
            logger.error(f"Erro no pinger: {e}")
        
        time.sleep(45)

# ========== COMANDOS SLASH ==========
@bot.tree.command(name="streamers", description="Gerenciar notificações de streamers")
@app_commands.default_permissions(manage_guild=True)
async def streamers_command(interaction: discord.Interaction):
    """Comando principal para gerenciar streamers"""
    await interaction.response.send_message(
        "**🎮 Painel de Streamers** - Escolha uma opção:",
        view=StreamersView(),
        ephemeral=True
    )

@bot.tree.command(name="ajuda", description="Mostra informações sobre o bot")
async def ajuda(interaction: discord.Interaction):
    """Comando de ajuda para usuários"""
    embed = discord.Embed(title="Ajuda do Bot de Twitch", color=0x9147FF)
    embed.add_field(
        name="/streamers", 
        value="Gerencia os streamers monitorados (requer permissão 'Gerenciar Servidor')", 
        inline=False
    )
    embed.add_field(
        name="!setup", 
        value="Configura o cargo 'Ao Vivo' no servidor", 
        inline=False
    )
    embed.add_field(
        name="Como funciona",
        value="O bot verifica a cada minuto quem está ao vivo e atribui o cargo 'Ao Vivo'. "
              "Quando a transmissão termina, o cargo é removido.",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== COMANDOS DE TEXTO (LEGACY) ==========
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx: commands.Context):
    """Sincroniza os comandos slash com o servidor"""
    try:
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ {len(synced)} comandos sincronizados!")
    except Exception as e:
        await ctx.send(f"❌ Erro: {e}")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def setup(ctx: commands.Context):
    """Configura o cargo 'Ao Vivo' no servidor"""
    live_role = discord.utils.get(ctx.guild.roles, name="Ao Vivo")
    if not live_role:
        try:
            live_role = await ctx.guild.create_role(
                name="Ao Vivo",
                color=discord.Color.purple(),
                hoist=True,
                mentionable=True
            )
            await ctx.send(f"✅ Cargo criado: {live_role.mention}")
        except Exception as e:
            await ctx.send(f"❌ Erro ao criar cargo: {e}")
            return
    await ctx.send("✅ Bot configurado! Use `/streamers` para gerenciar os streamers.")

# ========== EVENTOS DO BOT ==========
@bot.event
async def on_ready():
    """Evento disparado quando o bot está pronto"""
    global bot_ready
    bot_ready = True
    
    logger.info(f"✅ Bot conectado como {bot.user}")
    logger.info(f"🌐 Servidores: {len(bot.guilds)}")

    # Registra a view persistente
    bot.add_view(StreamersView())
    
    # Inicia as tarefas em segundo plano
    bot.loop.create_task(check_streams())
    
    # Inicia o pinger em uma thread separada
    threading.Thread(target=background_pinger, daemon=True).start()

    try:
        # Sincroniza os comandos slash
        synced = await bot.tree.sync()
        logger.info(f"🔗 {len(synced)} comandos slash sincronizados")
    except Exception as e:
        logger.error(f"⚠️ Erro ao sincronizar comandos: {e}")

# ========== INICIALIZAÇÃO COM SISTEMA DE REINÍCIO ==========
def run_bot():
    """Função para gerenciar o ciclo de vida do bot com reinícios controlados"""
    restart_count = 0
    max_restarts = 10
    restart_delay = 30  # Delay inicial em segundos

    while restart_count < max_restarts:
        try:
            logger.info(f"🚀 Iniciando bot (Tentativa {restart_count + 1}/{max_restarts})")
            
            # Inicia o servidor Flask em thread separada
            flask_thread = threading.Thread(target=run_flask, daemon=True)
            flask_thread.start()
            
            # Inicia o bot Discord
            bot.run(TOKEN)
            
            # Se bot.run() retornar normalmente, resetamos o contador
            restart_count = 0
            
        except discord.LoginError as e:
            logger.critical("❌ ERRO FATAL: Token do Discord inválido!")
            break  # Não tenta reiniciar para erros de autenticação
            
        except Exception as e:
            logger.error(f"⚠️ Erro na execução: {type(e).__name__} - {str(e)}")
            restart_count += 1
            
            if restart_count >= max_restarts:
                logger.critical("🔴 Máximo de reinícios atingido! Encerrando...")
                break
                
            # Calcula delay com backoff exponencial (máximo 5 minutos)
            delay = min(restart_delay * (2 ** (restart_count - 1)), 300)
            logger.info(f"⏳ Reiniciando em {delay} segundos...")
            time.sleep(delay)

if __name__ == '__main__':
    run_bot()  
