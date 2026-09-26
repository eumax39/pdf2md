# publicar_release.py
import os
import sys
import re
import subprocess
import shutil
import pathlib
import time

PYTHON_EXE = r"C:\Users\AB-ADVOGADOS\AppData\Local\Programs\Python\Python311\python.exe"
PROJECT_DIR = pathlib.Path(__file__).parent.resolve()
VERSION_FILE = PROJECT_DIR / "core" / "version.py"
SPEC_FILE = PROJECT_DIR / "PDF2MD_V2.spec"
DIST_DIR = PROJECT_DIR / "dist"
SETUP_ISS = PROJECT_DIR / "PDF2MD_Setup.iss"


def obter_versao_atual():
    if not VERSION_FILE.exists():
        return "2.2.0"
    texto = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', texto)
    return m.group(1) if m else "2.2.0"


def sugerir_proxima_versao(versao):
    partes = versao.split(".")
    if len(partes) == 3 and partes[2].isdigit():
        partes[2] = str(int(partes[2]) + 1)
        return ".".join(partes)
    return versao + ".1"


def atualizar_versao_no_codigo(nova_versao):
    texto = VERSION_FILE.read_text(encoding="utf-8")
    novo_texto = re.sub(r'APP_VERSION\s*=\s*"[^"]+"', f'APP_VERSION = "{nova_versao}"', texto)
    VERSION_FILE.write_text(novo_texto, encoding="utf-8")
    print(f"✅ Versão atualizada para '{nova_versao}' em core/version.py")


def compilar_pyinstaller():
    print("\n📦 [1/4] Gerando executável PyInstaller (--clean)...")
    cmd = [PYTHON_EXE, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_FILE)]
    res = subprocess.run(cmd, cwd=str(PROJECT_DIR))
    if res.returncode != 0:
        raise RuntimeError("Build do PyInstaller falhou.")
    print("✅ Executável gerado com sucesso em dist/PDF2MD_V2/")


def compilar_inno_setup(versao):
    print("\n🛠️ [2/4] Verificando Inno Setup (ISCC.exe)...")
    candidatos = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    iscc_path = None
    for c in candidatos:
        if os.path.exists(c):
            iscc_path = c
            break

    if SETUP_ISS.exists():
        texto_iss = SETUP_ISS.read_text(encoding="utf-8")
        texto_iss = re.sub(r'AppVersion=.*', f'AppVersion={versao}', texto_iss)
        SETUP_ISS.write_text(texto_iss, encoding="utf-8")

    if iscc_path and SETUP_ISS.exists():
        print(f"Compilando instalador com {iscc_path}...")
        res = subprocess.run([iscc_path, str(SETUP_ISS)], cwd=str(PROJECT_DIR))
        if res.returncode == 0:
            print("✅ Instalador PDF2MD_Setup.exe gerado com sucesso em dist/")
            return True

    print("⚠️ ISCC.exe não encontrado em caminhos padrão. Gerando pacote ZIP portable...")
    cmd_zip = f"Compress-Archive -Path '{DIST_DIR}\\PDF2MD_V2' -DestinationPath '{DIST_DIR}\\PDF2MD_V2_portable.zip' -Force"
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd_zip], cwd=str(PROJECT_DIR))
    print("✅ ZIP portable gerado em dist/PDF2MD_V2_portable.zip")
    return False


def enviar_git(versao, notas=""):
    print("\n🐙 [3/4] Atualizando o repositório Git e enviando Tag...")
    subprocess.run(["git", "add", "."], cwd=str(PROJECT_DIR))
    msg = f"Release v{versao}" + (f" - {notas}" if notas else "")
    subprocess.run(["git", "commit", "-m", msg], cwd=str(PROJECT_DIR))
    subprocess.run(["git", "push", "origin", "main"], cwd=str(PROJECT_DIR))

    tag = f"v{versao}"
    # Remove a tag local se já existir
    subprocess.run(["git", "tag", "-d", tag], cwd=str(PROJECT_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "tag", "-a", tag, "-m", msg], cwd=str(PROJECT_DIR))
    subprocess.run(["git", "push", "origin", tag], cwd=str(PROJECT_DIR))
    print(f"✅ Tag {tag} enviada para o GitHub!")


def publicar_release_github(versao, notas=""):
    print("\n🚀 [4/4] Publicando Release no GitHub...")
    tag = f"v{versao}"
    setup_exe = DIST_DIR / "PDF2MD_Setup.exe"
    zip_file = DIST_DIR / "PDF2MD_V2_portable.zip"

    files_to_upload = []
    if setup_exe.exists():
        files_to_upload.append(str(setup_exe))
    if zip_file.exists():
        files_to_upload.append(str(zip_file))

    gh_path = shutil.which("gh")
    if gh_path and files_to_upload:
        print("Usando GitHub CLI (gh) para criar o Release automaticamente...")
        cmd = [gh_path, "release", "create", tag] + files_to_upload + ["--title", f"Versão {versao}", "--notes", notas or f"Release da versão {versao}"]
        res = subprocess.run(cmd, cwd=str(PROJECT_DIR))
        if res.returncode == 0:
            print(f"🎉 Release {tag} publicado com sucesso no GitHub!")
            return

    print(f"\n========================================================")
    print(f"🎉 PROCESSO CONCLUÍDO COM SUCESSO!")
    print(f"Versão: {versao}")
    print(f"Tag Git: {tag}")
    if setup_exe.exists():
        print(f"Instalador: {setup_exe}")
    if zip_file.exists():
        print(f"ZIP Portable: {zip_file}")
    print(f"Para anexar o instalador ao Release no GitHub, acesse:")
    print(f"👉 https://github.com/eumax39/pdf2md/releases/new?tag={tag}")
    print(f"========================================================\n")


def main():
    versao_atual = obter_versao_atual()
    versao_sugerida = sugerir_proxima_versao(versao_atual)

    print("========================================================")
    print("      AUTOMAÇÃO DE RELEASE E BUILD DO PDF2MD")
    print("========================================================")
    print(f"Versão atual no código: {versao_atual}")

    if len(sys.argv) > 1:
        nova_versao = sys.argv[1].strip()
    else:
        entrada = input(f"Informe a nova versão [{versao_sugerida}]: ").strip()
        nova_versao = entrada if entrada else versao_sugerida

    notas = input("Notas da versão / resumo das mudanças (opcional): ").strip()

    atualizar_versao_no_codigo(nova_versao)
    compilar_pyinstaller()
    compilar_inno_setup(nova_versao)
    enviar_git(nova_versao, notas)
    publicar_release_github(nova_versao, notas)


if __name__ == "__main__":
    main()
