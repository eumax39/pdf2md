import hashlib
import io
from typing import Dict, Set, Tuple, Optional
import numpy as np
from PIL import Image

from core.utils import log_erro, log_aviso


class DetectorVisual:
    """
    Detector visual inteligente de imagens relevantes em PDFs processuais e petições.
    Filtra logotipos repetitivos, papéis timbrados, marcas d'água semi-transparentes,
    selos PJe, QR codes de validação e barras decorativas.
    """

    def __init__(self):
        self.hashes_repetidos: Set[str] = set()
        self.total_paginas: int = 0

    def indexar_documento(self, doc_fitz) -> None:
        """
        Scaneia previamente todo o arquivo PDF para identificar assinaturas/fingerprints
        de imagens que se repetem em 2 ou mais páginas (papel timbrado, logos, marcas d'água).
        """
        try:
            self.total_paginas = len(doc_fitz)
            if self.total_paginas <= 1:
                return

            paginas_por_hash: Dict[str, Set[int]] = {}

            for idx_pagina in range(self.total_paginas):
                pagina = doc_fitz.load_page(idx_pagina)
                # Otimização: se a página não tem imagens embutidas, pula a análise pesada de dicionário
                try:
                    if not pagina.get_images(full=True):
                        continue
                except Exception:
                    pass

                dados = pagina.get_text("dict") or {}
                blocos = dados.get("blocks") or []

                for bloco in blocos:
                    if bloco.get("type") != 1:  # 1 = Bloco de imagem
                        continue

                    imagem_bytes = bloco.get("image")
                    if not imagem_bytes:
                        xref = bloco.get("xref")
                        if xref:
                            try:
                                extraida = doc_fitz.extract_image(int(xref))
                                imagem_bytes = (extraida or {}).get("image")
                            except Exception:
                                imagem_bytes = None

                    if not imagem_bytes:
                        continue

                    fp = self._calcular_fingerprint(imagem_bytes)
                    if fp:
                        if fp not in paginas_por_hash:
                            paginas_por_hash[fp] = set()
                        paginas_por_hash[fp].add(idx_pagina)

            # Imagens presentes em 2 ou mais páginas são classificadas como template repetitivo
            self.hashes_repetidos = {
                fp for fp, pgs in paginas_por_hash.items() if len(pgs) >= 2
            }
        except Exception as e:
            log_erro("Erro ao indexar documento para fingerprint visual", e)

    def _calcular_fingerprint(self, imagem_bytes: bytes) -> Optional[str]:
        """
        Gera um perceptual hash (dHash 16x16) rápido da imagem para comparar
        semelhança visual entre páginas, ignorando diferenças irrelevantes de compressão.
        """
        try:
            with Image.open(io.BytesIO(imagem_bytes)) as img:
                img_l = img.convert("L").resize((17, 16), Image.Resampling.BILINEAR)
                pixels = np.array(img_l, dtype=np.int16)
                diff = pixels[:, 1:] > pixels[:, :-1]
                return hashlib.sha1(diff.tobytes()).hexdigest()
        except Exception:
            try:
                return hashlib.sha1(imagem_bytes).hexdigest()
            except Exception:
                return None

    def eh_imagem_relevante(
        self,
        imagem_bytes: bytes,
        bbox: Tuple[float, float, float, float],
        largura_pagina: float,
        altura_pagina: float,
        numero_pagina: int = 0,
    ) -> bool:
        """
        Decide se uma imagem é um documento/prova real (print, recibo, foto, RG, certidão)
        ou se deve ser descartada (logo, marca d'água, rodapé, barra, selo).
        """
        if not imagem_bytes:
            return False

        # -------------------------------------------------------------
        # Camada 1: Fingerprint Inter-Páginas (Deduplicação de Modelo)
        # -------------------------------------------------------------
        fp = self._calcular_fingerprint(imagem_bytes)
        if fp and fp in self.hashes_repetidos:
            return False

        # -------------------------------------------------------------
        # Camada 2: Análise Geométrica e Margens (Zoneamento & Proporção)
        # -------------------------------------------------------------
        x0, y0, x1, y1 = bbox
        largura_img = max(1.0, float(x1 - x0))
        altura_img = max(1.0, float(y1 - y0))
        area_pagina = max(1.0, float(largura_pagina * altura_pagina))
        area_ratio = (largura_img * altura_img) / area_pagina

        rel_x0 = x0 / max(1.0, largura_pagina)
        rel_x1 = x1 / max(1.0, largura_pagina)
        rel_y0 = y0 / max(1.0, altura_pagina)
        rel_y1 = y1 / max(1.0, altura_pagina)

        largura_rel = largura_img / max(1.0, largura_pagina)
        altura_rel = altura_img / max(1.0, altura_pagina)
        aspecto = largura_img / altura_img

        # Ignora barras finas de cabeçalho/divisor (largas na horizontal, finas na vertical)
        if largura_rel >= 0.50 and altura_rel <= 0.08:
            return False

        # Ignora selos laterais verticais finos em margens (ex: PJe nas bordas esquerda/direita)
        if (rel_x0 <= 0.10 or rel_x1 >= 0.90) and altura_rel >= 0.40 and largura_rel <= 0.12:
            return False

        # Ignora imagens minúsculas (ícones de telefone, e-mail, QR codes pequenos em cantos)
        if area_ratio < 0.03:
            return False

        # Ignora logos/ícones situados estritamente na faixa superior do cabeçalho ou inferior do rodapé
        faixa_topo = rel_y0 <= 0.14
        faixa_rodape = rel_y1 >= 0.86
        if (faixa_topo or faixa_rodape) and area_ratio <= 0.18 and (aspecto >= 2.5 or aspecto <= 0.40 or area_ratio < 0.08):
            return False

        # -------------------------------------------------------------
        # Camada 3: Filtro de Marca d'Água Semi-transparente de Fundo
        # -------------------------------------------------------------
        try:
            with Image.open(io.BytesIO(imagem_bytes)) as img:
                dim_w, dim_h = img.size
                if dim_w < 100 or dim_h < 100:
                    return False

                # Converte para L para medir brilho e variação
                img_l = img.convert("L")
                img_small = img_l.resize((200, 200), Image.Resampling.BILINEAR)
                arr = np.array(img_small, dtype=np.float32)

                brilho_medio = float(arr.mean())
                std_brilho = float(arr.std())
                rng_brilho = float(arr.max() - arr.min())

                # Marca d'água central transparente: tom cinza muito claro / quase branco (brilho > 215)
                # com baixo contraste ou baixíssima variação interna
                if area_ratio >= 0.12 and brilho_medio >= 215.0 and std_brilho < 32.0:
                    return False

                if area_ratio >= 0.25 and brilho_medio >= 200.0 and std_brilho < 25.0 and rng_brilho < 100.0:
                    return False

                # -------------------------------------------------------------
                # Camada 4: Entropia Visual & Densidade de Bordas (Classificador de Evidência)
                # -------------------------------------------------------------
                gx = np.abs(np.diff(arr, axis=1))
                gy = np.abs(np.diff(arr, axis=0))
                bordas = ((gx > 18).sum() + (gy > 18).sum())
                total_pixels = max(1, gx.size + gy.size)
                densidade_bordas = float(bordas) / float(total_pixels)

                # Se a imagem tiver área média/grande, mas quase NENHUMA borda interna (desenho simples/fundo sólido/logo)
                if area_ratio >= 0.10 and std_brilho < 18.0 and densidade_bordas < 0.020:
                    return False

        except Exception as e:
            log_aviso(f"Falha na verificação visual profunda da imagem: {type(e).__name__}")
            if faixa_topo or faixa_rodape:
                return False

        # Se passou por todas as camadas de filtro, é uma IMAGEM RELEVANTE DE CONTEÚDO
        return True
