import pathlib
import re
import threading
import queue
import time
import io
import json
from datetime import datetime

import fitz
from PIL import Image

from core.pdf_reader import PDFReader
from core.markdown_writer import MarkdownWriter
from core.historico import historico_app
from core.utils import log_erro, log_info, log_aviso
from ocr.manager import ocr_engine
from core.configuracao import config_app

MODO_HIBRIDO = "Híbrido (Texto Nativo + OCR em Imagem Relevante)"
MODO_HIBRIDO_ANTIGO = "Híbrido (Automático)"
MODO_FORCAR_OCR = "Forçar OCR (Ignora Texto Nativo)"
MODO_FORCAR_OCR_ANTIGO = "Forçar OCR em Todas as Páginas"
MODO_REFERENCIA_IMAGEM = "Texto Nativo + Referência de Imagem (Sem OCR)"
FORMATO_MD = "Markdown (.md)"
FORMATO_PDF_OCR = "PDF com OCR (.pdf)"


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
    def __init__(self, arquivos, pasta_destino, usar_ocr, cb_progresso, cb_concluido, cb_erro, formato_saida=FORMATO_MD, cb_status_arquivo=None):
        self.arquivos = arquivos
        self.pasta_destino = pasta_destino
        self.usar_ocr = usar_ocr
        self.cb_progresso = cb_progresso
        self.cb_concluido = cb_concluido
        self.cb_erro = cb_erro
        self.formato_saida = formato_saida
        self.cb_status_arquivo = cb_status_arquivo
        self._inicio_ts = time.monotonic()
        self._stats = {
            "arquivos_total": len(arquivos), "arquivos_concluidos": 0, "arquivos_com_erro": 0,
            "paginas_total": 0, "paginas_processadas": 0, "paginas_texto_nativo": 0,
            "paginas_ocr": 0, "paginas_referencia": 0, "paginas_com_alerta": 0,
        }
        self._stats_arquivos = []
        self.cancelar = False
        self._qtd_alertas_ocr = 0
        self._paginas_alerta_ocr = []


    def _status_arquivo(self, indice, status, detalhe=""):
        if self.cb_status_arquivo:
            try:
                self.cb_status_arquivo(indice, status, detalhe)
            except Exception:
                pass

    def _registrar_manifesto(self, pasta_base, resumo):
        if not bool(config_app.get("gerar_manifesto_conversao")):
            return None
        try:
            caminho = pathlib.Path(pasta_base) / "conversao_pdf2md.json"
            payload = {
                "gerado_em": datetime.now().isoformat(timespec="seconds"),
                "modo": normalizar_modo_conversao(config_app.get("modo_conversao")),
                "formato_saida": self.formato_saida,
                "cancelado": bool(self.cancelar),
                "resumo": resumo,
                "arquivos": self._stats_arquivos,
            }
            caminho.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(caminho)
        except Exception as e:
            log_erro("Falha ao salvar manifesto de conversão", e)
            return None

    def _ocr_com_retry(self, leitor, pagina, img_bgr, status_base, porcentagem):
        """OCR com uma retentativa conservadora para falha/timeout/resultado vazio."""
        texto = ""
        try:
            if img_bgr is not None:
                texto = ocr_engine.ler_imagem(img_bgr) or ""
        except Exception as e:
            log_aviso(f"OCR primário falhou na página {pagina + 1}: {type(e).__name__}")

        texto_limpo = texto.strip()
        deve_retry = (not texto_limpo) or ("excedeu o tempo limite" in texto_limpo.lower())
        if deve_retry and not self.cancelar:
            dpi_retry = int(config_app.get("ocr_dpi_timeout_retry") or 110)
            if bool(config_app.get("modo_compatibilidade")):
                dpi_retry = min(dpi_retry, 96)
            try:
                self.cb_progresso(
                    f"{status_base} (Retentativa OCR em {dpi_retry} DPI...)", porcentagem,
                    "> 🤖 Retentativa automática de OCR em modo leve...\n"
                )
                img_retry = leitor.extrair_imagem_da_pagina(pagina, dpi_override=dpi_retry)
                if img_retry is not None:
                    texto_retry = (ocr_engine.ler_imagem(img_retry) or "").strip()
                    if texto_retry:
                        texto_limpo = texto_retry
            except Exception as e:
                log_aviso(f"Retentativa OCR falhou na página {pagina + 1}: {type(e).__name__}")
        return texto_limpo

    def _gerar_pdf_pesquisavel_ocr(self, paginas_dados, caminho_saida_pdf):
        """Gera PDF pesquisável inserindo imagem da página + camada invisível de texto OCR."""
        doc = None
        try:
            doc = fitz.open()
            for dados in paginas_dados:
                img_array = dados.get("img_array")
                texto = (dados.get("texto") or "").strip()
                if img_array is None:
                    continue

                img = Image.fromarray(img_array)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                largura, altura = img.size
                page = doc.new_page(width=float(largura), height=float(altura))
                rect = fitz.Rect(0, 0, float(largura), float(altura))
                page.insert_image(rect, stream=img_bytes.getvalue())

                if texto:
                    try:
                        page.insert_textbox(
                            rect,
                            texto,
                            fontsize=8,
                            fontname="helv",
                            render_mode=3,
                        )
                    except Exception:
                        page.insert_text(
                            (6, 10),
                            texto,
                            fontsize=8,
                            fontname="helv",
                            render_mode=3,
                        )

            pathlib.Path(caminho_saida_pdf).parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(caminho_saida_pdf))
            return True
        except Exception as e:
            log_erro(f"Falha ao gerar PDF pesquisável OCR em '{caminho_saida_pdf}'", e)
            return False
        finally:
            if doc is not None:
                doc.close()

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
            saidas_geradas = []

            for idx_arq, caminho_pdf in enumerate(self.arquivos):
                if self.cancelar:
                    break

                self._status_arquivo(idx_arq, "processando")
                arquivo_stats = {"indice": idx_arq, "paginas_esperadas": 0, "paginas_processadas": 0, "status": "processando"}

                nome_original = pathlib.Path(caminho_pdf).stem
                pasta_base = pathlib.Path(self.pasta_destino) if self.pasta_destino else pathlib.Path(caminho_pdf).parent
                pasta_base.mkdir(parents=True, exist_ok=True)
                caminho_saida_md = str(pasta_base / (nome_original + ".md"))
                caminho_saida_pdf_ocr = str(pasta_base / f"{nome_original}_ocr.pdf")
                caminho_pdf_referencias = pasta_base / f"{nome_original}_referencias_imagens.pdf"

                gerar_pdf_ocr = bool(
                    self.formato_saida == FORMATO_PDF_OCR
                    and modo_atual == MODO_FORCAR_OCR
                    and self.usar_ocr
                )
                paginas_pdf_ocr = [] if gerar_pdf_ocr else None

                leitor = PDFReader(caminho_pdf)
                arquivo_stats["paginas_esperadas"] = int(leitor.total_paginas)
                self._stats["paginas_total"] += int(leitor.total_paginas)
                escritor = None if gerar_pdf_ocr else MarkdownWriter(caminho_saida_md)
                doc_referencias = fitz.open() if modo_referencia_imagem else None

                if self.usar_ocr and not modo_referencia_imagem:
                    ocr_engine.preaquecer_worker()

                fila_paginas = queue.Queue(maxsize=1 if bool(config_app.get("modo_compatibilidade")) else 2)
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
                    texto_ocr_limpo = ""

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
                                texto_ocr_limpo = self._ocr_com_retry(leitor, i, img_bgr, status_base, porcentagem)

                                if texto_ocr_limpo and not texto_ocr_limpo.startswith("> ["):
                                    if modo_atual == MODO_HIBRIDO and tem_texto_util:
                                        texto_extraido = (
                                            f"{texto_nativo_limpo}\n\n"
                                            f"> 🤖 **[IA - OCR complementar Pág. {i+1}]**\n\n{texto_ocr_limpo}\n"
                                        )
                                    else:
                                        texto_extraido = f"\n> 🤖 **[IA - OCR Pág. {i+1}]**\n\n{texto_ocr_limpo}\n"
                                elif texto_ocr_limpo.startswith("> ["):
                                    if "OCR indisponível" in texto_ocr_limpo:
                                        self._qtd_alertas_ocr += 1
                                        self._paginas_alerta_ocr.append((pathlib.Path(caminho_pdf).name, i + 1))
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
                        self._qtd_alertas_ocr += 1
                        self._paginas_alerta_ocr.append((pathlib.Path(caminho_pdf).name, i + 1))
                        self._status_arquivo(idx_arq, "aviso", f"Falha recuperada na página {i+1}")
                        texto_extraido = f"\n> [Erro ao processar a página {i+1}: {str(e)}]\n"

                    arquivo_stats["paginas_processadas"] += 1
                    self._stats["paginas_processadas"] += 1
                    if modo_referencia_imagem:
                        self._stats["paginas_referencia"] += 1
                    elif precisa_ocr:
                        self._stats["paginas_ocr"] += 1
                    elif tem_texto_util:
                        self._stats["paginas_texto_nativo"] += 1

                    if gerar_pdf_ocr:
                        img_para_pdf = img_bgr
                        if img_para_pdf is None:
                            img_para_pdf = leitor.extrair_imagem_da_pagina(i)
                        paginas_pdf_ocr.append(
                            {
                                "img_array": img_para_pdf,
                                "texto": texto_ocr_limpo,
                            }
                        )
                    elif escritor is not None:
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
                    if gerar_pdf_ocr:
                        ok_pdf = self._gerar_pdf_pesquisavel_ocr(paginas_pdf_ocr, caminho_saida_pdf_ocr)
                        if ok_pdf:
                            historico_app.adicionar_projeto(pathlib.Path(caminho_pdf).name, caminho_saida_pdf_ocr)
                            saidas_geradas.append(caminho_saida_pdf_ocr)
                        else:
                            self._qtd_alertas_ocr += 1
                    else:
                        historico_app.adicionar_projeto(pathlib.Path(caminho_pdf).name, caminho_saida_md)
                        saidas_geradas.append(caminho_saida_md)

                    if arquivo_stats["paginas_processadas"] == arquivo_stats["paginas_esperadas"]:
                        arquivo_stats["status"] = "concluido"
                        self._stats["arquivos_concluidos"] += 1
                        self._status_arquivo(idx_arq, "concluido")
                    else:
                        arquivo_stats["status"] = "aviso"
                        self._stats["arquivos_com_erro"] += 1
                        self._status_arquivo(idx_arq, "aviso", "Nem todas as páginas foram processadas")
                    self._stats_arquivos.append(arquivo_stats)

            if self.cancelar:
                self.cb_erro("⚠️ Conversão Cancelada pelo usuário.", cancelado=True)
            else:
                self._stats["paginas_com_alerta"] = int(self._qtd_alertas_ocr)
                resumo = {
                    "qtd_alertas_ocr": int(self._qtd_alertas_ocr),
                    "paginas_alerta_ocr": list(self._paginas_alerta_ocr),
                    "usou_ocr": bool(self.usar_ocr),
                    "saidas_geradas": saidas_geradas,
                    "estatisticas": dict(self._stats),
                    "tempo_segundos": round(time.monotonic() - self._inicio_ts, 2),
                    "integridade_ok": self._stats["paginas_processadas"] == self._stats["paginas_total"],
                }
                pasta_manifesto = pathlib.Path(self.pasta_destino) if self.pasta_destino else (pathlib.Path(self.arquivos[0]).parent if self.arquivos else pathlib.Path.cwd())
                manifesto = self._registrar_manifesto(pasta_manifesto, resumo)
                if manifesto:
                    resumo["manifesto"] = manifesto
                log_info(f"Conversão concluída: {self._stats['arquivos_concluidos']}/{self._stats['arquivos_total']} arquivos; {self._stats['paginas_processadas']}/{self._stats['paginas_total']} páginas")
                self.cb_concluido(resumo)

        except Exception as e:
            log_erro("Falha crítica no motor de conversão", e)
            self.cb_erro(f"Erro inesperado:\n{str(e)}")
        finally:
            ocr_engine.finalizar_worker()