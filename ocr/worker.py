from typing import Any, Dict

_WORKER_ENGINE = None


def _get_worker_engine():
	global _WORKER_ENGINE
	if _WORKER_ENGINE is None:
		from ocr.manager import GerenciadorOCR

		_WORKER_ENGINE = GerenciadorOCR(use_subprocess=False)
		# Perfil estável para o processo dedicado: evita oneDNN e modelos mais pesados.
		_WORKER_ENGINE._forcar_ocr_v3 = True
		_WORKER_ENGINE._usar_mkldnn = False
		_WORKER_ENGINE._cpu_threads = 1
	return _WORKER_ENGINE


def inicializar_worker_ocr() -> Dict[str, Any]:
	"""Inicializa o motor OCR no processo dedicado para reduzir latência da primeira página."""
	try:
		engine = _get_worker_engine()
		engine.inicializar_se_necessario()
		return {"ok": True}
	except Exception as e:
		return {"ok": False, "erro": str(e)}


def processar_ocr_em_worker(img_array) -> Dict[str, Any]:
	"""Executa OCR em processo separado usando um motor persistente por worker."""
	try:
		engine = _get_worker_engine()
		texto = engine.ler_imagem(img_array)
		return {"ok": True, "texto": texto}
	except Exception as e:
		return {"ok": False, "erro": str(e)}
