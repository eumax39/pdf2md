import logging
import re

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageOps

from core.configuracao import config_app
from core.utils import log_erro

# Silencia os avisos verbosos da IA no terminal
logging.getLogger("ppocr").setLevel(logging.ERROR)


class GerenciadorOCR:
    def __init__(self):
        self.motor = None
        self._falhas_consecutivas = 0
        self._desabilitado = False
        self._cache_imagens = {}

    def inicializar_se_necessario(self):
        if self._desabilitado:
            return

        if self.motor is None or self.motor == "ERRO":
            try:
                self.motor = PaddleOCR(
                    use_textline_orientation=False,
                    lang=config_app.get("idioma_ocr") or "pt",
                    enable_mkldnn=False,
                    cpu_threads=1,
                    text_detection_model_dir=None,
                    text_recognition_model_dir=None,
                )
                self._falhas_consecutivas = 0
            except Exception as e:
                self._falhas_consecutivas += 1
                log_erro("Falha ao inicializar o motor PaddleOCR", e)
                self.motor = "ERRO"
                if self._falhas_consecutivas >= 3:
                    self._desabilitado = True

    def _preprocessar_imagem(self, img_array):
        if not isinstance(img_array, np.ndarray) or img_array.size == 0:
            return None

        try:
            imagem = Image.fromarray(img_array)
            if imagem.mode != "RGB":
                imagem = imagem.convert("RGB")

            largura, altura = imagem.size
            largura_maxima = 1200
            if largura > largura_maxima:
                proporcao = largura_maxima / largura
                nova_altura = max(1, int(altura * proporcao))
                imagem = imagem.resize((largura_maxima, nova_altura), Image.Resampling.BILINEAR)

            return np.array(imagem)
        except Exception:
            return img_array

    def _limpar_texto(self, texto):
        if not texto:
            return ""
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    def _extrair_texto_de_valor(self, valor):
        if valor is None:
            return ""

        if isinstance(valor, str):
            return valor.strip()

        if isinstance(valor, (list, tuple)):
            partes = []
            for item in valor:
                texto = self._extrair_texto_de_valor(item)
                if texto:
                    partes.append(texto)
            return " ".join(partes).strip()

        if isinstance(valor, dict):
            for chave in ("rec_texts", "rec_text", "text", "ocr_text", "pred_texts", "pred_text"):
                if chave in valor:
                    return self._extrair_texto_de_valor(valor[chave])

            for item in valor.values():
                texto = self._extrair_texto_de_valor(item)
                if texto:
                    return texto
            return ""

        attrs = getattr(valor, "__dict__", None)
        if attrs:
            texto = self._extrair_texto_de_valor(attrs)
            if texto:
                return texto

        for chave in ("rec_texts", "rec_text", "text", "ocr_text", "pred_texts", "pred_text"):
            if hasattr(valor, chave):
                return self._extrair_texto_de_valor(getattr(valor, chave))

        return ""

    def _extrair_texto_do_resultado(self, resultados):
        if not resultados:
            return ""

        if isinstance(resultados, dict):
            resultados = [resultados]
        elif not isinstance(resultados, (list, tuple)):
            resultados = [resultados]

        textos = []
        for resultado in resultados:
            texto = self._extrair_texto_de_valor(resultado)
            if texto:
                textos.append(texto)

        return self._limpar_texto(" ".join(textos))

    def ler_imagem(self, img_array):
        self.inicializar_se_necessario()

        if self._desabilitado or self.motor is None or self.motor == "ERRO" or img_array is None:
            return "> [Aviso: OCR indisponível ou imagem inválida para leitura]\n"

        try:
            # imagem_processada não é mais usada aqui; o loop já chama _preprocessar_imagem
            if not isinstance(img_array, np.ndarray) or img_array.size == 0:
                return "> [Aviso: Matriz de imagem vazia]\n"

            texto_extraido = ""

            # tenta primeiro a imagem original, depois a redimensionada se necessário
            for candidato in [img_array, self._preprocessar_imagem(img_array)]:
                if candidato is None:
                    continue
                try:
                    resultados = self.motor.ocr(candidato)
                    texto_extraido = self._extrair_texto_do_resultado(resultados)
                    if texto_extraido.strip():
                        break
                except Exception:
                    continue

            if texto_extraido.strip():
                return f"\n{texto_extraido}\n"

            try:
                imagem_pil = Image.fromarray(np.array(img_array))
                if imagem_pil.mode != "RGB":
                    imagem_pil = imagem_pil.convert("RGB")
                imagem_pil = imagem_pil.resize((imagem_pil.width * 2, imagem_pil.height * 2), Image.Resampling.LANCZOS)
                return f"\n> [OCR não retornou texto legível nesta página. A imagem pode estar muito escura, muito pequena ou sem contraste suficiente.]\n"
            except Exception:
                return "> [OCR não retornou texto legível nesta página]\n"

        except Exception as e:
            log_erro("Erro interno durante a extração de texto", e)
            return "> [Erro no processamento OCR desta imagem]\n"


ocr_engine = GerenciadorOCR()