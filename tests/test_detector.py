import io
import pytest
import numpy as np
from PIL import Image, ImageDraw
import fitz

from ocr.detector import DetectorVisual


def criar_imagem_mock(cor=(255, 0, 0), tamanho=(300, 300), modo="RGB"):
    img = Image.new(modo, tamanho, cor)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def criar_imagem_evidencia_complexa(tamanho=(400, 400)):
    img = Image.new("RGB", tamanho, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Adiciona formas e textos contrastantes para simular um print/documento
    draw.rectangle([20, 20, 380, 100], fill=(20, 50, 120))
    draw.rectangle([20, 120, 380, 380], fill=(240, 240, 240), outline=(0, 0, 0))
    draw.line([30, 150, 350, 150], fill=(0, 0, 0), width=2)
    draw.line([30, 200, 350, 200], fill=(200, 0, 0), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def criar_imagem_marca_dagua_clara(tamanho=(400, 400)):
    # Marca d'água cinza clara semi-transparente
    img = Image.new("RGB", tamanho, (230, 230, 230))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 350, 350], fill=(238, 238, 238))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_detector_inicializacao():
    detector = DetectorVisual()
    assert detector.total_paginas == 0
    assert len(detector.hashes_repetidos) == 0


def test_detector_descarte_repeticao_inter_paginas():
    # Cria PDF em memória com a mesma imagem em 2 páginas (papel timbrado)
    doc = fitz.open()
    img_bytes = criar_imagem_mock(cor=(150, 20, 20), tamanho=(200, 100))

    page1 = doc.new_page(width=595, height=842)
    page1.insert_image(fitz.Rect(10, 10, 210, 110), stream=img_bytes)

    page2 = doc.new_page(width=595, height=842)
    page2.insert_image(fitz.Rect(10, 10, 210, 110), stream=img_bytes)

    detector = DetectorVisual()
    detector.indexar_documento(doc)

    assert len(detector.hashes_repetidos) > 0

    # Imagem repetida deve ser recusada
    relevante = detector.eh_imagem_relevante(
        imagem_bytes=img_bytes,
        bbox=(10.0, 10.0, 210.0, 110.0),
        largura_pagina=595.0,
        altura_pagina=842.0,
        numero_pagina=0,
    )
    assert relevante is False
    doc.close()


def test_detector_aceita_evidencia_unica():
    detector = DetectorVisual()
    img_evidencia = criar_imagem_evidencia_complexa()

    # Imagem no meio da folha com detalhes visuais e sem estar no índice repetitivo
    relevante = detector.eh_imagem_relevante(
        imagem_bytes=img_evidencia,
        bbox=(50.0, 200.0, 450.0, 600.0),
        largura_pagina=595.0,
        altura_pagina=842.0,
        numero_pagina=0,
    )
    assert relevante is True


def test_detector_descarte_marca_dagua_clara():
    detector = DetectorVisual()
    img_watermark = criar_imagem_marca_dagua_clara()

    # Marca d'água no centro da página
    relevante = detector.eh_imagem_relevante(
        imagem_bytes=img_watermark,
        bbox=(50.0, 200.0, 450.0, 600.0),
        largura_pagina=595.0,
        altura_pagina=842.0,
        numero_pagina=0,
    )
    assert relevante is False
