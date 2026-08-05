# PDF2MD_V2

Aplicativo desktop para conversao de PDFs processuais em Markdown.

## Modos de Conversao

- Hibrido: texto nativo + OCR complementar em imagem relevante.
- Forcar OCR: OCR puro, ignorando texto nativo.
- Texto nativo + referencia de imagem: sem OCR, com referencias de imagens relevantes.

## Requisitos

- Python 3.11+
- Dependencias em `requirements.txt`

## Como Executar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Licenca

Este projeto possui licenca proprietaria restritiva.
Veja os termos completos no arquivo `LICENSE`.

Regras principais:

- Nao pode ser comercializado.
- Modificacoes apenas para melhorias tecnicas do proprio projeto.
- Projeto fechado (codigo proprietario).
- Redistribuicao de versoes modificadas somente com autorizacao expressa.
