import re
import pathlib
import io

import fitz
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
                import pymupdf4llm

                markdown = pymupdf4llm.to_markdown(self.doc, pages=[numero_pagina], force_text=True)
                if markdown and str(markdown).strip():
                    return str(markdown).strip()
            except Exception as e:
                log_erro(f"Fallback pymupdf4llm indisponível na página {numero_pagina}", e)
                pass

            return ""
        except Exception as e:
            log_erro(f"Erro ao extrair texto nativo da página {numero_pagina}", e)
            return ""

    def extrair_texto_nativo_estrito(self, numero_pagina):
        """Extrai somente texto nativo real da página, sem fallback externo."""
        try:
            pagina = self.doc.load_page(numero_pagina)
            return (pagina.get_text("text") or "").strip()
        except Exception as e:
            log_erro(f"Erro ao extrair texto nativo estrito da página {numero_pagina}", e)
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

    def pagina_tem_imagem(self, numero_pagina):
        """Retorna True quando a página contém ao menos uma imagem embutida."""
        try:
            pagina = self.doc.load_page(numero_pagina)
            imagens = pagina.get_images(full=True)
            return len(imagens) > 0
        except Exception as e:
            log_erro(f"Erro ao inspecionar imagens da página {numero_pagina}", e)
            return False

    def _eh_imagem_irrelevante(self, bbox, largura_pagina, altura_pagina):
        x0, y0, x1, y1 = bbox
        largura = max(1.0, float(x1 - x0))
        altura = max(1.0, float(y1 - y0))
        area = largura * altura
        area_pagina = max(1.0, float(largura_pagina * altura_pagina))
        area_ratio = area / area_pagina
        aspecto = largura / altura

        min_area_ratio = float(config_app.get("imagem_ref_min_area_ratio") or 0.04)
        if area_ratio < min_area_ratio:
            return True

        margem_x = largura_pagina * 0.25
        margem_y = altura_pagina * 0.25
        centro_x = (x0 + x1) / 2.0
        centro_y = (y0 + y1) / 2.0

        canto_superior_esquerdo = centro_x <= margem_x and centro_y <= margem_y
        canto_superior_direito = centro_x >= (largura_pagina - margem_x) and centro_y <= margem_y
        canto_inferior_esquerdo = centro_x <= margem_x and centro_y >= (altura_pagina - margem_y)
        canto_inferior_direito = centro_x >= (largura_pagina - margem_x) and centro_y >= (altura_pagina - margem_y)
        perto_canto = (
            canto_superior_esquerdo
            or canto_superior_direito
            or canto_inferior_esquerdo
            or canto_inferior_direito
        )

        # QR code pequeno em canto.
        if perto_canto and 0.85 <= aspecto <= 1.15 and area_ratio < 0.10:
            return True

        # Logo/faixa pequena em canto.
        if perto_canto and area_ratio < 0.10 and (aspecto >= 3.0 or aspecto <= 0.33):
            return True

        largura_rel = largura / max(1.0, largura_pagina)
        altura_rel = altura / max(1.0, altura_pagina)
        faixa_topo = y0 <= (altura_pagina * 0.18)
        faixa_rodape = y1 >= (altura_pagina * 0.82)

        # Ignora faixas institucionais largas no topo/rodapé (logos e barras decorativas).
        if (faixa_topo or faixa_rodape) and largura_rel >= 0.75 and altura_rel <= 0.22 and area_ratio <= 0.20:
            return True

        # Ignora selos/retângulos verticais de margem com pouca área útil.
        if (centro_x <= margem_x or centro_x >= (largura_pagina - margem_x)) and altura_rel >= 0.50 and largura_rel <= 0.22 and area_ratio <= 0.20:
            return True

        return False

    def _imagem_parece_template(self, imagem_bytes, bbox, largura_pagina, altura_pagina):
        """Detecta papéis timbrados/fundos de baixa complexidade visual (não evidência)."""
        try:
            with Image.open(io.BytesIO(imagem_bytes)) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                # Reduz custo dos cálculos de textura.
                img_l = img.convert("L")
                img_l.thumbnail((320, 320), Image.Resampling.BILINEAR)

                arr = np.array(img_l, dtype=np.float32)
                if arr.size == 0:
                    return False

                std = float(arr.std())
                rng = float(arr.max() - arr.min())

                gx = np.abs(np.diff(arr, axis=1))
                gy = np.abs(np.diff(arr, axis=0))
                bordas = ((gx > 18).sum() + (gy > 18).sum())
                total = max(1, gx.size + gy.size)
                densidade_borda = float(bordas) / float(total)

            x0, y0, x1, y1 = bbox
            largura = max(1.0, float(x1 - x0))
            altura = max(1.0, float(y1 - y0))
            area_ratio = (largura * altura) / max(1.0, float(largura_pagina * altura_pagina))

            # Fundo/timbrado grande, baixo contraste e pouca borda (como os exemplos enviados).
            if area_ratio >= 0.30 and std < 22.0 and rng < 110.0 and densidade_borda < 0.035:
                return True

            # Blocos médios com pouco detalhe visual também tendem a ser arte decorativa.
            if area_ratio >= 0.12 and std < 16.0 and densidade_borda < 0.025:
                return True

            return False
        except Exception:
            return False

    def extrair_imagens_relevantes(self, numero_pagina):
        """Extrai imagens relevantes da página, ignorando logos/QRs pequenos de cabeçalho/rodapé."""
        try:
            pagina = self.doc.load_page(numero_pagina)
            dados = pagina.get_text("dict") or {}
            blocos = dados.get("blocks") or []

            largura_pagina = float(pagina.rect.width)
            altura_pagina = float(pagina.rect.height)

            imagens = []
            for bloco in blocos:
                if bloco.get("type") != 1:
                    continue

                bbox = bloco.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue

                if self._eh_imagem_irrelevante(bbox, largura_pagina, altura_pagina):
                    continue

                imagem_bytes = bloco.get("image")
                if not imagem_bytes:
                    xref = bloco.get("xref")
                    if xref:
                        try:
                            extraida = self.doc.extract_image(int(xref))
                            imagem_bytes = (extraida or {}).get("image")
                        except Exception:
                            imagem_bytes = None

                if not imagem_bytes:
                    continue

                # Valida se o conteúdo é imagem legível.
                try:
                    with Image.open(io.BytesIO(imagem_bytes)) as img:
                        largura_img, altura_img = img.size
                    if largura_img < 180 or altura_img < 180:
                        continue
                except Exception:
                    continue

                if self._imagem_parece_template(imagem_bytes, bbox, largura_pagina, altura_pagina):
                    continue

                imagens.append({"bytes": imagem_bytes, "bbox": bbox})

            return imagens
        except Exception as e:
            log_erro(f"Erro ao extrair imagens relevantes da página {numero_pagina}", e)
            return []

    def extrair_imagem_da_pagina(self, numero_pagina, dpi_override=None):
        try:
            pagina = self.doc.load_page(numero_pagina)
            if dpi_override is not None:
                dpi = int(dpi_override)
            else:
                dpi = int(config_app.get("dpi_leitura") or 120)

            dpi = max(90, min(300, dpi))
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

    def exportar_pagina_como_pdf(self, numero_pagina, caminho_saida):
        """Exporta uma única página do PDF original para um novo PDF."""
        doc_saida = None
        try:
            caminho = pathlib.Path(caminho_saida)
            caminho.parent.mkdir(parents=True, exist_ok=True)

            doc_saida = fitz.open()
            doc_saida.insert_pdf(self.doc, from_page=numero_pagina, to_page=numero_pagina)
            doc_saida.save(str(caminho))
            return str(caminho)
        except Exception as e:
            log_erro(f"Erro ao exportar a página {numero_pagina} para PDF separado", e)
            return None
        finally:
            if doc_saida is not None:
                doc_saida.close()

    def fechar(self):
        self.doc.close()