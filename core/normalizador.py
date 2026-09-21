import re


class NormalizadorTextoJuridico:
    """
    Normalizador e Formatador de Texto Jurídico em Markdown.

    Recursos:
    1. PRESERVA 100% dos IDs e números de documentos do PJe (ex: Id. 98032470, Num. 12345 - Pág. 1)
       para citação processual pelos advogados nas peças.
    2. Executa des-hifenização de quebras de margem e junção de frases.
    3. Formata a hierarquia jurídica (H1 para endereçamento, H2 para seções, > para ementas de julgados).
    4. Substitui rótulos verbosos de IA por separadores discretos e normaliza espaçamentos.
    """

    # Expressão para detectar títulos de seções judiciais típicas
    PADRAO_SECAO_JURIDICA = re.compile(
        r"^(I{1,3}|IV|V|VI|VII|VIII|IX|X|\d+)?[\.\-\s]*"
        r"(DOS FATOS|DO DIREITO|DOS PEDIDOS|DA TUTELA DE URGÊNCIA|DA TUTELA ANTECIPADA|"
        r"DA SÍNTESE DO PROCESSO|DA PRELIMINAR|DAS PRELIMINARES|DO MÉRITO|DO MERITO|DOS REQUERIMENTOS|"
        r"DA FUNDAMENTAÇÃO|DA TEMPESTIVIDADE|DA GRATUIDADE DA JUSTIÇA|PRELIMINARMENTE)$",
        re.IGNORECASE,
    )

    # Expressão para ementas de jurisprudência (ex: PROCESSUAL CIVIL. APELAÇÃO CÍVEL...)
    PADRAO_EMENTA_JURISPRUDENCIA = re.compile(
        r"^(PROCESSUAL CIVIL|DIREITO CIVIL|DIREITO PROCESSUAL CIVIL|DIREITO CONSUMIDOR|"
        r"AGRAVO DE INSTRUMENTO|APELAÇÃO CÍVEL|RECURSO ESPECIAL|HABEAS CORPUS|"
        r"EMBARGOS DE DECLARAÇÃO|RECURSO INNOMINADO)[\.\s]",
        re.IGNORECASE,
    )

    def normalizar_pagina(self, texto: str) -> str:
        if not texto or not texto.strip():
            return ""

        linhas = texto.splitlines()
        linhas_processadas = []

        for i, linha in enumerate(linhas):
            ln = linha.rstrip()

            # 1. Limpeza de rótulos verbosos de IA / OCR (Substitui por separadores discretos)
            if ln.startswith("> 🤖 **[IA - OCR") or ln.startswith("> [Página ") or ln.startswith("> 📸 [Imagem na"):
                if "OCR indisponível" in ln or "Erro" in ln:
                    linhas_processadas.append(ln)
                else:
                    linhas_processadas.append("\n---\n")
                continue

            # 2. Formatação discreta de IDs de documento PJe (PRESERVA O ID PARA CITAÇÃO PROCESSUAL!)
            if re.search(r"Num\.\s*\d+.*Pág\.\s*\d+|Assinado eletronicamente por:", ln, flags=re.IGNORECASE):
                linhas_processadas.append(f"> *[{ln.strip()}]*")
                continue

            # 3. Formatação de seções judiciais em H2 (## DOS FATOS)
            if self.PADRAO_SECAO_JURIDICA.match(ln.strip()):
                linhas_processadas.append(f"\n## {ln.strip().upper()}\n")
                continue

            # 4. Formatação de Endereçamento Inicial (# EXCELENTÍSSIMO...)
            if ln.strip().startswith("EXCELENTÍSSIMO") or ln.strip().startswith("EXCELENTISSIMO"):
                linhas_processadas.append(f"\n# {ln.strip().upper()}\n")
                continue

            # 5. Formatação de Ementas de Jurisprudência em citação ( > **PROCESSUAL CIVIL...** )
            if self.PADRAO_EMENTA_JURISPRUDENCIA.match(ln.strip()):
                linhas_processadas.append(f"\n> **{ln.strip()}**")
                continue

            linhas_processadas.append(ln)

        texto_intermediario = "\n".join(linhas_processadas)

        # 6. Des-hifenização de final de linha (ex: "in-\nfrutífera" -> "infrutífera")
        texto_deshifenizado = re.sub(
            r"(\b[a-zA-ZáàâãéèêíïóôõúüçÁÀÂÃÉÈÊÍÏÓÔÕÚÜÇ]+)\-\n([a-zA-ZáàâãéèêíïóôõúüçÁÀÂÃÉÈÊÍÏÓÔÕÚÜÇ]+\b)",
            r"\1\2",
            texto_intermediario,
        )

        # 7. Compressão de linhas em branco excessivas (máximo 2 consecutivas)
        texto_final = re.sub(r"\n{3,}", "\n\n", texto_deshifenizado).strip()

        return texto_final
