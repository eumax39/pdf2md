import re
from typing import Tuple


class AvaliadorQualidadeTexto:
    """
    Avaliador de Qualidade de Texto Extraído / OCR.
    Calcula um Score de 0.0 (0%) a 1.0 (100%) indicando a fidelidade e legibilidade
    do texto em português jurídico.
    """

    # Expressão regular para palavras válidas em português (incluindo acentuadas e termos jurídicos)
    PADRAO_PALAVRA_VALIDA = re.compile(
        r"^[a-zA-ZáàâãéèêíïóôõúüçÁÀÂÃÉÈÊÍÏÓÔÕÚÜÇ0-9\.\,\;\:\-\/\(\)\°\º\ª\$]+$"
    )

    # Símbolos estranhos frequentemente gerados por falha/ruído de OCR
    SIMBOLOS_RUIDO = set("¶§þ½¿|\\_~`^<>[]{}*#+=@")

    def __init__(self, limiar_padrao: float = 0.80):
        self.limiar_padrao = float(limiar_padrao)

    def calcular_score(self, texto: str) -> float:
        """
        Calcula o Score de Qualidade do texto de 0.0 a 1.0.
        """
        if not texto or not texto.strip():
            return 0.0

        texto_limpo = texto.strip()
        tamanho_total = len(texto_limpo)
        if tamanho_total < 15:
            return 0.3  # Texto extremamente curto / suspeito

        palavras = texto_limpo.split()
        if not palavras:
            return 0.0

        # 1. Taxa de palavras válidas
        palavras_validas = 0
        for p in palavras:
            p_clean = p.strip(".,;:()[]{}'\"")
            if p_clean and self.PADRAO_PALAVRA_VALIDA.match(p_clean):
                # Se for uma palavra com ao menos 1 letra/número e sem lixo no meio
                if any(c.isalnum() for c in p_clean):
                    palavras_validas += 1

        taxa_palavras_validas = palavras_validas / max(1, len(palavras))

        # 2. Penalidade por densidade de caracteres de ruído
        qtd_ruido = sum(1 for c in texto_limpo if c in self.SIMBOLOS_RUIDO or ord(c) < 32 or ord(c) > 1000)
        penalidade_ruido = min(1.0, qtd_ruido / max(1, tamanho_total * 0.08))

        # 3. Penalidade por anomalia de estrutura (palavras coladas gigantes ou letras isoladas repetidas)
        qtd_palavras_gigantes = sum(1 for p in palavras if len(p) > 55)
        qtd_letras_isoladas = sum(1 for p in palavras if len(p) == 1 and p.isalpha())
        proporcao_isoladas = qtd_letras_isoladas / max(1, len(palavras))

        penalidade_estrutura = 0.0
        if qtd_palavras_gigantes > 0:
            penalidade_estrutura += 0.3
        if proporcao_isoladas > 0.25:
            penalidade_estrutura += 0.3

        penalidade_estrutura = min(1.0, penalidade_estrutura)

        # 4. Cálculo final ponderado
        score = (taxa_palavras_validas * 0.65) + ((1.0 - penalidade_ruido) * 0.25) + ((1.0 - penalidade_estrutura) * 0.10)
        return max(0.0, min(1.0, round(score, 4)))

    def eh_texto_de_alta_qualidade(self, texto: str, limiar: float = None) -> bool:
        """
        Retorna True se o score do texto for maior ou igual ao limiar (ex: 0.80 = 80%).
        """
        if limiar is None:
            limiar = self.limiar_padrao

        score = self.calcular_score(texto)
        return score >= float(limiar)
