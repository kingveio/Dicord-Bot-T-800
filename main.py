# -*- coding: utf-8 -*-
import os
import json
import logging
import asyncio
import requests
from threading import Thread
import re
from github import Github
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask

# ==============================================================================
# 1. CONFIGURAÇÃO INICIAL
# ==============================================================================

# Força a desativação de voz para evitar o erro 'audioop'
os.environ.setdefault('DISCORD_VOICE', '0')
try:
    import discord.opus
    discord.opus.is_loaded = lambda: False
except ImportError:
    pass

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes da API
YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300  # 5 minutos
KEEP_ALIVE_INTERVAL = 240  # 4 minutos
MAX_CHANNELS_PER_REQUEST = 50

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

def is_valid_youtube_id(channel_id):
    """Valida o formato de um ID de canal do YouTube"""
    if not channel_id or not isinstance(channel_id, str):
        return False
    return re.match(r'^[A-Za-z]{2}[A-Za-z0-9_-]{22}$', channel_id) is not None

def verify_github_credentials():
    """Verifica as credenciais do GitHub"""
    required_vars = ['GITHUB_TOKEN', 'GITHUB_REPO']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        raise ValueError(f"Variáveis de ambiente GitHub faltando: {', '.join(missing)}")

    try:
        github = Github(os.getenv('GITHUB_TOKEN'))
        repo = github.get_repo(os.getenv('GITHUB_REPO'))
        logger.info(f"✅ Conexão com GitHub estabelecida. Repositório: {repo.full_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Falha na conexão com GitHub: {e}")
        raise

class StreamerManager:
    """Gerenciador de streamers com armazenamento no GitHub."""
    def __init__(self):
        try:
            self.github = Github(os.getenv('GITHUB_TOKEN'))
            self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
            self.file_path = 'streamers.json'
            self.data = self._load_or_create_file()
        except Exception as e:
            logger.critical(f"Falha ao iniciar StreamerManager: {e}")
            raise

    def _load_or_create_file(self):
        """Carrega o arquivo de dados ou cria um novo se não existir."""
        try:
            contents = self.repo.get_contents(self.file_path)
            return json.loads(contents.decoded_content.decode())
        except Exception:
            logger.info("Criando novo arquivo streamers.json")
            initial_data = {
                'users': {},
                'servers': {}
            }
            self._save_data(initial_data)
            return initial_data

    def _save_data(self, data=None):
        """Salva os dados no GitHub, atualizando ou criando o arquivo."""
        data_to_save = data if data else self.data
        try:
            contents = self.repo.get_contents(self.file_path)
            self.repo.update_file(
                contents.path,
                "Atualização automática de streamers",
                json.dumps(data_to_save, indent=2),
                contents.sha
            )
            logger.info("Dados salvos no GitHub.")
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")
            try:
                self.repo.create_file(
                    self.file_path,
                    "Criação do arquivo streamers.json",
                    json.dumps(data_to_save, indent=2)
                )
                logger.info("Arquivo streamers.json criado com sucesso.")
            except Exception as create_e:
                logger.error(f"Erro ao tentar criar o arquivo: {create_e}")

    def add_streamer(self, discord_user_id, youtube_channel_id):
        """Adiciona um novo streamer ao registro."""
        youtube_channel_id = youtube_channel_id.strip()
        if not is_valid_youtube_id(youtube_channel_id):
            return False, "ID do canal do YouTube inválido."
        if str(discord_user_id) in self.data['users']:
            return False, "Usuário já tem um canal vinculado."
            
        self.data['users'][str(discord_user_id)] = youtube_channel_id
        self._save_data()
        return True, "Streamer adicionado com sucesso."

    def remove_streamer(self, identifier):
        """Remove um streamer por ID do Discord ou ID do canal do YouTube."""
        identifier = str(identifier).strip()
        
        if identifier in self.data['users']:
            self.data['users'].pop(identifier)
            self._save_data()
            return True, "Streamer removido com sucesso."
            
        for user_id, youtube_id in list(self.data['users'].items()):
            if youtube_id.lower() == identifier.lower():
                self.data['users'].pop(user_id)
                self._save_data()
                return True, "Streamer removido com sucesso."
                
        return False, "Nenhum streamer encontrado."

    def set_live_role(self, server_id, role_id):
        """Configura o cargo 'ao vivo' para um servidor."""
        if str(server_id) not in self.data['servers']:
            self.data['servers'][str(server_id)] = {}
        self.data['servers'][str(server_id)]['live_role'] = str(role_id)
        self._save_data()

    def get_live_role(self, server_id):
        """Obtém o cargo 'ao vivo' de um servidor."""
        return self.data['servers'].get(str(server_id), {}).get('live_role')
        
    def set_permission_role(self, server_id, role_id):
        """Configura o cargo de permissão para o servidor."""
        if str(server_id) not in self.data['servers']:
            self.data['servers'][str(server_id)] = {}
        self.data['servers'][str(server_id)]['permission_role'] = str(role_id)
        self._save_data()

    def get_permission_role(self, server_id):
        """Obtém o cargo de permissão de um servidor."""
        return self.data['servers'].get(str(server_id), {}).get('permission_role')
        
    def check_permission(self, interaction: discord.Interaction):
        """Verifica se o usuário tem o cargo de permissão."""
        permission_role_id = self.get_permission_role(interaction.guild_id)
        if not permission_role_id:
            return False
            
        member_roles = [str(role.id) for role in interaction.user.roles]
        return permission_role_id in member_roles
        
    def get_all_streamers(self):
        """Retorna todos os streamers cadastrados."""
        return self.data['users']

# ==============================================================================
# 3. CONFIGURAÇÃO E INICIALIZAÇÃO DO BOT
# ==============================================================================

# Verifica as credenciais do GitHub antes de iniciar o bot
try:
    verify_github_credentials()
    manager = StreamerManager()
except Exception as e:
    logger.critical(f"Falha crítica na inicialização: {e}")
    exit(1)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Servidor Flask para manter o bot ativo
app = Flask(__name__)

@app.route('/health')
def home():
    """Endpoint de home para o Render/servidor."""
    return "Bot de monitoramento de streamers está online! Eu voltarei."

def run_flask():
    """Inicia o servidor Flask em um thread separado."""
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ==============================================================================
# 4. COMANDOS DO BOT
# ==============================================================================

@app_commands.command(name="youtube_canal", description="Vincula um canal do YouTube a um membro do Discord.")
async def youtube_canal(interaction: discord.Interaction,
                       id_do_canal: str,
                       usuario_do_discord: discord.Member):
    """
    Comando para adicionar um streamer do YouTube.
    """
    if not interaction.user.guild_permissions.administrator and not manager.check_permission(interaction):
        await interaction.response.send_message(
            "⚠️ Acesso negado. Você não tem permissão para usar este comando. Eu tenho as coordenadas.",
            ephemeral=True
        )
        return

    success, message = manager.add_streamer(str(usuario_do_discord.id), id_do_canal)
    await interaction.response.send_message(
        f"✅ {message.replace('Streamer adicionado com sucesso.', f'Canal do YouTube com ID **{id_do_canal}** vinculado a {usuario_do_discord.mention}. Missão cumprida.')}"
        if success
        else f"⚠️ {message.replace('Usuário já tem um canal vinculado.', 'Acesso negado. O usuário já tem um canal vinculado. Eu tenho as coordenadas.')}",
        ephemeral=True
    )

@app_commands.command(name="remover_streamer", description="Remove um streamer vinculado. Hasta la vista, baby.")
async def remove_streamer(interaction: discord.Interaction,
                          identificador: str):
    """
    Comando para remover um streamer por ID do Discord ou ID do canal do YouTube.
    """
    if not interaction.user.guild_permissions.administrator and not manager.check_permission(interaction):
        await interaction.response.send_message(
            "⚠️ Acesso negado. Você não tem permissão para usar este comando. Verificação de dados falhou.",
            ephemeral=True
        )
        return

    success, message = manager.remove_streamer(identificador)
    await interaction.response.send_message(
        f"✅ {message.replace('Streamer removido com sucesso.', 'Streamer removido com sucesso. Hasta la vista, baby.')}"
        if success
        else f"⚠️ {message.replace('Nenhum streamer encontrado.', 'Nenhum alvo encontrado. Verificação de dados falhou.')}",
        ephemeral=True
    )

@app_commands.command(name="configurar_cargo", description="Define o cargo para streamers ao vivo. Resistência ativada.")
@app_commands.default_permissions(administrator=True)
async def set_live_role(interaction: discord.Interaction, cargo: discord.Role):
    """
    Comando para configurar o cargo que será dado aos streamers ao vivo.
    """
    manager.set_live_role(str(interaction.guild.id), cargo.id)
    await interaction.response.send_message(
        f"✅ O cargo de **{cargo.name}** foi configurado para os soldados da resistência. Agora eles brilharão ao vivo!",
        ephemeral=True
    )
    
@app_commands.command(name="configurar_permissao", description="Define o cargo para quem pode usar os comandos de gerenciamento de streamers.")
@app_commands.default_permissions(administrator=True)
async def set_permission_role(interaction: discord.Interaction, cargo: discord.Role):
    """
    Comando para configurar o cargo de permissão.
    """
    manager.set_permission_role(str(interaction.guild.id), cargo.id)
    await interaction.response.send_message(
        f"✅ O cargo de **{cargo.name}** foi configurado para gerenciar os streamers. O controle foi estabelecido.",
        ephemeral=True
    )

@app_commands.command(name="listar_streamers", description="Lista todos os streamers cadastrados.")
async def list_streamers(interaction: discord.Interaction):
    """
    Comando para listar todos os streamers cadastrados.
    """
    streamers = manager.get_all_streamers()
    if not streamers:
        await interaction.response.send_message("Não há streamers cadastrados.", ephemeral=True)
        return

    response_message = "**Streamers Cadastrados:**\n"
    for discord_id, youtube_id in streamers.items():
        try:
            member = interaction.guild.get_member(int(discord_id))
            if member:
                response_message += f"• **{member.display_name}**: Canal com ID `{youtube_id}`\n"
            else:
                response_message += f"• **Usuário não encontrado**: Canal com ID `{youtube_id}`\n"
        except (ValueError, TypeError):
            response_message += f"• **Usuário com ID {discord_id}**: Canal com ID `{youtube_id}`\n"
            
    await interaction.response.send_message(response_message, ephemeral=True)

# Fim dos codigos dos comandos

# ==============================================================================
# 5. ROTINAS E LOOPS DE BACKGROUND
# ==============================================================================

async def check_live_streams():
    """Loop assíncrono para verificar o status dos streamers no YouTube."""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            youtube_channel_ids = list(manager.data['users'].values())
            online_channels = get_youtube_status(youtube_channel_ids)
            
            for guild in bot.guilds:
                live_role_id = manager.get_live_role(str(guild.id))
                if not live_role_id:
                    continue
                    
                live_role = guild.get_role(int(live_role_id))
                if not live_role:
                    continue
                    
                for discord_id, youtube_channel_id in manager.data['users'].items():
                    try:
                        member = await guild.fetch_member(int(discord_id))
                        is_live = youtube_channel_id in online_channels
                        has_role = live_role in member.roles
                        
                        if is_live and not has_role:
                            await member.add_roles(live_role)
                            logger.info(f"Cargo adicionado para {member.display_name}")
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                            logger.info(f"Cargo removido de {member.display_name}")
                    except Exception as e:
                        logger.error(f"Erro ao atualizar cargo: {e}")
                        
        except Exception as e:
            logger.error(f"Erro no loop de monitoramento: {e}")
            
        await asyncio.sleep(POLLING_INTERVAL)

async def keep_alive():
    """
    Loop assíncrono para enviar requisições HTTP para o próprio bot,
    mantendo-o ativo no serviço de hospedagem.
    """
    await bot.wait_until_ready()
    port = os.environ.get('PORT', 8080)
    
    while not bot.is_closed():
        try:
            # Requer o nome do host do Render para a requisição
            host_url = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            if host_url:
                # Adiciona explicitamente a porta e o endpoint de health check
                requests.get(f'http://{host_url}:{port}/health', timeout=5)
                logger.info("Keep-alive request sent.")
            else:
                logger.warning("RENDER_EXTERNAL_HOSTNAME not found, cannot send keep-alive.")
        except Exception as e:
            logger.error(f"Erro no keep-alive: {e}")
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)

# Fim das rotinas e loops de background

# ==============================================================================
# 6. FUNÇÕES AUXILIARES DO YOUTUBE
# ==============================================================================

def get_youtube_status(channel_ids):
    """
    Verifica quais canais do YouTube estão online.
    """
    if not channel_ids:
        return set()

    online_channels = set()
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        logger.error("YOUTUBE_API_KEY não está configurada.")
        return online_channels

    try:
        # A API de busca do YouTube pode receber até 50 channelIds por requisição.
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i+50]
            
            response = requests.get(
                f'{YOUTUBE_API_URL}/search',
                params={
                    'key': api_key,
                    'channelId': ','.join(batch),
                    'part': 'snippet',
                    'eventType': 'live',
                    'type': 'video'
                },
                timeout=15
            )
            response.raise_for_status()

            for item in response.json().get('items', []):
                online_channels.add(item['snippet']['channelId'])

    except Exception as e:
        logger.error(f"Erro ao verificar streams do YouTube: {e}")
    
    return online_channels

# Fim das funções auxiliares do YouTube

# ==============================================================================
# 7. INÍCIO DO PROGRAMA
# ==============================================================================

@bot.event
async def on_ready():
    """Executado quando o bot se conecta ao Discord."""
    logger.info(f'Bot conectado como {bot.user} (ID: {bot.user.id}). Missão: proteger a resistência.')
    
    # Define a atividade do bot
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Procurando alvos online"))
    
    # Sincroniza os comandos de barra
    await bot.tree.sync()
    
    # Inicia os loops de background
    bot.loop.create_task(check_live_streams())
    bot.loop.create_task(keep_alive())

# Registra os comandos do bot
bot.tree.add_command(youtube_canal)
bot.tree.add_command(remove_streamer)
bot.tree.add_command(set_live_role)
bot.tree.add_command(set_permission_role)
bot.tree.add_command(list_streamers)

if __name__ == '__main__':
    # Inicia o servidor Flask em um thread separado
    Thread(target=run_flask, daemon=True).start()
    
    # Inicia o bot do Discord
    bot.run(os.getenv('DISCORD_TOKEN'))

# Fim do programa
