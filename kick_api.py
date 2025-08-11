import aiohttp
import logging
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class KickAPI:
    """Classe para interagir com o Kick simulando um navegador."""
    def __init__(self):
        # Adiciona um conjunto completo de cabeçalhos para simular uma requisição de navegador real.
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
            'Referer': 'https://kick.com/',
        }
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_stream_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Verifica se um canal do Kick está ao vivo buscando informações na página principal."""
        kick_url = f"https://kick.com/{username}"
        try:
            async with self.session.get(kick_url) as response:
                response.raise_for_status()
                html_content = await response.text()
                
                # A forma mais confiável de verificar se a live está online é procurar por um elemento
                # HTML específico que só aparece quando o canal está ao vivo.
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Procura por um elemento de metadados JSON no script da página
                script_tag = soup.find('script', id='__NEXT_DATA__')
                if script_tag:
                    import json
                    json_data = json.loads(script_tag.string)
                    channel_data = json_data['props']['pageProps']['channel']
                    if channel_data['livestream']:
                        return {
                            'is_live': True,
                            'livestream': channel_data['livestream']
                        }
                    
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro ao acessar a página do Kick para '{username}': {e}")
        except Exception as e:
            logger.error(f"❌ Erro inesperado ao processar dados da página do Kick para '{username}': {e}")
        
        return None
