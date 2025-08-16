# 🤖 T-1000 - Monitor de Lives do YouTube para Discord

## 📖 Sobre

O **T-1000** é um bot de Discord projetado para monitorar canais do YouTube e gerenciar automaticamente um cargo de "Live" para os streamers. Ele utiliza a API do YouTube para detectar quando um canal está transmitindo ao vivo e atualiza o cargo do usuário correspondente no Discord, tornando fácil para a comunidade saber quem está online.

O bot usa o GitHub como um banco de dados simples, o que o torna ideal para ser hospedado em plataformas gratuitas como o Render.

## ✨ Funcionalidades

* **Monitoramento de Lives:** Verifica periodicamente canais do YouTube para saber se estão ao vivo.
* **Gestão de Cargos Automática:** Adiciona ou remove um cargo pré-definido quando o streamer inicia ou encerra a live.
* **Comandos Slash (`/`)**: Interface moderna e intuitiva para adicionar, remover e configurar streamers diretamente no Discord.
* **Sistema de Banco de Dados Simples:** Armazena as informações dos streamers em um arquivo JSON no GitHub.
* **Uptime Contínuo:** Configurado para ser hospedado no Render e mantido online com um serviço de monitoramento como o UptimeRobot.

## 🚀 Como Usar

O bot utiliza comandos slash (`/`) para todas as interações.

* `/adicionar_youtube nome_do_canal: <handle> usuario: <membro>`
    * Adiciona um streamer. Use o **handle** do YouTube com `@` (ex: `@felps`).
    * **Exemplo:** `/adicionar_youtube nome_do_canal: @seu-streamer usuario: @SeuMembroDiscord`

* `/remover_canal usuario: <membro>`
    * Remove o monitoramento de um usuário.
    * **Exemplo:** `/remover_canal usuario: @SeuMembroDiscord`

* `/configurar_cargo cargo: <cargo>`
    * Define qual cargo será adicionado/removido automaticamente.
    * **Exemplo:** `/configurar_cargo cargo: @Live`

## ⚙️ Configuração (Setup)

Para rodar o bot, você precisará configurar as credenciais necessárias em três plataformas: Discord, Google (YouTube) e GitHub.

### Passo 1: Discord

1. Vá para o [Portal do Desenvolvedor do Discord](https://discord.com/developers/applications).
2. Crie uma nova aplicação e, em seguida, um bot.
3. Vá em **Bot** > **Privileged Gateway Intents** e ative o `SERVER MEMBERS INTENT`.
4. Copie o **TOKEN** do bot. Você precisará dele mais tarde.
5. Adicione o bot ao seu servidor com permissões de `Administrator` ou com as seguintes permissões: `Manage Roles` e `Read Messages/View Channels`.

### Passo 2: Google Cloud (API do YouTube)

1. Vá para o [Console do Google Cloud](https://console.cloud.google.com/).
2. Crie um novo projeto.
3. No menu, vá em **APIs e Serviços** > **Biblioteca**.
4. Pesquise e ative a **YouTube Data API v3**.
5. Vá em **APIs e Serviços** > **Credenciais**.
6. Clique em **+ CRIAR CREDENCIAIS** > **Chave de API** e copie a chave.

### Passo 3: GitHub (Banco de Dados)

1. Crie um novo repositório **privado** no seu GitHub para hospedar o código e o arquivo de dados.
2. Crie um arquivo chamado `streamers.json` na raiz do repositório. O arquivo deve conter o seguinte JSON vazio:
    ```json
    {
      "usuarios": {},
      "servidores": {}
    }
    ```
3. Vá para as suas **Configurações do GitHub** > **Developer settings** > **Personal access tokens** > **Tokens (classic)**.
4. Gere um novo token e dê a ele o escopo de `repo` para que o bot possa ler e escrever no arquivo JSON. **Copie o token, ele não será exibido novamente.**

### Passo 4: Render (Hospedagem)

1. Vá para o [Render](https://render.com/) e crie um novo **Web Service**.
2. Selecione a opção de construir a partir de um repositório Git.
3. Conecte seu repositório do GitHub. O Render é capaz de se conectar a repositórios privados, então não há necessidade de torná-lo público.
4. Configure o web service:
    * **Environment:** Python 3
    * **Build Command:** `pip install -r requirements.txt` (Assumindo que você tenha um arquivo `requirements.txt` com as dependências).
    * **Start Command:** `python seu_arquivo_principal.py` (Se o seu arquivo principal for diferente).
5. Vá em **Environment** para adicionar suas variáveis de ambiente (Environment Variables) e cole as chaves que você copiou:
    * **`DISCORD_TOKEN`**: O token do seu bot do Discord.
    * **`YOUTUBE_API_KEY`**: A chave da API do YouTube.
    * **`GITHUB_TOKEN`**: O token de acesso pessoal que você criou no GitHub.
    * **`GITHUB_REPO`**: O nome do seu repositório no formato `seu-usuario/seu-repositorio`.
6. **Importante:** O Render suspende serviços gratuitos após 15 minutos de inatividade. Para mantê-lo online, use um serviço como o [UptimeRobot](https://uptimerobot.com/) para pingar a URL do seu bot a cada 5 minutos.

## 🛠️ Tecnologias Utilizadas

* **Python:** Linguagem de programação principal.
* **`discord.py`**: Biblioteca para interação com o Discord.
* **`requests`**: Biblioteca para comunicação com a API do YouTube.
* **`PyGithub`**: Biblioteca para manipulação de arquivos no GitHub.
* **`Flask`**: Web server simples para o `health check`.

## 📜 Licença

Este projeto está licenciado sob a Licença MIT.
