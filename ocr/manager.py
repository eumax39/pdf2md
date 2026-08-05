import logging
import os
import pathlib
import re
import time
import threading
import hashlib
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FutureTimeoutError
from multiprocessing import get_context

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageFilter, ImageOps

from core.configuracao import config_app
from core.utils import get_app_root, get_resource_path, log_erro

# Evita checagens remotas de host de modelos que podem atrasar o startup em Windows.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def _resolver_model_home_local():
    candidatos = [
        get_resource_path("assets", "paddlex"),
        get_app_root() / "assets" / "paddlex",
        get_app_root() / ".paddlex",
        pathlib.Path.home() / ".paddlex",
    ]

    for base in candidatos:
        if (base / "official_models").exists():
            return base
    return None


MODEL_HOME_LOCAL = _resolver_model_home_local()
if MODEL_HOME_LOCAL is not None:
    os.environ.setdefault("PADDLE_PDX_MODEL_HOME", str(MODEL_HOME_LOCAL))

# Silencia os avisos verbosos da IA no terminal
logging.getLogger("ppocr").setLevel(logging.ERROR)


class GerenciadorOCR:
    def __init__(self, use_subprocess=True):
        self.motor = None
        self._falhas_consecutivas = 0
        self._desabilitado = False
        self._cache_imagens = {}
        self._idioma_em_uso = None
        self._ultimo_erro_init = ""
        self._proxima_tentativa_ts = 0.0
        self._cpu_threads = max(1, int(config_app.get("threads_cpu") or (os.cpu_count() or 4)))
        self._usar_mkldnn = True
        self._forcar_ocr_v3 = False
        self._use_subprocess = bool(use_subprocess)
        self._ocr_executor = None
        self._executor_lock = threading.Lock()
        self._worker_aquecido = False
        self._cache_resultados_ocr = {}
        self._cache_ordem = []
        self._cache_maximo = 80
        self._timeouts_consecutivos = 0
        self._ocr_pausado_ate_ts = 0.0

    def _obter_timeout_ocr(self):
        valor = config_app.get("ocr_timeout_segundos")
        try:
            timeout = float(valor)
            if timeout <= 0:
                raise ValueError("timeout inválido")
            return timeout
        except Exception:
            return 25.0

    def _obter_timeout_inicial_worker(self):
        valor = config_app.get("ocr_timeout_inicial_segundos")
        try:
            timeout = float(valor)
            if timeout <= 0:
                raise ValueError("timeout inválido")
            return timeout
        except Exception:
            return 90.0

    def _hash_imagem(self, img_array):
        if not isinstance(img_array, np.ndarray) or img_array.size == 0:
            return None

        try:
            h = hashlib.sha1()
            h.update(str(img_array.shape).encode("utf-8"))
            h.update(str(img_array.dtype).encode("utf-8"))
            h.update(img_array.tobytes())
            return h.hexdigest()
        except Exception:
            return None

    def _cache_get(self, chave):
        if not chave:
            return None
        return self._cache_resultados_ocr.get(chave)

    def _cache_set(self, chave, valor):
        if not chave:
            return

        if chave in self._cache_resultados_ocr:
            self._cache_resultados_ocr[chave] = valor
            return

        self._cache_resultados_ocr[chave] = valor
        self._cache_ordem.append(chave)

        while len(self._cache_ordem) > self._cache_maximo:
            antigo = self._cache_ordem.pop(0)
            self._cache_resultados_ocr.pop(antigo, None)

    def _inicializar_executor(self):
        if not self._use_subprocess:
            return None

        with self._executor_lock:
            if self._ocr_executor is None:
                try:
                    contexto = get_context("spawn")
                    self._ocr_executor = ProcessPoolExecutor(max_workers=1, mp_context=contexto)
                except Exception:
                    self._ocr_executor = ProcessPoolExecutor(max_workers=1)

            return self._ocr_executor

    def _reiniciar_executor(self):
        with self._executor_lock:
            executor_atual = self._ocr_executor
            self._ocr_executor = None
            self._worker_aquecido = False

        if executor_atual is not None:
            try:
                executor_atual.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def finalizar_worker(self):
        with self._executor_lock:
            executor_atual = self._ocr_executor
            self._ocr_executor = None
            self._worker_aquecido = False

        if executor_atual is not None:
            try:
                executor_atual.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def preaquecer_worker(self):
        if not self._use_subprocess:
            return

        executor = self._inicializar_executor()
        if executor is None:
            return

        from ocr.worker import inicializar_worker_ocr

        timeout = self._obter_timeout_inicial_worker()
        future = executor.submit(inicializar_worker_ocr)

        try:
            resultado = future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            self._reiniciar_executor()
            return
        except Exception:
            self._reiniciar_executor()
            return

        if isinstance(resultado, dict) and resultado.get("ok"):
            self._worker_aquecido = True
        else:
            self._reiniciar_executor()

    def _criar_motor(self, idioma, *, ocr_version=None, enable_mkldnn=True, cpu_threads=1):
        kwargs = {
            "use_textline_orientation": False,
            "lang": idioma,
            "enable_mkldnn": enable_mkldnn,
            "cpu_threads": max(1, int(cpu_threads)),
            "text_detection_model_dir": None,
            "text_recognition_model_dir": None,
        }
        if ocr_version:
            kwargs["ocr_version"] = ocr_version
        return PaddleOCR(**kwargs)

    def inicializar_se_necessario(self):
        agora = time.monotonic()
        if self._desabilitado and agora < self._proxima_tentativa_ts:
            return

        if self._desabilitado and agora >= self._proxima_tentativa_ts:
            self._desabilitado = False

        if self.motor is None or self.motor == "ERRO":
            try:
                threads_config = config_app.get("threads_cpu")
                try:
                    self._cpu_threads = max(1, int(threads_config))
                except (TypeError, ValueError):
                    self._cpu_threads = max(1, os.cpu_count() or 4)

                idioma_config = str(config_app.get("idioma_ocr") or "pt").strip().lower()
                idiomas_tentativa = [idioma_config]
                if idioma_config in {"pt", "pt-br", "pt_br", "portugues", "portuguese"}:
                    idiomas_tentativa.append("latin")
                if "latin" not in idiomas_tentativa:
                    idiomas_tentativa.append("latin")

                tentativas_motor = []
                idiomas_com_fallback = list(idiomas_tentativa)
                if "en" not in idiomas_com_fallback:
                    idiomas_com_fallback.append("en")

                if self._forcar_ocr_v3:
                    for idioma in idiomas_com_fallback:
                        tentativas_motor.append((idioma, "PP-OCRv3", False, 1))
                else:
                    for idioma in idiomas_tentativa:
                        tentativas_motor.append((idioma, None, self._usar_mkldnn, self._cpu_threads))
                        tentativas_motor.append((idioma, "PP-OCRv3", False, 1))
                    # fallback final para inglês, que costuma ter maior disponibilidade de modelos.
                    tentativas_motor.append(("en", "PP-OCRv3", False, 1))

                ultimo_erro = None
                for idioma, versao, usar_mkldnn, threads in tentativas_motor:
                    try:
                        self.motor = self._criar_motor(
                            idioma,
                            ocr_version=versao,
                            enable_mkldnn=usar_mkldnn,
                            cpu_threads=threads,
                        )
                        self._usar_mkldnn = usar_mkldnn
                        self._cpu_threads = threads
                        self._idioma_em_uso = idioma
                        ultimo_erro = None
                        break
                    except Exception as erro_idioma:
                        ultimo_erro = erro_idioma
                        self.motor = None

                if self.motor is None:
                    raise RuntimeError(
                        f"Falha ao carregar modelos de OCR para idiomas: {', '.join(idiomas_tentativa)}"
                    ) from ultimo_erro

                self._falhas_consecutivas = 0
                self._ultimo_erro_init = ""
                self._desabilitado = False
                self._proxima_tentativa_ts = 0.0
            except Exception as e:
                self._falhas_consecutivas += 1
                self._ultimo_erro_init = str(e)
                log_erro("Falha ao inicializar o motor PaddleOCR", e)
                self.motor = "ERRO"
                if self._falhas_consecutivas >= 3:
                    self._desabilitado = True
                    # Evita tentar inicializar a cada página quando há falha recorrente.
                    self._proxima_tentativa_ts = time.monotonic() + 30.0

    def _precisa_fallback_mkldnn(self, erro):
        if erro is None:
            return False

        msg = str(erro).lower()
        gatilhos = (
            "convertpirattribute2runtimeattribute",
            "onednn_instruction",
            "onednn",
            "notimplemented",
            "unimplemented",
        )
        return any(gatilho in msg for gatilho in gatilhos)

    def _reconfigurar_sem_mkldnn(self):
        # Reinicializa o motor em modo mais compatível quando oneDNN falha no runtime.
        self._usar_mkldnn = False
        self.motor = None
        self._desabilitado = False
        self._proxima_tentativa_ts = 0.0
        self.inicializar_se_necessario()

    def _reconfigurar_para_ocr_v3(self):
        # Fallback forte para ambientes em que os modelos novos falham na inferência.
        self._forcar_ocr_v3 = True
        self._usar_mkldnn = False
        self._cpu_threads = 1
        self.motor = None
        self._desabilitado = False
        self._proxima_tentativa_ts = 0.0
        self.inicializar_se_necessario()

    def _executar_ocr(self, imagem):
        try:
            return self.motor.ocr(imagem)
        except Exception as e:
            log_erro("Erro no OCR durante inferência", e)
            if self._usar_mkldnn and self._precisa_fallback_mkldnn(e):
                self._reconfigurar_sem_mkldnn()
                if self.motor not in (None, "ERRO"):
                    try:
                        return self.motor.ocr(imagem)
                    except Exception as erro_sem_mkldnn:
                        log_erro("Erro no OCR após fallback sem MKLDNN", erro_sem_mkldnn)

            if self._precisa_fallback_mkldnn(e):
                self._reconfigurar_para_ocr_v3()
                if self.motor not in (None, "ERRO"):
                    return self.motor.ocr(imagem)
            raise

    def _preprocessar_imagem(self, img_array):
        if not isinstance(img_array, np.ndarray) or img_array.size == 0:
            return None

        try:
            imagem = Image.fromarray(img_array)
            if imagem.mode != "RGB":
                imagem = imagem.convert("RGB")

            largura, altura = imagem.size
            largura_maxima = 1200
            if largura > largura_maxima:
                proporcao = largura_maxima / largura
                nova_altura = max(1, int(altura * proporcao))
                imagem = imagem.resize((largura_maxima, nova_altura), Image.Resampling.BILINEAR)

            return np.array(imagem)
        except Exception:
            return img_array

    def _preprocessar_imagem_reforco(self, img_array):
        if not isinstance(img_array, np.ndarray) or img_array.size == 0:
            return None

        try:
            imagem = Image.fromarray(img_array)
            if imagem.mode != "RGB":
                imagem = imagem.convert("RGB")

            cinza = ImageOps.grayscale(imagem)
            contraste = ImageOps.autocontrast(cinza, cutoff=2)
            nitida = contraste.filter(ImageFilter.SHARPEN)

            largura, altura = nitida.size
            if largura < 1400:
                fator = 1400 / max(1, largura)
                nova_altura = max(1, int(altura * fator))
                nitida = nitida.resize((1400, nova_altura), Image.Resampling.BICUBIC)

            return np.array(nitida.convert("RGB"))
        except Exception:
            return None

    def _limpar_texto(self, texto):
        if not texto:
            return ""
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    def _extrair_texto_de_valor(self, valor):
        if valor is None:
            return ""

        if isinstance(valor, str):
            return valor.strip()

        if isinstance(valor, (list, tuple)):
            partes = []
            for item in valor:
                texto = self._extrair_texto_de_valor(item)
                if texto:
                    partes.append(texto)
            return " ".join(partes).strip()

        if isinstance(valor, dict):
            for chave in ("rec_texts", "rec_text", "text", "ocr_text", "pred_texts", "pred_text"):
                if chave in valor:
                    return self._extrair_texto_de_valor(valor[chave])

            for item in valor.values():
                texto = self._extrair_texto_de_valor(item)
                if texto:
                    return texto
            return ""

        attrs = getattr(valor, "__dict__", None)
        if attrs:
            texto = self._extrair_texto_de_valor(attrs)
            if texto:
                return texto

        for chave in ("rec_texts", "rec_text", "text", "ocr_text", "pred_texts", "pred_text"):
            if hasattr(valor, chave):
                return self._extrair_texto_de_valor(getattr(valor, chave))

        return ""

    def _extrair_texto_do_resultado(self, resultados):
        if not resultados:
            return ""

        if isinstance(resultados, dict):
            resultados = [resultados]
        elif not isinstance(resultados, (list, tuple)):
            resultados = [resultados]

        textos = []
        for resultado in resultados:
            texto = self._extrair_texto_de_valor(resultado)
            if texto:
                textos.append(texto)

        return self._limpar_texto(" ".join(textos))

    def _ler_imagem_local(self, img_array):
        self.inicializar_se_necessario()

        if self._desabilitado or self.motor is None or self.motor == "ERRO" or img_array is None:
            detalhe = f" Detalhe: {self._ultimo_erro_init}" if self._ultimo_erro_init else ""
            return f"> [Aviso: OCR indisponível.{detalhe}]\n"

        try:
            if not isinstance(img_array, np.ndarray) or img_array.size == 0:
                return "> [Aviso: Matriz de imagem vazia]\n"

            img_processada = self._preprocessar_imagem(img_array)
            if img_processada is None:
                return "> [Erro: imagem inválida]\n"

            texto_extraido = ""

            # Fluxo principal: roda OCR uma vez na imagem preprocessada.
            try:
                resultados = self._executar_ocr(img_processada)
                texto_extraido = self._extrair_texto_do_resultado(resultados)
            except Exception:
                texto_extraido = ""

            # Fallback condicional: só tenta a imagem original se a preprocessada não trouxe texto
            # e se houve alteração real no tamanho/formato da matriz.
            if not texto_extraido.strip() and img_processada.shape != img_array.shape:
                try:
                    resultados = self._executar_ocr(img_array)
                    texto_extraido = self._extrair_texto_do_resultado(resultados)
                except Exception:
                    texto_extraido = ""

            # Reforço de leitura: tenta uma variação com contraste e nitidez
            # apenas quando o fluxo principal não encontrou texto.
            if not texto_extraido.strip():
                img_reforco = self._preprocessar_imagem_reforco(img_array)
                if img_reforco is not None:
                    try:
                        resultados = self._executar_ocr(img_reforco)
                        texto_extraido = self._extrair_texto_do_resultado(resultados)
                    except Exception:
                        texto_extraido = ""

            if texto_extraido.strip():
                return f"\n{texto_extraido}\n"

            try:
                imagem_pil = Image.fromarray(np.array(img_array))
                if imagem_pil.mode != "RGB":
                    imagem_pil = imagem_pil.convert("RGB")
                imagem_pil = imagem_pil.resize((imagem_pil.width * 2, imagem_pil.height * 2), Image.Resampling.LANCZOS)
                return f"\n> [OCR não retornou texto legível nesta página. A imagem pode estar muito escura, muito pequena ou sem contraste suficiente.]\n"
            except Exception:
                return "> [OCR não retornou texto legível nesta página]\n"

        except Exception as e:
            log_erro("Erro interno durante a extração de texto", e)
            return "> [Erro no processamento OCR desta imagem]\n"

    def _ler_imagem_via_worker(self, img_array):
        agora = time.monotonic()
        if agora < self._ocr_pausado_ate_ts:
            restante = int(max(1, self._ocr_pausado_ate_ts - agora))
            return f"> [Aviso: OCR temporariamente pausado após timeouts consecutivos. Tentando novamente em {restante}s.]\n"

        executor = self._inicializar_executor()
        if executor is None:
            return self._ler_imagem_local(img_array)

        from ocr.worker import processar_ocr_em_worker

        timeout = self._obter_timeout_ocr()
        if not self._worker_aquecido:
            timeout = max(timeout, self._obter_timeout_inicial_worker())
        future = executor.submit(processar_ocr_em_worker, img_array)

        try:
            resultado = future.result(timeout=timeout)
        except FutureTimeoutError:
            future.cancel()
            self._timeouts_consecutivos += 1
            if self._timeouts_consecutivos >= 2:
                # Evita esperar timeout em todas as páginas quando o backend trava.
                self._ocr_pausado_ate_ts = time.monotonic() + 120.0
            self._reiniciar_executor()
            return f"> [Aviso: OCR excedeu o tempo limite de {int(timeout)}s nesta página.]\n"
        except Exception as e:
            log_erro("Falha ao executar OCR no processo dedicado", e)
            self._timeouts_consecutivos += 1
            self._reiniciar_executor()
            return "> [Erro no processo de OCR. Tente novamente nesta página.]\n"

        if not isinstance(resultado, dict):
            self._reiniciar_executor()
            return "> [Erro: resposta inválida do processo OCR.]\n"

        if resultado.get("ok"):
            texto = resultado.get("texto") or ""
            self._worker_aquecido = True
            self._timeouts_consecutivos = 0
            self._ocr_pausado_ate_ts = 0.0
            return texto

        detalhe = resultado.get("erro") or "falha desconhecida"
        log_erro("Erro retornado pelo worker OCR", Exception(detalhe))
        self._timeouts_consecutivos += 1
        self._reiniciar_executor()
        return f"> [Erro no worker OCR: {detalhe}]\n"

    def ler_imagem(self, img_array):
        chave_cache = self._hash_imagem(img_array)
        cache_hit = self._cache_get(chave_cache)
        if cache_hit is not None:
            return cache_hit

        if self._use_subprocess:
            resposta = self._ler_imagem_via_worker(img_array)
        else:
            resposta = self._ler_imagem_local(img_array)

        resposta_normalizada = (resposta or "").strip().lower()
        if resposta and "tempo limite" not in resposta_normalizada and "erro" not in resposta_normalizada:
            self._cache_set(chave_cache, resposta)

        return resposta


ocr_engine = GerenciadorOCR()