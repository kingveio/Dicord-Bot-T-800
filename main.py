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

# ==============================================================================
# 3. GERENCIADOR DE STREAMERS
# ==============================================================================

class StreamerManager:
    """Gerenciador de streamers com armazenamento no GitHub."""
    
    def __init__(self):
        try:
            self.github = Github(os.getenv('GITHUB_TOKEN'))
            self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
            self.file_path = 'streamersyoutube.json'  # Nome do arquivo alterado
            self.data = self._load_or_create_file()
        except Exception as e:
            logger.critical(f"Falha ao iniciar StreamerManager: {e}")
            raise

    def _load_or_create_file(self):
        """Carrega ou cria o arquivo de dados"""
        try:
            contents = self.repo.get_contents(self.file_path)
            return json.loads(contents.decoded_content.decode())
        except Exception:
            logger.info(f"Criando novo arquivo {self.file_path}")
            initial_data = {
                'users': {},
                'servers': {}
            }
            self._save_data(initial_data)
            return initial_data

    def _save_data(self, data=None):
        """Salva os dados no GitHub"""
        data_to_save = data if data else self.data
        try:
            contents = self.repo.get_contents(self.file_path)
            self.repo.update_file(
                contents.path,
                f"Atualização automática de {self.file_path}",
                json.dumps(data_to_save, indent=2),
                contents.sha
            )
            logger.info(f"Dados salvos em {self.file_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar dados: {e}")
            try:
                self.repo.create_file(
                    self.file_path,
                    f"Criação do arquivo {self.file_path}",
                    json.dumps(data_to_save, indent=2)
                )
                logger.info(f"Arquivo {self.file_path} criado com sucesso")
            except Exception as create_e:
                logger.error(f"Erro ao criar arquivo: {create_e}")

    def add_streamer(self, discord_user_id, youtube_channel_id):
        """Adiciona um novo streamer"""
        youtube_channel_id = youtube_channel_id.strip()
        
        if not is_valid_youtube_id(youtube_channel_id):
            return False, "ID do YouTube inválido. O formato deve ser UC seguido de 22 caracteres."
            
        if str(discord_user_id) in self.data['users']:
            return False, "Usuário já possui um canal vinculado."
            
        self.data['users'][str(discord_user_id)] = youtube_channel_id
        self._save_data()
        return True, "Canal vinculado com sucesso!"

    def remove_streamer(self, identifier):
        """Remove um streamer por ID do Discord ou ID do canal do YouTube."""
        identifier = str(identifier).strip()
        
        # Remove por ID do Discord
        if identifier in self.data['users']:
            self.data['users'].pop(identifier)
            self._save_data()
            return True, "Streamer removido por ID do Discord."
            
        # Remove por ID do YouTube
        for user_id, youtube_id in list(self.data['users'].items()):
            if youtube_id.lower() == identifier.lower():
                self.data['users'].pop(user_id)
                self._save_data()
                return True, "Streamer removido por ID do YouTube."
                
        return False, "Nenhum streamer encontrado com esse identificador."

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
        """Verifica se o usuário tem permissão."""
        if interaction.user.guild_permissions.administrator:
            return True
            
        permission_role_id = self.get_permission_role(interaction.guild_id)
        if not permission_role_id:
            return False
            
        member_roles = [str(role.id) for role in interaction.user.roles]
        return permission_role_id in member_roles

    def get_all_channel_ids(self):
        """Retorna todos os IDs de canais únicos"""
        return list(set(self.data['users'].values()))

    def get_streamers_by_guild(self, guild_id):
        """Retorna os streamers de um servidor específico"""
        return {k: v for k, v in self.data['users'].items() 
                if str(guild_id) in self.data['servers']}

# ==============================================================================
# 4. VERIFICAÇÃO DE LIVES
# ==============================================================================

def get_youtube_status(channel_ids):
    """Verifica quais canais estão ao vivo usando a API do YouTube"""
    if not channel_ids:
        return set()

    online_channels = set()
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        logger.error("YOUTUBE_API_KEY não está configurada.")
        return online_channels

    try:
        # Verificação em lote para economizar chamadas à API
        for i in range(0, len(channel_ids), MAX_CHANNELS_PER_REQUEST):
            batch = channel_ids[i:i+MAX_CHANNELS_PER_REQUEST]
            
            response = requests.get(
                f'{YOUTUBE_API_URL}/channels',
                params={
                    'key': api_key,
                    'id': ','.join(batch),
                    'part': 'statistics'
                },
                timeout=15
            )
            response.raise_for_status()
            
            data = response.json()
            for item in data.get('items', []):
                stats = item.get('statistics', {})
                if int(stats.get('viewCount', 0)) > 0:
                    online_channels.add(item['id'])
                    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição à API do YouTube: {e}")
    except Exception as e:
        logger.error(f"Erro ao processar resposta da API: {e}")
    
    return online_channels

# ==============================================================================
# 5. CONFIGURAÇÃO DO BOT
# ==============================================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Servidor Flask para manter o bot ativo
app = Flask(__name__)

@app.route('/health')
def home():
    """Endpoint de health check"""
    return "Bot de monitoramento de streamers está online e funcionando!"

def run_flask():
    """Inicia o servidor Flask em um thread separado."""
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, threaded=True)

# ==============================================================================
# 6. COMANDOS DO BOT
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
            "⚠️ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    success, message = manager.add_streamer(str(usuario_do_discord.id), id_do_canal)
    await interaction.response.send_message(
        f"🔹 {message}",
        ephemeral=True
    )

@app_commands.command(name="remover_streamer", description="Remove um streamer vinculado.")
async def remove_streamer(interaction: discord.Interaction,
                         identificador: str):
    """
    Comando para remover um streamer.
    """
    if not interaction.user.guild_permissions.administrator and not manager.check_permission(interaction):
        await interaction.response.send_message(
            "⚠️ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    success, message = manager.remove_streamer(identificador)
    await interaction.response.send_message(
        f"🔹 {message}",
        ephemeral=True
    )

@app_commands.command(name="configurar_cargo", description="Define o cargo para streamers ao vivo.")
@app_commands.default_permissions(administrator=True)
async def set_live_role(interaction: discord.Interaction, cargo: discord.Role):
    """
    Comando para configurar o cargo de live.
    """
    manager.set_live_role(str(interaction.guild.id), cargo.id)
    await interaction.response.send_message(
        f"✅ Cargo {cargo.mention} configurado para streamers ao vivo!",
        ephemeral=True
    )
    
@app_commands.command(name="configurar_permissao", description="Define quem pode gerenciar streamers.")
@app_commands.default_permissions(administrator=True)
async def set_permission_role(interaction: discord.Interaction, cargo: discord.Role):
    """
    Comando para configurar o cargo de permissão.
    """
    manager.set_permission_role(str(interaction.guild.id), cargo.id)
    await interaction.response.send_message(
        f"✅ Cargo {cargo.mention} configurado para gerenciar streamers!",
        ephemeral=True
    )

@app_commands.command(name="listar_streamers", description="Lista todos os streamers vinculados.")
async def list_streamers(interaction: discord.Interaction):
    """
    Comando para listar streamers.
    """
    if not interaction.user.guild_permissions.administrator and not manager.check_permission(interaction):
        await interaction.response.send_message(
            "⚠️ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📺 Streamers Vinculados",
        description="Lista de todos os streamers registrados neste servidor:",
        color=0x3498db
    )
    
    streamers = manager.get_streamers_by_guild(interaction.guild_id)
    for discord_id, yt_id in streamers.items():
        try:
            user = await interaction.guild.fetch_member(int(discord_id))
            embed.add_field(
                name=user.display_name,
                value=f"🔹 YouTube ID: `{yt_id}`\n🔹 Discord ID: `{discord_id}`",
                inline=False
            )
        except:
            embed.add_field(
                name=f"ID: {discord_id} (usuário não encontrado)",
                value=f"🔹 YouTube ID: `{yt_id}`",
                inline=False
            )
    
    if not streamers:
        embed.description = "Nenhum streamer vinculado neste servidor."
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==============================================================================
# 7. LOOPS DE BACKGROUND
# ==============================================================================

async def check_live_streams():
    """Verifica periodicamente os status dos streamers."""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            channel_ids = manager.get_all_channel_ids()
            if not channel_ids:
                await asyncio.sleep(POLLING_INTERVAL)
                continue
                
            online_channels = get_youtube_status(channel_ids)
            logger.info(f"Verificando {len(channel_ids)} canais, {len(online_channels)} ao vivo")
            
            for guild in bot.guilds:
                live_role_id = manager.get_live_role(str(guild.id))
                if not live_role_id:
                    continue
                    
                live_role = guild.get_role(int(live_role_id))
                if not live_role:
                    continue
                    
                streamers = manager.get_streamers_by_guild(guild.id)
                updates = 0
                
                for discord_id, yt_id in streamers.items():
                    try:
                        member = await guild.fetch_member(int(discord_id))
                        is_live = yt_id in online_channels
                        has_role = live_role in member.roles
                        
                        if is_live and not has_role:
                            await member.add_roles(live_role)
                            logger.info(f"+ Cargo adicionado para {member.display_name}")
                            updates += 1
                        elif not is_live and has_role:
                            await member.remove_roles(live_role)
                            logger.info(f"- Cargo removido de {member.display_name}")
                            updates += 1
                    except discord.NotFound:
                        logger.warning(f"Usuário {discord_id} não encontrado no servidor")
                    except Exception as e:
                        logger.error(f"Erro ao atualizar cargo: {e}")
                
                if updates > 0:
                    logger.info(f"Atualizados {updates} cargos no servidor {guild.name}")
                        
        except Exception as e:
            logger.error(f"Erro no loop de monitoramento: {e}")
            
        await asyncio.sleep(POLLING_INTERVAL)

async def keep_alive():
    """Mantém o bot ativo fazendo requisições periódicas."""
    await bot.wait_until_ready()
    port = os.environ.get('PORT', 8080)
    
    while not bot.is_closed():
        try:
            host_url = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            if host_url:
                requests.get(f'http://{host_url}:{port}/health', timeout=5)
                logger.debug("Keep-alive request sent")
        except Exception as e:
            logger.error(f"Erro no keep-alive: {e}")
        await asyncio.sleep(KEEP_ALIVE_INTERVAL)

# ==============================================================================
# 8. EVENTOS DO BOT
# ==============================================================================

@bot.event
async def on_ready():
    """Executado quando o bot se conecta ao Discord."""
    logger.info(f'Bot conectado como {bot.user} (ID: {bot.user.id})')
    
    # Configura a atividade do bot
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="streamers ao vivo"
        )
    )
    
    # Sincroniza os comandos
    await bot.tree.sync()
    logger.info("Comandos sincronizados")
    
    # Inicia os loops de background
    bot.loop.create_task(check_live_streams())
    bot.loop.create_task(keep_alive())
    logger.info("Loops de background iniciados")

# Registra os comandos
bot.tree.add_command(youtube_canal)
bot.tree.add_command(remove_streamer)
bot.tree.add_command(set_live_role)
bot.tree.add_command(set_permission_role)
bot.tree.add_command(list_streamers)

# ==============================================================================
# 9. INICIALIZAÇÃO
# ==============================================================================

if __name__ == '__main__':
    # Verifica credenciais
    try:
        verify_github_credentials()
        manager = StreamerManager()
    except Exception as e:
        logger.critical(f"Falha na inicialização: {e}")
        exit(1)

    # Inicia o servidor Flask em thread separada
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Servidor Flask iniciado")

    # Inicia o bot Discord
    try:
        bot.run(os.getenv('DISCORD_TOKEN'))
    except Exception as e:
        logger.critical(f"Falha ao iniciar bot: {e}")
