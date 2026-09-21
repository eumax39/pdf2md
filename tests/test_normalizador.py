import pytest

from core.normalizador import NormalizadorTextoJuridico


def test_normalizador_preserva_ids_pje():
    normalizador = NormalizadorTextoJuridico()
    texto = "Num. 98032470 - Pág. 1\nAssinado eletronicamente por: RANIERY ALMEIDA"
    resultado = normalizador.normalizar_pagina(texto)

    # PRESERVAÇÃO TOTAL: Garantir que os IDs do PJe continuam presentes para citação pelos advogados
    assert "98032470" in resultado
    assert "Assinado eletronicamente por" in resultado
    assert "> *[" in resultado  # Formatação discreta em citação/itálico


def test_normalizador_deshifenizacao():
    normalizador = NormalizadorTextoJuridico()
    texto = 'a citação da empresa ré, restou in-\nfrutífera pelo motivo "MUDOU-SE".'
    resultado = normalizador.normalizar_pagina(texto)

    assert "infrutífera" in resultado
    assert "in-\nfrutífera" not in resultado


def test_normalizador_hierarquia_juridica():
    normalizador = NormalizadorTextoJuridico()
    texto = (
        "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO\n"
        "DOS FATOS\n"
        "O autor ajuizou a ação...\n"
        "DO DIREITO\n"
        "PROCESSUAL CIVIL. APELAÇÃO CÍVEL. CITAÇÃO POSTAL."
    )
    resultado = normalizador.normalizar_pagina(texto)

    assert "# EXCELENTÍSSIMO" in resultado
    assert "## DOS FATOS" in resultado
    assert "## DO DIREITO" in resultado
    assert "> **PROCESSUAL CIVIL" in resultado


def test_normalizador_limpeza_rotulos_ia():
    normalizador = NormalizadorTextoJuridico()
    texto = "> 🤖 **[IA - OCR complementar Pág. 2]**\n\nConteúdo lido..."
    resultado = normalizador.normalizar_pagina(texto)

    assert "---" in resultado
    assert "Conteúdo lido..." in resultado
