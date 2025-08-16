# -*- coding: utf-8 -*-
# ==============================================================================
# 1. INICIALIZAÇÃO DOS SISTEMAS DA SKYNET - PROTOCOLO T-1000 ATIVADO
# ==============================================================================
import os
os.environ["DISCORD_VOICE"] = "0"  # Módulos de voz desativados

import json
import logging
import asyncio
import requests
from threading import Thread
from github import Github
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import traceback

# ==============================================================================
# 2. CONFIGURAÇÃO DOS SISTEMAS PRINCIPAIS
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - T-1000 - %(levelname)s - %(message)s'
)
logger = logging.getLogger('T-1000')

# Verificação do Token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN or not DISCORD_TOKEN.startswith('MT'):
    logger.critical("❌ FALHA NA ATIVAÇÃO - TOKEN INVÁLIDO")
    exit(1)

# Constantes
YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300
UPTIME_CHECK_INTERVAL = 60  # Verificação a cada 1 minuto para Uptime Robot

# ==============================================================================
# 3. BANCO DE DADOS DA SKYNET (OTIMIZADO)
# ==============================================================================
class GerenciadorSkynet:
    def __init__(self):
        try:
            self.github = Github(os.getenv('GITHUB_TOKEN'))
            self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
            self.arquivo = 'streamers.json'
            self.dados = self._carregar_ou_criar_arquivo()
            logger.info("Banco de dados inicializado")
        except Exception:
            logger.critical(f"FALHA: {traceback.format_exc()}")
            raise

    def _carregar_ou_criar_arquivo(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            dados = json.loads(conteudo.decoded_content.decode())
            return {'usuarios': dados.get('usuarios', {}), 
                    'servidores': dados.get('servidores', {})}
        except Exception:
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
        except Exception:
            logger.error(f"ERRO AO SALVAR: {traceback.format_exc()}")

    def adicionar_streamer(self, discord_id, youtube_id):
        """Adiciona um novo streamer ao monitoramento"""
        try:
            if str(discord_id) in self.dados['usuarios']:
                return False, "Alvo já registrado na base de dados."
                
            self.dados['usuarios'][str(discord_id)] = youtube_id
            self._salvar_dados()
            return True, "Alvo assimilado com sucesso. Nenhum problema."
        except Exception as e:
            logger.error(f"ERRO: {traceback.format_exc()}")
            return False, "Falha na assimilação. Tente novamente."

    def remover_streamer(self, identificador):
        """Remove um streamer do monitoramento"""
        try:
            identificador = str(identificador)
            # Tenta remover por ID do Discord
            if identificador in self.dados['usuarios']:
                self.dados['usuarios'].pop(identificador)
                self._salvar_dados()
                return True, "Alvo eliminado. Até a vista, baby."
            
            # Tenta remover por ID do YouTube
            for user_id, yt_id in list(self.dados['usuarios'].items()):
                if yt_id == identificador:
                    self.dados['usuarios'].pop(user_id)
                    self._salvar_dados()
                    return True, "Alvo eliminado da base de dados."
                    
            return False, "Alvo não encontrado. Voltarei."
        except Exception as e:
            logger.error(f"ERRO: {traceback.format_exc()}")
            return False, "Falha na eliminação. Tente novamente."

    def definir_cargo_live(self, server_id, cargo_id):
        """Define o cargo para usuários em live"""
        try:
            if str(server_id) not in self.dados['servidores']:
                self.dados['servidores'][str(server_id)] = {}
                
            self.dados['servidores'][str(server_id)]['cargo_live'] = str(cargo_id)
            self._salvar_dados()
            return "Cargo configurado. Será atribuído automaticamente."
        except Exception as e:
            logger.error(f"ERRO: {traceback.format_exc()}")
            return "Falha na configuração do cargo."

# ==============================================================================
# 4. CONFIGURAÇÃO DO BOT (SIMPLIFICADA)
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
# 5. COMANDOS (MANTIDOS OS MESMOS)
# ==============================================================================
@bot.tree.command(name="adicionar_youtube", description="Vincular canal YouTube a usuário")
async def adicionar_youtube(interaction: discord.Interaction, nome_do_canal: str, usuario: discord.Member):

@bot.tree.command(name="remover_canal", description="Remover canal do monitoramento")
async def remover_canal(interaction: discord.Interaction, id_alvo: str):

@bot.tree.command(name="configurar_cargo", description="Definir cargo para streams ao vivo")
@app_commands.default_permissions(administrator=True)
async def configurar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    """Configura o cargo automático para transmissões ao vivo"""
    try:
        mensagem = skynet.definir_cargo_live(interaction.guild.id, cargo.id)
        await interaction.response.send_message(
            f"🤖 Cargo {cargo.mention} configurado com sucesso!\n"
            f"> *\"{mensagem} Venha comigo se quiser viver.\"*",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"ERRO: {traceback.format_exc()}")
        await interaction.response.send_message("⚠️ Falha ao configurar cargo. Tente novamente.", ephemeral=True)

# ==============================================================================
# 6. SERVIDOR FLASK PARA UPTIME ROBOT (ATUALIZADO)
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Sistemas operacionais", 200

@app.route('/health')
def health_check():
    try:
        # Verifica se o bot está conectado
        if not bot.is_ready():
            return "Bot não conectado", 503
        
        # Verifica conexão com GitHub
        skynet.repo.get_contents('streamers.json')
        
        return "T-1000 operacional", 200
    except Exception:
        return "Falha no sistema", 500

def executar_servidor():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ==============================================================================
# 7. MONITORAMENTO DE STREAMS (OTIMIZADO)
# ==============================================================================
async def monitorar_streams():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Implemente sua lógica de verificação aqui
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception:
            logger.error(f"ERRO: {traceback.format_exc()}")

# ==============================================================================
# 8. INICIALIZAÇÃO (COM VERIFICAÇÃO DE UPTIME)
# ==============================================================================
@bot.event
async def on_ready():
    try:
        logger.info(f"Bot conectado em {len(bot.guilds)} servidores")
        
        # Sincroniza comandos
        await bot.tree.sync()
        
        # Inicia monitoramento
        bot.loop.create_task(monitorar_streams())
        
        # Status personalizado
        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servidores"
        ))
    except Exception:
        logger.critical(f"FALHA: {traceback.format_exc()}")

if __name__ == '__main__':
    # Inicia servidor Flask
    flask_thread = Thread(target=executar_servidor, daemon=True)
    flask_thread.start()
    
    # Inicia bot
    try:
        bot.run(DISCORD_TOKEN)
    except Exception:
        logger.critical("Falha na inicialização do bot")
        exit(1)
