import json
import shutil
from datetime import datetime

from core.utils import get_app_root, get_data_root


def _obter_caminho_historico():
    caminho_data = get_data_root() / "historico_projetos.json"
    if not caminho_data.exists():
        caminho_app = get_app_root() / "historico_projetos.json"
        if caminho_app.exists():
            try:
                shutil.copy2(caminho_app, caminho_data)
            except Exception:
                pass
    return caminho_data


class HistoricoApp:
    @property
    def arquivo_memoria(self):
        return _obter_caminho_historico()

    def adicionar_projeto(self, nome_pdf, caminho_md):
        historico = self.obter_todos()
        
        # Evita duplicar se o mesmo projeto for salvo duas vezes seguidas
        for proj in historico:
            if isinstance(proj, dict) and proj.get("md_gerado") == str(caminho_md):
                return
                
        novo_projeto = {
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "pdf_original": nome_pdf,
            "md_gerado": str(caminho_md)
        }
        historico.insert(0, novo_projeto)
        
        caminho = self.arquivo_memoria
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)

    def obter_todos(self):
        caminho = self.arquivo_memoria
        if caminho.exists():
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def limpar_historico(self):
        caminho = self.arquivo_memoria
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump([], f)


historico_app = HistoricoApp()
ARQUIVO_MEMORIA = _obter_caminho_historico()