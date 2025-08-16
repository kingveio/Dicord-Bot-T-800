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
    logger.critical("Verifique o token e tente novamente")
    exit(1)

# Constantes de Operação
YOUTUBE_API_URL = 'https://www.googleapis.com/youtube/v3'
POLLING_INTERVAL = 300  # 5 minutos entre verificações
KEEP_ALIVE_INTERVAL = 240  # 4 minutos entre keep-alives

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
            logger.critical(f"FALHA NO SISTEMA: {e}")
            raise

    def _carregar_ou_criar_arquivo(self):
        try:
            conteudo = self.repo.get_contents(self.arquivo)
            return json.loads(conteudo.decoded_content.decode())
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
            logger.info("Banco de dados atualizado")
        except Exception as e:
            logger.error(f"ERRO: {e}")

    def adicionar_streamer(self, discord_id, youtube_id):
        if str(discord_id) in self.dados['usuarios']:
            return False, "Alvo já registrado na base de dados."
        self.dados['usuarios'][str(discord_id)] = youtube_id
        self._salvar_dados()
        return True, "Alvo assimilado com sucesso. Nenhum problema."

    def remover_streamer(self, identificador):
        identificador = str(identificador)
        if identificador in self.dados['usuarios']:
            self.dados['usuarios'].pop(identificador)
            self._salvar_dados()
            return True, "Alvo eliminado. Até a vista, baby."
        return False, "Alvo não encontrado. Voltarei."

    def definir_cargo_live(self, server_id, cargo_id):
        self.dados['servidores'][str(server_id)] = {'cargo_live': str(cargo_id)}
        self._salvar_dados()
        return "Cargo configurado. Será atribuído automaticamente."

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
@bot.tree.command(name="assimilar", description="Assimilar um canal à Skynet")
async def assimilar(interaction: discord.Interaction, id_canal: str, usuario: discord.Member):
    """Assimilar um canal do YouTube para monitoramento"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Acesso negado. Nível de autorização insuficiente.",
            ephemeral=True
        )
        return
    
    sucesso, mensagem = skynet.adicionar_streamer(usuario.id, id_canal)
    resposta = f"✅ {mensagem}" if sucesso else f"⚠️ {mensagem}"
    await interaction.response.send_message(resposta, ephemeral=True)

@bot.tree.command(name="eliminar", description="Eliminar um alvo da Skynet")
async def eliminar(interaction: discord.Interaction, id_alvo: str):
    """Remover um streamer do monitoramento"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Acesso negado. Você não tem permissão para isso.",
            ephemeral=True
        )
        return
    
    sucesso, mensagem = skynet.remover_streamer(id_alvo)
    resposta = f"✅ {mensagem}" if sucesso else f"⚠️ {mensagem}"
    await interaction.response.send_message(resposta, ephemeral=True)

@bot.tree.command(name="configurar_cargo", description="Definir cargo para streamers ao vivo")
@app_commands.default_permissions(administrator=True)
async def configurar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    """Configurar o cargo que será atribuído durante streams"""
    mensagem = skynet.definir_cargo_live(interaction.guild.id, cargo.id)
    await interaction.response.send_message(
        f"✅ {mensagem} Venha comigo se quiser viver.",
        ephemeral=True
    )

# ==============================================================================
# 6. SISTEMA DE MONITORAMENTO - PROTOCOLO DE VIGILÂNCIA
# ==============================================================================
async def monitorar_streams():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            # Lógica de verificação de streams aqui
            logger.info("Verificando alvos... Sistemas operacionais")
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception as e:
            logger.error(f"FALHA NO MONITORAMENTO: {e}")

# ==============================================================================
# 7. SERVIDOR FLASK - MANUTENÇÃO DOS SISTEMAS
# ==============================================================================
app = Flask(__name__)

@app.route('/status')
def status():
    return "Sistemas operacionais. Nenhum problema.", 200

def executar_servidor():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 8080)))

# ==============================================================================
# 8. ATIVAÇÃO DO T-1000 - SEQUÊNCIA DE INICIALIZAÇÃO
# ==============================================================================
@bot.event
async def on_ready():
    logger.info(f"T-1000 online em {len(bot.guilds)} servidores. Estarei de volta.")
    
    try:
        await bot.tree.sync()
        logger.info("Comandos sincronizados com sucesso!")
    except Exception as e:
        logger.error(f"FALHA NA SINCRONIZAÇÃO: {e}")

    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="os alvos da resistência"
    ))
    
    bot.loop.create_task(monitorar_streams())

if __name__ == '__main__':
    # Iniciar servidor Flask em segundo plano
    Thread(target=executar_servidor, daemon=True).start()
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.critical("FALHA NA ATIVAÇÃO - TOKEN REJEITADO")
        logger.critical("Skynet não pode completar a inicialização")
        exit(1)
