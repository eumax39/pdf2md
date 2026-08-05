import pathlib
import re
import threading
import queue
import time
import io

import fitz
from PIL import Image

from core.pdf_reader import PDFReader
from core.markdown_writer import MarkdownWriter
from core.historico import historico_app
from core.utils import log_erro
from ocr.manager import ocr_engine
from core.configuracao import config_app

MODO_HIBRIDO = "Híbrido (Texto Nativo + OCR em Imagem Relevante)"
MODO_HIBRIDO_ANTIGO = "Híbrido (Automático)"
MODO_FORCAR_OCR = "Forçar OCR (Ignora Texto Nativo)"
MODO_FORCAR_OCR_ANTIGO = "Forçar OCR em Todas as Páginas"
MODO_REFERENCIA_IMAGEM = "Texto Nativo + Referência de Imagem (Sem OCR)"


def normalizar_modo_conversao(valor):
    aliases = {
        MODO_HIBRIDO_ANTIGO: MODO_HIBRIDO,
        MODO_FORCAR_OCR_ANTIGO: MODO_FORCAR_OCR,
        MODO_REFERENCIA_IMAGEM: MODO_REFERENCIA_IMAGEM,
        MODO_HIBRIDO: MODO_HIBRIDO,
        MODO_FORCAR_OCR: MODO_FORCAR_OCR,
    }
    return aliases.get(valor, MODO_HIBRIDO)

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

    def _texto_nativo_util(self, texto, modo_referencia_imagem=False):
        texto_limpo = (texto or "").strip()
        if not texto_limpo or texto_limpo.startswith("> [Erro"):
            return False

        if modo_referencia_imagem and self._parece_rodape_pje(texto_limpo):
            return False

        return len(re.sub(r"[^A-Za-z0-9]", "", texto_limpo)) > 20

    def _parece_rodape_pje(self, texto):
        """Detecta páginas com apenas metadados/rodapé do PJe sem conteúdo útil do corpo."""
        linhas = [ln.strip() for ln in (texto or "").splitlines() if ln.strip()]
        if not linhas:
            return False

        padroes_rodape = [
            r"^Num\.\s*\d+\s*-\s*P[aá]g\.\s*\d+",
            r"^Assinado eletronicamente por:",
            r"^https?://pje\.",
            r"^N[uú]mero do documento:",
            r"^Este documento foi gerado pelo usu[aá]rio",
            r"^SIGILOSO$",
        ]

        ruido = 0
        linhas_validas = []
        for linha in linhas:
            if any(re.search(p, linha, flags=re.IGNORECASE) for p in padroes_rodape):
                ruido += 1
            else:
                linhas_validas.append(linha)

        chars_validos = len(re.sub(r"[^A-Za-z0-9]", "", " ".join(linhas_validas)))
        proporcao_ruido = ruido / max(1, len(linhas))

        # Se quase tudo é rodapé PJe e sobra pouco conteúdo real, tratamos como página-imagem.
        return proporcao_ruido >= 0.6 and chars_validos < 80

    def _adicionar_imagem_ao_pdf_referencias(self, doc_ref, imagem_bytes, referencia, pagina_origem):
        """Adiciona a imagem em uma nova página do PDF único de referências e escreve legenda abaixo."""
        try:
            with Image.open(io.BytesIO(imagem_bytes)) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                out = io.BytesIO()
                img.save(out, format="PNG")
                png_bytes = out.getvalue()
                img_w, img_h = img.size

            page_w, page_h = 595.0, 842.0  # A4 aproximado em pontos
            margem = 36.0
            area_legenda = 56.0
            max_w = page_w - (2 * margem)
            max_h = page_h - (2 * margem) - area_legenda

            escala = min(max_w / max(1.0, float(img_w)), max_h / max(1.0, float(img_h)))
            draw_w = max(1.0, float(img_w) * escala)
            draw_h = max(1.0, float(img_h) * escala)

            x0 = (page_w - draw_w) / 2.0
            y0 = margem
            rect_img = fitz.Rect(x0, y0, x0 + draw_w, y0 + draw_h)

            page = doc_ref.new_page(width=page_w, height=page_h)
            page.insert_image(rect_img, stream=png_bytes)

            legenda = f"Ref: {referencia} | Origem: página {pagina_origem}"
            rect_legenda = fitz.Rect(margem, page_h - margem - 24, page_w - margem, page_h - margem)
            page.insert_textbox(rect_legenda, legenda, fontsize=10, align=1)

            return doc_ref.page_count
        except Exception as e:
            log_erro(f"Falha ao adicionar imagem '{referencia}' ao PDF de referências", e)
            return None

    def _preparar_paginas(self, leitor, idx_arq, total_arquivos, modo_atual, modo_referencia_imagem, fila_paginas):
        try:
            forcar_ia = (modo_atual == MODO_FORCAR_OCR)
            modo_hibrido = (modo_atual == MODO_HIBRIDO)

            for i in range(leitor.total_paginas):
                if self.cancelar:
                    break

                porcentagem = (i + 1) / leitor.total_paginas
                status_base = f"Arquivo {idx_arq+1}/{total_arquivos} | Página {i+1} de {leitor.total_paginas}"

                if modo_referencia_imagem:
                    texto_nativo_limpo = (leitor.extrair_texto_nativo_estrito(i) or "").strip()
                    imagens_relevantes = leitor.extrair_imagens_relevantes(i)
                else:
                    texto_nativo = leitor.extrair_markdown_rapido(i)
                    texto_nativo_limpo = (texto_nativo or "").strip()
                    imagens_relevantes = leitor.extrair_imagens_relevantes(i) if modo_hibrido else []

                tem_imagem = bool(imagens_relevantes) if modo_referencia_imagem else False
                tem_imagem_relevante = bool(imagens_relevantes) if modo_hibrido else False

                tem_texto_util = self._texto_nativo_util(
                    texto_nativo_limpo,
                    modo_referencia_imagem=modo_referencia_imagem,
                )

                if modo_referencia_imagem and not tem_texto_util:
                    # Evita gravar apenas assinatura/rodapé no markdown nesse modo.
                    texto_nativo_limpo = ""

                if forcar_ia:
                    precisa_ocr = bool(self.usar_ocr)
                elif modo_hibrido:
                    # Híbrido: mantém texto nativo e aplica OCR complementar quando há imagem relevante.
                    precisa_ocr = bool(self.usar_ocr and (not tem_texto_util or tem_imagem_relevante))
                else:
                    precisa_ocr = bool(self.usar_ocr and (forcar_ia or not tem_texto_util))

                img_bgr = leitor.extrair_imagem_da_pagina(i) if precisa_ocr else None

                payload = {
                    "pagina": i,
                    "porcentagem": porcentagem,
                    "status_base": status_base,
                    "tem_texto_util": tem_texto_util,
                    "tem_imagem": tem_imagem,
                    "tem_imagem_relevante": tem_imagem_relevante,
                    "imagens_relevantes": imagens_relevantes,
                    "texto_nativo_limpo": texto_nativo_limpo,
                    "precisa_ocr": precisa_ocr,
                    "img_bgr": img_bgr,
                }

                fila_paginas.put(payload)

        except Exception as e:
            fila_paginas.put({"erro": str(e)})
        finally:
            fila_paginas.put(None)

    def _processar_fila(self):
        try:
            total_arquivos = len(self.arquivos)
            modo_atual = normalizar_modo_conversao(config_app.get("modo_conversao"))
            modo_referencia_imagem = (modo_atual == MODO_REFERENCIA_IMAGEM)

            for idx_arq, caminho_pdf in enumerate(self.arquivos):
                if self.cancelar:
                    break

                nome_original = pathlib.Path(caminho_pdf).stem
                pasta_base = pathlib.Path(self.pasta_destino) if self.pasta_destino else pathlib.Path(caminho_pdf).parent
                pasta_base.mkdir(parents=True, exist_ok=True)
                caminho_saida = str(pasta_base / (nome_original + ".md"))
                caminho_pdf_referencias = pasta_base / f"{nome_original}_referencias_imagens.pdf"

                leitor = PDFReader(caminho_pdf)
                escritor = MarkdownWriter(caminho_saida)
                doc_referencias = fitz.open() if modo_referencia_imagem else None

                if self.usar_ocr and not modo_referencia_imagem:
                    ocr_engine.preaquecer_worker()

                fila_paginas = queue.Queue(maxsize=2)
                produtor = threading.Thread(
                    target=self._preparar_paginas,
                    args=(leitor, idx_arq, total_arquivos, modo_atual, modo_referencia_imagem, fila_paginas),
                    daemon=True,
                )
                produtor.start()

                ultimo_status_ts = 0.0

                while True:
                    if self.cancelar:
                        break

                    payload = fila_paginas.get()
                    if payload is None:
                        break

                    if "erro" in payload:
                        raise RuntimeError(payload["erro"])

                    i = payload["pagina"]
                    porcentagem = payload["porcentagem"]
                    status_base = payload["status_base"]
                    tem_texto_util = payload["tem_texto_util"]
                    tem_imagem = payload.get("tem_imagem", False)
                    tem_imagem_relevante = payload.get("tem_imagem_relevante", False)
                    imagens_relevantes = payload.get("imagens_relevantes", [])
                    texto_nativo_limpo = payload["texto_nativo_limpo"]
                    precisa_ocr = payload["precisa_ocr"]
                    img_bgr = payload["img_bgr"]

                    texto_extraido = ""
                    status_msg = status_base

                    try:
                        if modo_referencia_imagem:
                            partes = []

                            if tem_texto_util:
                                status_msg = f"{status_base} (Extração Digital)"
                                partes.append(texto_nativo_limpo)

                            if tem_imagem:
                                status_msg = f"{status_base} (Extração Digital + Referência de Imagem)" if tem_texto_util else f"{status_base} (Extraindo Imagem de Referência)"
                                refs_pagina = []

                                for idx_img, img_info in enumerate(imagens_relevantes, start=1):
                                    nome_ref = f"imagem_pagina_{i+1:04d}_{idx_img:02d}"
                                    pg_ref = self._adicionar_imagem_ao_pdf_referencias(
                                        doc_referencias,
                                        img_info.get("bytes"),
                                        nome_ref,
                                        i + 1,
                                    )
                                    if pg_ref is not None:
                                        refs_pagina.append((nome_ref, pg_ref))

                                if refs_pagina:
                                    caminho_relativo_pdf = caminho_pdf_referencias.relative_to(pasta_base).as_posix()
                                    linhas_ref = [
                                        f"> [Página {i+1} contém imagem(ns) relevante(s). PDF único de referências: [{caminho_relativo_pdf}]({caminho_relativo_pdf})]"
                                    ]
                                    for nome_ref, pg_ref in refs_pagina:
                                        linhas_ref.append(f"> - Ref: {nome_ref} (pág. {pg_ref} do [PDF de referências]({caminho_relativo_pdf}))")
                                    partes.append("\n".join(linhas_ref))
                                else:
                                    partes.append(f"> [Página {i+1}: Nenhuma imagem relevante foi exportada]")

                            if not tem_texto_util and not tem_imagem:
                                status_msg = f"{status_base} (Sem texto nativo e sem imagem detectada)"
                                partes.append(f"> [Página {i+1}: Sem texto nativo útil e sem imagem detectada]")

                            texto_extraido = "\n" + "\n\n".join([p for p in partes if p.strip()]) + "\n"
                        elif tem_texto_util and not precisa_ocr:
                            status_msg = f"{status_base} (Extração Digital)"
                            texto_extraido = texto_nativo_limpo
                        elif precisa_ocr:
                            if modo_atual == MODO_FORCAR_OCR:
                                status_msg = f"{status_base} (Processando OCR...)"
                            elif tem_imagem_relevante and tem_texto_util:
                                status_msg = f"{status_base} (OCR complementar em imagem relevante...)"
                            else:
                                status_msg = f"{status_base} (Processando OCR...)"

                            agora = time.monotonic()
                            if (agora - ultimo_status_ts) >= 0.35:
                                self.cb_progresso(status_msg, porcentagem, "> 🤖 Lendo imagem/documento via OCR...\n")
                                ultimo_status_ts = agora

                            if img_bgr is not None:
                                texto_ocr = ocr_engine.ler_imagem(img_bgr)
                                texto_ocr_limpo = (texto_ocr or "").strip()

                                if "excedeu o tempo limite" in texto_ocr_limpo.lower():
                                    dpi_retry = int(config_app.get("ocr_dpi_timeout_retry") or 110)
                                    status_retry = f"{status_base} (OCR retry leve em {dpi_retry} DPI...)"
                                    self.cb_progresso(status_retry, porcentagem, "> 🤖 Tentando OCR em modo leve para reduzir timeout...\n")

                                    img_retry = leitor.extrair_imagem_da_pagina(i, dpi_override=dpi_retry)
                                    if img_retry is not None:
                                        texto_retry = ocr_engine.ler_imagem(img_retry)
                                        texto_retry_limpo = (texto_retry or "").strip()
                                        if texto_retry_limpo:
                                            texto_ocr_limpo = texto_retry_limpo

                                if texto_ocr_limpo and not texto_ocr_limpo.startswith("> ["):
                                    if modo_atual == MODO_HIBRIDO and tem_texto_util:
                                        texto_extraido = (
                                            f"{texto_nativo_limpo}\n\n"
                                            f"> 🤖 **[IA - OCR complementar Pág. {i+1}]**\n\n{texto_ocr_limpo}\n"
                                        )
                                    else:
                                        texto_extraido = f"\n> 🤖 **[IA - OCR Pág. {i+1}]**\n\n{texto_ocr_limpo}\n"
                                elif texto_ocr_limpo.startswith("> ["):
                                    if modo_atual == MODO_HIBRIDO and tem_texto_util:
                                        texto_extraido = f"{texto_nativo_limpo}\n\n{texto_ocr_limpo}\n"
                                    else:
                                        texto_extraido = f"\n{texto_ocr_limpo}\n"
                                else:
                                    if modo_atual == MODO_HIBRIDO and tem_texto_util:
                                        texto_extraido = texto_nativo_limpo
                                    else:
                                        texto_extraido = f"\n> [Página {i+1}: OCR não retornou texto legível. O documento pode ser um PDF digital com texto já extraível ou uma imagem muito ruim.]\n"
                            else:
                                if modo_atual == MODO_HIBRIDO and tem_texto_util:
                                    texto_extraido = texto_nativo_limpo
                                else:
                                    texto_extraido = f"\n> [Página {i+1}: Imagem vazia ou ilegível]\n"
                        else:
                            status_msg = f"{status_base} (OCR Desativado)"
                            texto_extraido = f"\n> 📸 [Imagem na Página {i+1} - OCR Desativado]\n"

                        if not texto_extraido.strip() and self.usar_ocr:
                            texto_extraido = f"\n> [Página {i+1}: OCR não retornou texto legível. O PDF pode não ter conteúdo escaneado ou o texto ficou muito fraco para leitura.]\n"

                    except Exception as e:
                        log_erro(f"Falha ao processar a página {i+1} do arquivo {caminho_pdf}", e)
                        texto_extraido = f"\n> [Erro ao processar a página {i+1}: {str(e)}]\n"

                    escritor.escrever_pagina(texto_extraido)
                    if texto_extraido.strip():
                        self.cb_progresso(status_msg, porcentagem, texto_extraido)

                produtor.join(timeout=1.0)

                if doc_referencias is not None:
                    try:
                        if doc_referencias.page_count > 0:
                            doc_referencias.save(str(caminho_pdf_referencias))
                    finally:
                        doc_referencias.close()

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
        finally:
            ocr_engine.finalizar_worker()