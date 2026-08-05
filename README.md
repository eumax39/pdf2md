# PDF2MD_V2

Aplicativo desktop para conversao de PDFs processuais em Markdown, com tres modos de leitura:

- Hibrido: texto nativo + OCR complementar apenas em imagem relevante.
- Forcar OCR: OCR puro, ignorando texto nativo.
- Texto nativo + referencia de imagem: sem OCR, com exportacao de imagens relevantes para PDF unico de referencias.

## Licenca e Uso

Este projeto utiliza licenca proprietaria restritiva. Consulte o arquivo `LICENSE` para os termos completos.

Resumo das regras principais:

- Nao pode ser comercializado.
- Modificacoes sao permitidas apenas para melhorias tecnicas do proprio projeto.
- O projeto e fechado (nao open source).
- Redistribuicao de versoes modificadas depende de autorizacao expressa do titular.

## Build Offline do Executavel

Este projeto foi ajustado para funcionar offline quando empacotado, desde que os modelos do PaddleOCR estejam presentes na maquina de build.

### Pre-requisito

Os modelos do Paddle precisam existir em:

`%USERPROFILE%\.paddlex\official_models`

Na maquina atual, esse cache ja foi detectado e o arquivo `PDF2MD_V2.spec` foi preparado para embuti-lo na distribuicao.

### Gerar o executavel

No PowerShell, dentro da pasta do projeto:

```powershell
.\build_offline.ps1
```

Ou manualmente:

```powershell
python -m pip install --upgrade pyinstaller
python -m PyInstaller --noconfirm .\PDF2MD_V2.spec
```

### Saida

O executavel sera gerado em:

`dist\PDF2MD_V2\PDF2MD_V2.exe`

### Observacoes

- O build usa `onedir`, que e mais estavel para PaddleOCR do que `onefile`.
- O executavel usa os modelos embutidos em `assets/paddlex/official_models` quando existir essa pasta na distribuicao.
- `config.json`, `historico_projetos.json`, `icone.ico` e `logo.png` entram na build.
- Logs e configuracoes passam a funcionar relativos a pasta da aplicacao empacotada.

## Publicacao no Git

Versione no repositorio apenas codigo-fonte, recursos estaticos, documentacao e arquivos de build declarativos.

Deve ir para o Git:

- `main.py`
- pastas `app/`, `core/`, `ocr/`, `tests/`, `assets/`
- `README.md`, `requirements.txt`, `PDF2MD_V2.spec`, `build_offline.ps1`, `.gitignore`, `LICENSE`
- recursos de interface como `icone.ico` e `logo.png`

Nao deve ir para o Git:

- `build/` e `dist/`
- caches (`__pycache__/`, `.pytest_cache/`, arquivos `.pyc`)
- logs e temporarios (`logs/`, `*.log`, `*.tmp`, `*.bak`)
- dados locais de execucao (`historico.db`, `historico_projetos.json` quando for dado local)
- saidas geradas pelo app (`*_referencias_imagens.pdf`, `*_referencias/`)
