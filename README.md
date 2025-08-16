# 🤖 T-1000 - Monitor de Lives do YouTube para Discord

!(https://placehold.co/800x400/2c2f33/ffffff?text=T-1000)

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

1. Vá para o [Portal do Desenvolvedor do Discord](https://www.google.com/search?q=https://discord.com/developers/applications).

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
