import json
import requests
from typing import Optional

from core.configuracao import config_app
from core.utils import log_erro, log_info, log_aviso


class ClienteDeepSeek:
    """
    Cliente para integração com a API do DeepSeek (DeepSeek-V3).
    Refina textos com falha de OCR, remove rodapés repetitivos de sistemas PJe
    e formata a saída em Markdown jurídico limpo.
    """

    ENDPOINT_DEFAULT = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        self.api_key = api_key or config_app.get("deepseek_api_key") or ""
        self.model = model
        self.timeout_segundos = 25.0

    def refinar_texto_ocr(self, texto: str, numero_pagina: int = 1) -> Optional[str]:
        """
        Envia o texto para a API do DeepSeek para correção de erros de OCR,
        higienização de rodapés e formatação em Markdown limpo.
        Retorna o texto refinado ou None se houver erro/timeout.
        """
        chave = self.api_key or config_app.get("deepseek_api_key")
        if not chave or not str(chave).strip():
            log_aviso("DeepSeek: Chave de API não configurada.")
            return None

        if not texto or not texto.strip():
            return None

        prompt_sistema = (
            "Você é um assistente especialista em revisão de textos jurídicos e leitura de OCR de processos judiciais brasileiros. "
            "Sua única tarefa é:\n"
            "1. Corrigir erros de digitação e leitura OCR do texto enviado (ex: letras trocadas como '0AB' -> 'OAB', 'corn' -> 'com', acentos ausentes).\n"
            "2. Remover linhas de metadados/rodapés repetitivos de sistemas PJe/tribunais (ex: 'Num. 12345 - Pág. 1', 'Assinado eletronicamente por...').\n"
            "3. Formatar o texto em Markdown limpo (usando ## para títulos de seções e > para ementas/jurisprudências).\n"
            "REGRA ABSOLUTA: MANTENHA 100% dos nomes próprios, números de processo, valores, datas e o conteúdo jurídico original sem resumir ou alterar nenhuma informação."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Texto da Página {numero_pagina}:\n\n{texto.strip()}"},
            ],
            "temperature": 0.1,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {chave.strip()}",
            "Content-Type": "application/json",
        }

        try:
            log_info(f"DeepSeek: Enviando página {numero_pagina} para refinamento de OCR via API...")
            resp = requests.post(
                self.ENDPOINT_DEFAULT,
                json=payload,
                headers=headers,
                timeout=self.timeout_segundos,
            )

            if resp.status_code == 200:
                dados = resp.json()
                choices = dados.get("choices") or []
                if choices:
                    conteudo = choices[0].get("message", {}).get("content", "").strip()
                    if conteudo:
                        log_info(f"DeepSeek: Página {numero_pagina} refinada com sucesso!")
                        return conteudo
                log_aviso(f"DeepSeek: Resposta vazia da API na página {numero_pagina}")
                return None
            else:
                log_erro(f"DeepSeek: API retornou status HTTP {resp.status_code}: {resp.text}", Exception(resp.text))
                return None

        except Exception as e:
            log_erro(f"DeepSeek: Falha de conexão/timeout ao refinar página {numero_pagina}", e)
            return None
