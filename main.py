# -*- coding: utf-8 -*-
# ==============================================================================
# 1. INICIALIZAÇÃO DOS SISTEMAS - SKYNET T-1000
# ==============================================================================
import os
import json
import logging
import asyncio
import requests
from threading import Thread
from github import Github
import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask, jsonify
import traceback

# ==============================================================================
# 2. CONFIGURAÇÃO INICIAL - LOGS E VARIÁVEIS DE AMBIENTE
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - T-1000 - %(levelname)s - %(message)s'
)
logger = logging.getLogger('T-1000')

YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    logger.critical("❌ CHAVE DA API DO YOUTUBE NÃO ENCONTRADA")
    exit(1)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN or not DISCORD_TOKEN.startswith('MT'):
    logger.critical("❌ TOKEN INVÁLIDO - Verifique DISCORD_TOKEN no Render")
    exit(1)

# Constantes
YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300  # Verificação a cada 5 minutos
UPTIME_CHECK_INTERVAL = 60  # UptimeRobot verifica a cada 1 minuto

# ==============================================================================
# 3. BANCO DE DADOS (GITHUB)
# ==============================================================================
class GerenciadorSkynet:
    def __init__(self):
        try:
            self.github = Github(os.getenv('GITHUB_TOKEN'))
            self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
            self.arquivo = 'streamers.json'
            self.dados = self._carregar_ou_criar_arquivo()
            logger.info("✅ Banco de dados inicializado")
        except Exception as e:
            logger.critical(f"❌ FALHA NO BANCO DE DADOS: {traceback.format_exc()}")
            raise

    def _carregar_ou_criar_arquivo(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            dados = json.loads(conteudo.decoded_content.decode())
            return {'usuarios': dados.get('usuarios', {}), 'servidores': dados.get('servidores', {})}
        except Exception:
            logger.warning("⚠️ Arquivo não encontrado, criando novo...")
            return {'usuarios': {}, 'servidores': {}}

    def _salvar_dados(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            self.repo.update_file(
                conteudo.path,
                "Atualização automática",
                json.dumps(self.dados, indent=2),
                conteudo.sha
            )
        except Exception as e:
            logger.error(f"❌ ERRO AO SALVAR: {traceback.format_exc()}")

    def adicionar_streamer(self, discord_id, youtube_id):
        try:
            if str(discord_id) in self.dados['usuarios']:
                return False, "❌ Alvo já registrado."
            self.dados['usuarios'][str(discord_id)] = youtube_id
            self._salvar_dados()
            return True, "✅ Alvo assimilado. Nenhum problema."
        except Exception:
            return False, "❌ Falha na assimilação."

    def remover_streamer(self, identificador):
        try:
            identificador = str(identificador)
            if identificador in self.dados['usuarios']:
                self.dados['usuarios'].pop(identificador)
                self._salvar_dados()
                return True, "🔫 Alvo eliminado. Até a vista, baby."
            return False, "⚠️ Alvo não encontrado."
        except Exception:
            return False, "❌ Falha na eliminação."

    def definir_cargo_live(self, server_id, cargo_id):
        try:
            if str(server_id) not in self.dados['servidores']:
                self.dados['servidores'][str(server_id)] = {}
            self.dados['servidores'][str(server_id)]['cargo_live'] = str(cargo_id)
            self._salvar_dados()
            return "🤖 Cargo configurado. Venha comigo se quiser viver."
        except Exception:
            return "❌ Falha na configuração."

# ==============================================================================
# 4. CONFIGURAÇÃO DO BOT
# ==============================================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

skynet = GerenciadorSkynet()

# ==============================================================================
# 5. COMANDOS SLASH (/)
# ==============================================================================
@bot.tree.command(name="adicionar_youtube", description="Vincula um canal YouTube a um usuário")
async def adicionar_youtube(interaction: discord.Interaction, nome_do_canal: str, usuario: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⚠️ Acesso negado.", ephemeral=True)
        return
    sucesso, mensagem = skynet.adicionar_streamer(usuario.id, nome_do_canal)
    await interaction.response.send_message(f"{mensagem}\n`Canal:` {nome_do_canal}\n`Usuário:` {usuario.mention}", ephemeral=True)

@bot.tree.command(name="remover_canal", description="Remove um canal do monitoramento")
async def remover_canal(interaction: discord.Interaction, id_alvo: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⚠️ Acesso negado.", ephemeral=True)
        return
    sucesso, mensagem = skynet.remover_streamer(id_alvo)
    await interaction.response.send_message(f"{mensagem}\n`Alvo:` {id_alvo}", ephemeral=True)

@bot.tree.command(name="configurar_cargo", description="Define o cargo para streams ao vivo")
@app_commands.default_permissions(administrator=True)
async def configurar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    mensagem = skynet.definir_cargo_live(interaction.guild.id, cargo.id)
    await interaction.response.send_message(f"{mensagem}\n`Cargo:` {cargo.mention}", ephemeral=True)

# ==============================================================================
# 7. MONITORAMENTO DE LIVES (Lógica Principal)
# ==============================================================================

async def get_channel_id_from_username(username):
    """Obtém o ID do canal do YouTube a partir do nome de usuário."""
    try:
        params = {
            'part': 'id',
            'forUsername': username,
            'key': YOUTUBE_API_KEY
        }
        response = requests.get(f'{YOUTUBE_API_URL}/channels', params=params)
        response.raise_for_status()
        data = response.json()
        if 'items' in data and data['items']:
            return data['items'][0]['id']
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ ERRO AO OBTER ID DO CANAL: {e}")
    except Exception as e:
        logger.error(f"❌ ERRO DESCONHECIDO NO GET_CHANNEL_ID: {e}")
    return None

async def verificar_live(channel_id):
    """Verifica se um canal do YouTube está transmitindo ao vivo usando o ID do canal."""
    try:
        params = {
            'part': 'snippet,liveStreamingDetails',
            'channelId': channel_id,
            'type': 'video',
            'eventType': 'live',
            'key': YOUTUBE_API_KEY
        }
        
        response = requests.get(f'{YOUTUBE_API_URL}/search', params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'items' in data and data['items']:
            # A API retorna um video de live, pegue o videoId do primeiro item
            video_id = data['items'][0]['id']['videoId']
            return True, f"https://www.youtube.com/watch?v={video_id}"
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ ERRO AO ACESSAR API DO YOUTUBE: {e}")
    except Exception as e:
        logger.error(f"❌ ERRO DESCONHECIDO NO MONITORAMENTO: {e}")

    return False, None

@tasks.loop(seconds=POLLING_INTERVAL)
async def monitorar_streamers():
    """Tarefa que verifica se os streamers estão ao vivo e atualiza o cargo."""
    logger.info("🤖 Iniciando verificação de lives...")
    streamers = skynet.dados['usuarios']
    
    for discord_id, youtube_username in streamers.items():
        # Obtém o ID do canal a partir do nome de usuário
        youtube_channel_id = await get_channel_id_from_username(youtube_username)
        if not youtube_channel_id:
            logger.warning(f"⚠️ Não foi possível obter o ID do canal para o usuário {youtube_username}.")
            continue
            
        esta_ao_vivo, live_url = await verificar_live(youtube_channel_id)
        
        for guild in bot.guilds:
            # Encontra o membro no servidor específico
            membro = guild.get_member(int(discord_id))
            if not membro:
                continue

            if str(guild.id) in skynet.dados['servidores']:
                cargo_id = skynet.dados['servidores'][str(guild.id)].get('cargo_live')
                if cargo_id:
                    cargo_live = guild.get_role(int(cargo_id))
                    if cargo_live:
                        if esta_ao_vivo:
                            if cargo_live not in membro.roles:
                                try:
                                    await membro.add_roles(cargo_live, reason="Streamer ao vivo no YouTube")
                                    logger.info(f"✅ Cargo de live adicionado para {membro.name} em {guild.name}")
                                except discord.Forbidden:
                                    logger.error(f"❌ Sem permissão para adicionar cargo para {membro.name}")
                        elif cargo_live in membro.roles:
                            try:
                                await membro.remove_roles(cargo_live, reason="Streamer encerrou a live")
                                logger.info(f"✅ Cargo de live removido de {membro.name} em {guild.name}")
                            except discord.Forbidden:
                                logger.error(f"❌ Sem permissão para remover cargo de {membro.name}")
    logger.info("✅ Verificação de lives concluída.")

# ==============================================================================
# 8. INICIALIZAÇÃO DO BOT
# ==============================================================================
@bot.event
async def on_ready():
    logger.info(f"✅ Bot online em {len(bot.guilds)} servidores")
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="Buscando alvos da resistência"
    ))
    
    monitorar_streamers.start()
    
# ==============================================================================
# 9. SERVIDOR FLASK (PARA UPTIMEROBOT)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "🟢 Bot Online | Skynet Ativo", 200

@app.route('/health')
def health_check():
    try:
        # Verifica se o bot está conectado
        if not bot.is_ready():
            return jsonify({"status": "🔴 Bot não conectado"}), 503
        
        # Verifica conexão com GitHub
        skynet.repo.get_contents('streamers.json')
        
        return jsonify({"status": "🟢 Tudo operacional"}), 200
    except Exception:
        return jsonify({"status": "🔴 Falha no sistema"}), 500

def executar_servidor():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

if __name__ == '__main__':
    Thread(target=executar_servidor, daemon=True).start()
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"❌ FALHA: {traceback.format_exc()}")
        exit(1)
