import pathlib
import re
import threading

from core.pdf_reader import PDFReader
from core.markdown_writer import MarkdownWriter
from core.historico import historico_app
from core.utils import log_erro
from ocr.manager import ocr_engine
from core.configuracao import config_app

class MotorConversao:
    def __init__(self, arquivos, pasta_destino, usar_ocr, cb_progresso, cb_concluido, cb_erro):
        self.arquivos = arquivos
        self.pasta_destino = pasta_destino
        self.usar_ocr = usar_ocr
        self.cb_progresso = cb_progresso
        self.cb_concluido = cb_concluido
        self.cb_erro = cb_erro
        self.cancelar = False

    def iniciar(self):
        threading.Thread(target=self._processar_fila, daemon=True).start()

    def solicitar_cancelamento(self):
        self.cancelar = True

    def _processar_fila(self):
        try:
            total_arquivos = len(self.arquivos)
            modo_atual = config_app.get("modo_conversao") or "Híbrido (Automático)"

            for idx_arq, caminho_pdf in enumerate(self.arquivos):
                if self.cancelar:
                    break

                nome_original = pathlib.Path(caminho_pdf).stem
                pasta_base = pathlib.Path(self.pasta_destino) if self.pasta_destino else pathlib.Path(caminho_pdf).parent
                pasta_base.mkdir(parents=True, exist_ok=True)
                caminho_saida = str(pasta_base / (nome_original + ".md"))

                leitor = PDFReader(caminho_pdf)
                escritor = MarkdownWriter(caminho_saida)

                for i in range(leitor.total_paginas):
                    if self.cancelar:
                        break

                    texto_extraido = ""
                    porcentagem = (i + 1) / leitor.total_paginas
                    status_msg = f"Arquivo {idx_arq+1}/{total_arquivos} | Página {i+1} de {leitor.total_paginas}"

                    try:
                        forcar_ia = (modo_atual == "Forçar OCR em Todas as Páginas")
                        texto_nativo = leitor.extrair_markdown_rapido(i)
                        texto_nativo_limpo = (texto_nativo or "").strip()
                        tem_texto_util = bool(
                            texto_nativo_limpo
                            and not texto_nativo_limpo.startswith("> [Erro")
                            and len(re.sub(r"[^A-Za-z0-9]", "", texto_nativo_limpo)) > 20
                        )

                        if not forcar_ia and tem_texto_util:
                            status_msg = f"{status_msg} (Extração Digital)"
                            self.cb_progresso(status_msg, porcentagem, "")
                            texto_extraido = texto_nativo_limpo
                        elif self.usar_ocr:
                                status_msg = f"{status_msg} (Processando OCR...)"
                                self.cb_progresso(status_msg, porcentagem, "> 🤖 Lendo imagem/documento via OCR...\n")

                                img_bgr = leitor.extrair_imagem_da_pagina(i)
                                if img_bgr is not None:
                                    texto_ocr = ocr_engine.ler_imagem(img_bgr)
                                    if texto_ocr and texto_ocr.strip() and not texto_ocr.startswith("> ["):
                                        texto_extraido = f"\n> 🤖 **[IA - OCR Pág. {i+1}]**\n{texto_ocr}\n"
                                    else:
                                        texto_extraido = f"\n> [Página {i+1}: OCR não retornou texto legível. O documento pode ser um PDF digital com texto já extraível ou uma imagem muito ruim.]\n"
                                else:
                                    texto_extraido = f"\n> [Página {i+1}: Imagem vazia ou ilegível]\n"
                        else:
                            status_msg = f"{status_msg} (OCR Desativado)"
                            self.cb_progresso(status_msg, porcentagem, "")
                            texto_extraido = f"\n> 📸 [Imagem na Página {i+1} - OCR Desativado]\n"

                        if not texto_extraido.strip() and self.usar_ocr:
                            texto_extraido = f"\n> [Página {i+1}: OCR não retornou texto legível. O PDF pode não ter conteúdo escaneado ou o texto ficou muito fraco para leitura.]\n"

                    except Exception as e:
                        log_erro(f"Falha ao processar a página {i+1} do arquivo {caminho_pdf}", e)
                        texto_extraido = f"\n> [Erro ao processar a página {i+1}: {str(e)}]\n"

                    escritor.escrever_pagina(texto_extraido)
                    if texto_extraido.strip():
                        self.cb_progresso(status_msg, porcentagem, texto_extraido)

                leitor.fechar()

                if not self.cancelar:
                    historico_app.adicionar_projeto(pathlib.Path(caminho_pdf).name, caminho_saida)

            if self.cancelar:
                self.cb_erro("⚠️ Conversão Cancelada pelo usuário.", cancelado=True)
            else:
                self.cb_concluido()

        except Exception as e:
            log_erro("Falha crítica no motor de conversão", e)
            self.cb_erro(f"Erro inesperado:\n{str(e)}")