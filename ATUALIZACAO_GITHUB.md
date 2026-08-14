# Atualização automática pelo GitHub Releases

A versão do aplicativo é definida somente em `core/version.py`.

## Publicação da versão 2.0.0

1. Gere o executável com o fluxo atual do PyInstaller.
2. Gere o instalador pelo Inno Setup.
3. No GitHub, crie um **Release** com a tag `v2.0.0`.
4. Anexe ao Release o instalador `.exe` criado pelo Inno Setup.
5. Preferencialmente use o nome `PDF2MD_Setup.exe` (nomes contendo `Setup`, `Installer` ou `Instalador` também são reconhecidos).
6. Publique o Release como estável, não como draft/prerelease.

A build 2.0.0 não tentará instalar o próprio release 2.0.0. A primeira atualização automática real deverá possuir uma versão superior, por exemplo `v2.0.1`.

## Próximas versões

Antes de gerar uma nova build:

```python
# core/version.py
APP_VERSION = "2.0.1"
```

Depois publique um Release com a tag correspondente:

```text
v2.0.1
```

## Funcionamento

Ao iniciar a versão empacotada pelo PyInstaller, o programa consulta em segundo plano o último GitHub Release estável. Se a versão remota for superior, o usuário recebe o aviso de atualização.

Se aceitar:

- o instalador é baixado para a pasta temporária do Windows;
- o tamanho do asset é conferido;
- quando o GitHub fornecer SHA-256 (`digest`), o hash também é validado;
- o Inno Setup é iniciado em modo silencioso;
- o PDF2MD é encerrado pela thread principal para permitir a substituição dos arquivos.

## Recomendações para os Releases

Mantenha apenas o instalador Inno Setup como `.exe` do Release ou use um nome contendo `Setup`/`Installer`. Outros arquivos podem ser ZIP, checksums, notas etc.
