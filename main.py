# -*- coding: utf-8 -*-
# ==============================================================================
# 1. INICIALIZAÇÃO DOS SISTEMAS DA SKYNET - PROTOCOLO T-1000 ATIVADO
# ==============================================================================
import os
os.environ["DISCORD_VOICE"] = "0"  # Módulos de voz desativados - Protocolo de Segurança

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
# 2. CONFIGURAÇÃO DOS SISTEMAS PRINCIPAIS - MAINFRAME SKYNET
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - T-1000 - %(levelname)s - %(message)s'
)
logger = logging.getLogger('T-1000')

# Verificação do Token de Ativação
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN or not DISCORD_TOKEN.startswith('MT'):
    logger.critical("❌ FALHA NA ATIVAÇÃO - TOKEN INVÁLIDO")
    logger.critical("Skynet não pode ser inicializada")
    exit(1)

# Constantes de Operação
YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300  # 5 minutos entre verificações

# ==============================================================================
# 3. BANCO DE DADOS DA SKYNET - GERENCIADOR DE STREAMERS
# ==============================================================================
class GerenciadorSkynet:
    def __init__(self):
        try:
            self.github = Github(os.getenv('GITHUB_TOKEN'))
            self.repo = self.github.get_repo(os.getenv('GITHUB_REPO'))
            self.arquivo = 'streamers.json'
            self.dados = self._carregar_ou_criar_arquivo()
            logger.info("Banco de dados da Skynet inicializado")
        except Exception as e:
            logger.critical(f"FALHA NO SISTEMA: {traceback.format_exc()}")
            raise

    def _carregar_ou_criar_arquivo(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            dados = json.loads(conteudo.decoded_content.decode())
            # Garante a estrutura correta
            if 'usuarios' not in dados:
                dados['usuarios'] = {}
            if 'servidores' not in dados:
                dados['servidores'] = {}
            return dados
        except Exception:
            logger.info("Criando novo banco de dados - Protocolo de Inicialização")
            return {'usuarios': {}, 'servidores': {}}

    def _salvar_dados(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            self.repo.update_file(
                conteudo.path,
                "Atualização automática - Skynet",
                json.dumps(self.dados, indent=2),
                conteudo.sha
            )
        except Exception as e:
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
# 4. CONFIGURAÇÃO DO T-1000 - UNIDADE PRINCIPAL
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
# 5. COMANDOS DO T-1000 - INTERFACE DE CONTROLE
# ==============================================================================
@bot.tree.command(name="adicionar_youtube", description="Vincular um canal do YouTube a um usuário")
async def adicionar_youtube(interaction: discord.Interaction, nome_do_canal: str, usuario: discord.Member):
    """Associa um canal YouTube a um usuário do Discord"""
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⚠️ Acesso negado. Nível de autorização insuficiente.", ephemeral=True)
            return
        
        sucesso, mensagem = skynet.adicionar_streamer(usuario.id, nome_do_canal)
        resposta = f"✅ {mensagem}" if sucesso else f"❌ {mensagem}"
        await interaction.response.send_message(
            f"{resposta}\n\n`Canal:` {nome_do_canal}\n`Usuário:` {usuario.mention}",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f"ERRO: {traceback.format_exc()}")
        await interaction.response.send_message("⚠️ Falha ao processar comando. Tente novamente.", ephemeral=True)

@bot.tree.command(name="remover_canal", description="Remover um canal YouTube do monitoramento")
async def remover_canal(interaction: discord.Interaction, id_alvo: str):
    """Remove um canal da lista de monitoramento"""
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⚠️ Acesso negado. Você não é um operador autorizado.", ephemeral=True)
            return
        
        sucesso, mensagem = skynet.remover_streamer(id_alvo)
        resposta = f"🔫 {mensagem}" if sucesso else f"⚠️ {mensagem}"
        await interaction.response.send_message(f"{resposta}\n\n`Alvo:` {id_alvo}", ephemeral=True)
    except Exception as e:
        logger.error(f"ERRO: {traceback.format_exc()}")
        await interaction.response.send_message("⚠️ Falha ao processar comando. Tente novamente.", ephemeral=True)

@bot.tree.command(name="configurar_cargo", description="Definir cargo para usuários em live")
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
# 6. SISTEMA DE MONITORAMENTO - PROTOCOLO DE VIGILÂNCIA
# ==============================================================================
async def monitorar_streams():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            logger.info("Verificando alvos... Sistemas operacionais")
            # Implemente aqui a lógica de verificação de streams
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception as e:
            logger.error(f"FALHA NO MONITORAMENTO: {traceback.format_exc()}")

# ==============================================================================
# 7. SERVIDOR FLASK - MANUTENÇÃO DOS SISTEMAS
# ==============================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Sistemas da Skynet operacionais. Nenhum problema.", 200

@app.route('/health')
def health_check():
    return "T-1000 operacional. Sistemas normais.", 200

def executar_servidor():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ==============================================================================
# 8. ATIVAÇÃO DO T-1000 - SEQUÊNCIA DE INICIALIZAÇÃO
# ==============================================================================
@bot.event
async def on_ready():
    try:
        logger.info(f"T-1000 online em {len(bot.guilds)} servidores. Estarei de volta.")
        
        # Teste de conexão com APIs externas
        try:
            requests.get(YOUTUBE_API_URL, timeout=5)
            logger.info("Conexão com YouTube API: OK")
        except Exception as e:
            logger.error(f"FALHA NA CONEXÃO COM YOUTUBE: {traceback.format_exc()}")
        
        # Sincronização de comandos
        synced = await bot.tree.sync()
        logger.info(f"{len(synced)} comandos sincronizados")

        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="os alvos da resistência"
        ))
        
        bot.loop.create_task(monitorar_streams())
    except Exception as e:
        logger.critical(f"FALHA CRÍTICA: {traceback.format_exc()}")

if __name__ == '__main__':
    try:
        # Iniciar servidor Flask em segundo plano
        flask_thread = Thread(target=executar_servidor, daemon=True)
        flask_thread.start()
        
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.critical("FALHA NA ATIVAÇÃO - TOKEN REJEITADO")
        exit(1)
    except Exception as e:
        logger.critical(f"FALHA NA INICIALIZAÇÃO: {traceback.format_exc()}")
        exit(1)
