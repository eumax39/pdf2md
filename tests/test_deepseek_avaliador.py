import pytest

from core.avaliador_qualidade import AvaliadorQualidadeTexto
from core.deepseek import ClienteDeepSeek


def test_avaliador_qualidade_texto_limpo():
    avaliador = AvaliadorQualidadeTexto(limiar_padrao=0.80)
    texto_juridico_limpo = (
        "EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 7ª VARA CÍVEL DA COMARCA DE TERESINA - PI. "
        "Processo nº: 0862113-73.2025.8.18.0140. ANTARES COMERCIO ATACADISTA LTDA, já devidamente qualificada "
        "nos autos do processo em epígrafe, que move em face de D. B. OLIVEIRA IMOVEIS LTDA e outros, "
        "vem, respeitosamente, por intermédio de seu advogado que esta subscreve, expor e requerer o que se segue."
    )

    score = avaliador.calcular_score(texto_juridico_limpo)
    assert score >= 0.80
    assert avaliador.eh_texto_de_alta_qualidade(texto_juridico_limpo) is True


def test_avaliador_qualidade_texto_ruidoso_ocr():
    avaliador = AvaliadorQualidadeTexto(limiar_padrao=0.80)
    texto_ocr_ruidoso = (
        "E X C E L E N T l S S l M O   S E N H O R   J U l Z ¶§þ½\n"
        "Pr0c3ss0 n°: 0862113-73.2025.8.18.0140\n"
        "ANTARES C0MERClO ATACADlSTA LTDA corn base na\n"
        "a t e n t a t i v a   d e   c i t a c a o   d a   e m p r e s a\n"
        "|\\_~`^<>[]{}*#+=@"
    )

    score = avaliador.calcular_score(texto_ocr_ruidoso)
    assert score < 0.80
    assert avaliador.eh_texto_de_alta_qualidade(texto_ocr_ruidoso) is False


def test_cliente_deepseek_init():
    cliente = ClienteDeepSeek(api_key="sk-test-key")
    assert cliente.api_key == "sk-test-key"
    assert cliente.model == "deepseek-chat"
