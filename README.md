# T-800-YouTube 🤖

Bot do Discord que atualiza cargos quando usuários estão ao vivo no YouTube, com a capacidade de gerenciar permissões de uso.

### ⚙️ Pré-requisitos
Para o funcionamento do bot, são necessários os seguintes itens:
* 🐍 Python 3.11+
* Uma conta no Render (plano gratuito)
* As seguintes variáveis de ambiente devem ser configuradas no seu serviço Render:
    * `DISCORD_TOKEN`: O token do seu bot do Discord.
    * `GITHUB_TOKEN`: Um token de acesso pessoal ao GitHub para permitir que o bot leia e escreva no repositório.
    * `GITHUB_REPO`: O nome do seu repositório onde o arquivo `streamers.json` será armazenado (ex: `seuuser/seurepo`).
    * **`YOUTUBE_API_KEY`**: A chave da API de Dados do YouTube. Você pode obtê-la no Google Cloud Console.

### 🚀 Como Hospedar no Render
O processo para hospedar o bot no Render é o seguinte:
1.  Conecte seu repositório GitHub ao Render.
2.  Defina as variáveis de ambiente mencionadas acima no painel do Render.
3.  O arquivo `render.yaml` já está configurado para o deploy automático.

### 🎮 Comandos do Bot
Os comandos de barra a seguir podem ser usados no Discord:
* `/youtube_canal [id_do_canal] [usuário_do_discord]`: Vincula um canal do YouTube (usando o ID do canal, ex: `UCyQxQ3sKq3...`) a um membro do Discord. Apenas usuários com permissão de administrador ou com o cargo configurado podem usar este comando.
* `/remover_streamer [id]`: Remove um streamer da lista por ID do Discord ou ID do canal do YouTube. Apenas usuários com permissão de administrador ou com o cargo configurado podem usar este comando.
* `/configurar_cargo [cargo]`: Define o cargo que será atribuído aos streamers quando estiverem ao vivo. Este comando é restrito a administradores.
* `/configurar_permissao [cargo]`: Define um cargo específico para que os membros possam usar os comandos `/youtube_canal` e `/remover_streamer`. Este comando é restrito a administradores.

### 📂 Arquivos Principais
* `main.py`: O código principal do bot, contendo a lógica de conexão com o Discord e o YouTube, além de gerenciar os comandos e as rotinas de verificação.
* `streamers.json`: O "banco de dados" do bot, armazenado no GitHub, que guarda as informações dos streamers e as configurações de cargos por servidor.
* `requirements.txt`: Lista todas as bibliotecas Python necessárias para o projeto.
* `render.yaml`: O arquivo de configuração para o serviço de hospedagem Render.
