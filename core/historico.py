import json
from datetime import datetime

from core.utils import get_app_root

ARQUIVO_MEMORIA = get_app_root() / "historico_projetos.json"

class HistoricoApp:
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
        
        with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)

    def obter_todos(self):
        if ARQUIVO_MEMORIA.exists():
            try:
                with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def limpar_historico(self):
        with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
            json.dump([], f)

historico_app = HistoricoApp()