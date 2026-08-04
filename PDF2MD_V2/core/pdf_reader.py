import re

import fitz
import pymupdf4llm
import numpy as np
from PIL import Image

from core.configuracao import config_app
from core.utils import log_erro

class PDFReader:
    def __init__(self, caminho_pdf):
        self.caminho_pdf = caminho_pdf
        self.doc = fitz.open(caminho_pdf)
        self.total_paginas = len(self.doc)

    def pagina_tem_texto_nativo(self, numero_pagina, limite_caracteres_uteis=20):
        try:
            pagina = self.doc.load_page(numero_pagina)
            texto_cru = pagina.get_text("text") or ""
            texto_limpo = re.sub(r"\s+", " ", texto_cru).strip()

            if texto_limpo and any(ch.isalnum() for ch in texto_limpo):
                return True

            blocos = pagina.get_text("blocks")
            total_caracteres_miolo = 0
            for bloco in blocos:
                texto_bloco = bloco[4].strip() if len(bloco) > 4 else ""
                if len(texto_bloco) > 10 and not any(termo in texto_bloco.lower() for termo in ["http://", "https://", "assinado eletronicamente", "documento gerado"]):
                    total_caracteres_miolo += len(texto_bloco)

            return total_caracteres_miolo > limite_caracteres_uteis

        except Exception as e:
            log_erro(f"Erro ao inspecionar a página {numero_pagina} do PDF", e)
            return False

    def extrair_texto_nativo(self, numero_pagina):
        try:
            pagina = self.doc.load_page(numero_pagina)
            texto = (pagina.get_text("text") or "").strip()
            if texto:
                return texto

            try:
                markdown = pymupdf4llm.to_markdown(self.doc, pages=[numero_pagina], force_text=True)
                if markdown and str(markdown).strip():
                    return str(markdown).strip()
            except Exception:
                pass

            return ""
        except Exception as e:
            log_erro(f"Erro ao extrair texto nativo da página {numero_pagina}", e)
            return ""

    def extrair_markdown_rapido(self, numero_pagina):
        try:
            texto = self.extrair_texto_nativo(numero_pagina)
            if texto:
                return texto
            return f"> [Erro de leitura na página {numero_pagina+1}]\n"
        except Exception as e:
            log_erro(f"Erro ao extrair markdown nativo da página {numero_pagina}", e)
            return f"> [Erro de leitura na página {numero_pagina+1}]\n"

    def extrair_imagem_da_pagina(self, numero_pagina):
        try:
            pagina = self.doc.load_page(numero_pagina)
            dpi = max(140, int(config_app.get("dpi_leitura") or 120))
            pix = pagina.get_pixmap(dpi=dpi)

            if pix.width == 0 or pix.height == 0:
                return None

            modo = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(modo, [pix.width, pix.height], pix.samples)

            if modo == "RGBA":
                img = img.convert("RGB")

            img_array = np.array(img)
            if img_array.size == 0:
                return None

            return img_array

        except Exception as e:
            log_erro(f"Erro ao converter página {numero_pagina} em imagem", e)
            return None

    def fechar(self):
        self.doc.close()