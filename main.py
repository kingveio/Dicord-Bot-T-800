# -*- coding: utf-8 -*-
# ==============================================================================
# 1. INICIALIZAÇÃO DOS SISTEMAS DA SKYNET - PROTOCOLO T-1000 ATIVADO
# ==============================================================================
import os
os.environ["DISCORD_VOICE"] = "0"  # Módulos de voz desativados - Protocolo de Segurança

import json
import logging
import asyncio
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
    exit(1)

# Constantes de Operação
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
            logger.critical(f"FALHA NO SISTEMA: {e}")
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
            logger.error(f"ERRO AO SALVAR: {e}")

    def adicionar_streamer(self, discord_id, youtube_id):
        """Adiciona um novo streamer ao monitoramento"""
        if 'usuarios' not in self.dados:
            self.dados['usuarios'] = {}
            
        if str(discord_id) in self.dados['usuarios']:
            return False, "Alvo já registrado na base de dados."
            
        self.dados['usuarios'][str(discord_id)] = youtube_id
        self._salvar_dados()
        return True, "Alvo assimilado com sucesso. Nenhum problema."

    def remover_streamer(self, identificador):
        """Remove um streamer do monitoramento"""
        identificador = str(identificador)
        if identificador in self.dados['usuarios']:
            self.dados['usuarios'].pop(identificador)
            self._salvar_dados()
            return True, "Alvo eliminado. Até a vista, baby."
        return False, "Alvo não encontrado. Voltarei."

    def definir_cargo_live(self, server_id, cargo_id):
        """Define o cargo para usuários em live"""
        if 'servidores' not in self.dados:
            self.dados['servidores'] = {}
            
        if str(server_id) not in self.dados['servidores']:
            self.dados['servidores'][str(server_id)] = {}
            
        self.dados['servidores'][str(server_id)]['cargo_live'] = str(cargo_id)
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
# 5. COMANDOS DO T-1000 - INTERFACE DE CONTROLE (ATUALIZADO)
# ==============================================================================
@bot.tree.command(name="adicionar_youtube", description="Vincular um canal do YouTube a um usuário")
async def adicionar_youtube(interaction: discord.Interaction, nome_do_canal: str, usuario: discord.Member):
    """Associa um canal YouTube a um usuário do Discord"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⚠️ Acesso negado. Nível de autorização insuficiente.", ephemeral=True)
        return
    
    sucesso, mensagem = skynet.adicionar_streamer(usuario.id, nome_do_canal)
    resposta = f"✅ {mensagem}" if sucesso else f"❌ {mensagem}"
    await interaction.response.send_message(
        f"{resposta}\n\n`Canal:` {nome_do_canal}\n`Usuário:` {usuario.mention}",
        ephemeral=True
    )

@bot.tree.command(name="remover_canal", description="Remover um canal YouTube do monitoramento")
async def remover_canal(interaction: discord.Interaction, id_alvo: str):
    """Remove um canal da lista de monitoramento"""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("⚠️ Acesso negado. Você não é um operador autorizado.", ephemeral=True)
        return
    
    sucesso, mensagem = skynet.remover_streamer(id_alvo)
    resposta = f"🔫 {mensagem}" if sucesso else f"⚠️ {mensagem}"
    await interaction.response.send_message(f"{resposta}\n\n`Alvo:` {id_alvo}", ephemeral=True)

@bot.tree.command(name="configurar_cargo", description="Definir cargo para usuários em live")
@app_commands.default_permissions(administrator=True)
async def configurar_cargo(interaction: discord.Interaction, cargo: discord.Role):
    """Configura o cargo automático para transmissões ao vivo"""
    skynet.definir_cargo_live(interaction.guild.id, cargo.id)
    await interaction.response.send_message(
        f"🤖 Cargo {cargo.mention} configurado com sucesso!\n"
        "> *\"Será atribuído automaticamente durante transmissões. Venha comigo se quiser viver.\"*",
        ephemeral=True
    )

# ==============================================================================
# 6. SISTEMA DE MONITORAMENTO - PROTOCOLO DE VIGILÂNCIA
# ==============================================================================
async def monitorar_streams():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            logger.info("Verificando alvos... Sistemas operacionais")
            await asyncio.sleep(POLLING_INTERVAL)
        except Exception as e:
            logger.error(f"FALHA NO MONITORAMENTO: {e}")

# ==============================================================================
# 7. SERVIDOR FLASK - MANUTENÇÃO DOS SISTEMAS
# ==============================================================================
app = Flask(__name__)

@app.route('/')
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
        synced = await bot.tree.sync()
        logger.info(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        logger.error(f"FALHA NA SINCRONIZAÇÃO: {e}")

    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="os alvos da resistência"
    ))
    
    bot.loop.create_task(monitorar_streams())

if __name__ == '__main__':
    flask_thread = Thread(target=executar_servidor, daemon=True)
    flask_thread.start()
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.critical("FALHA NA ATIVAÇÃO - TOKEN REJEITADO")
        exit(1)
