# -*- coding: utf-8 -*-
# brain_la.py - BRAIN CON CACHE INTELLIGENTE

import time
import json
import logging
import re
from google import genai
from config_auto_apprendimento import (
    GEMINI_MODEL, GEMINI_RETRIES, GEMINI_RETRY_DELAY, GEMINI_REQUEST_DELAY, VOTO_MIN_DEFAULT, VOTO_MAX_DEFAULT
)
from lstm_predictor_lite import LSTMPredictor
from asset_list import ASSET_MAPPING  
class BrainLA:
    def __init__(self, api_key=None, feedback_engine=None):
        import os, logging
        try:
            # Prova a importare config_la (se esiste) per ottenere eventuali chiavi o client già predisposti
            try:
                import config_la
            except Exception:
                config_la = None

            # Priorità per la chiave API:
            # 1) argomento esplicito api_key
            # 2) config_la.GEMINI_KEY o config_la.GOOGLE_API_KEY (se config_la importabile)
            # 3) variabili d'ambiente BRAIN_API_KEY, GOOGLE_API_KEY, GEMINI_KEY
            self.api_key = (
                api_key
                or (getattr(config_la, "GEMINI_KEY", None) if config_la is not None else None)
                or (getattr(config_la, "GOOGLE_API_KEY", None) if config_la is not None else None)
                or os.environ.get("BRAIN_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("GEMINI_KEY")
                or ""
            )

            # Se in config_la è definito un client pronto (es. config_la.client), usalo
            self.client = getattr(config_la, "client", None) if config_la is not None else None

            # Valori di configurazione esistenti (presumo definiti come costanti globali)
            self.model_name = globals().get("GEMINI_MODEL", None)
            self.tentativi_gemini = globals().get("GEMINI_RETRIES", 1)
            self.delay_retry = globals().get("GEMINI_RETRY_DELAY", 1)
            self.request_delay = globals().get("GEMINI_REQUEST_DELAY", 0)
            self.ultimo_request_time = 0
            self.feedback_engine = feedback_engine
            self.cache_analisi = {}
            self.cache_timeout = 300

            # Caricamento LSTM predictor (se disponibile)
            try:
                self.lstm_predictor = LSTMPredictor()
                logging.info("✅ LSTM Predictor caricato")
            except Exception as ex:
                logging.error(f"❌ Errore LSTM Predictor: {ex}")
                import traceback; traceback.print_exc()
                self.lstm_predictor = None

            logging.info(f"✅ BrainLA inizializzato con modello {self.model_name}")
            logging.info(f"✅ Cache sistema attivo (timeout: {self.cache_timeout}s)")
        except Exception as e:
            logging.error(f"❌ Errore inizializzazione Brain: {e}")
            import traceback; traceback.print_exc()
            # fallback sicuro per evitare crash a livello di creazione dell'istanza
            self.client = None
            self.api_key = api_key or ""
            self.model_name = None
            self.tentativi_gemini = 1
            self.delay_retry = 1
            self.request_delay = 0
            self.ultimo_request_time = 0
            self.feedback_engine = feedback_engine
            self.cache_analisi = {}
            self.cache_timeout = 300
            self.lstm_predictor = None

    def genera_analisi_ia(self, prompt, api_key):
        """
        Funzione resiliente per chiamare il client GenAI.
        Prova metodi top-level e metodi annidati (es. chats.create, models.generate_content, interactions.create).
        Restituisce testo (o None).
        """
        import logging, time, traceback, sys

        print("[DEBUG_CALL] Entra genera_analisi_ia", flush=True)
        logging.info("[DEBUG_CALL] Entra genera_analisi_ia")

        api_key = api_key or getattr(self, "api_key", None)

        # nomi di method-path semplici e annidati da provare (ordine importante)
        candidate_method_paths = [
            # preferenze dirette osservate nel tuo client
            "chats.create", "interactions.create", "models.generate_content", "models.generate",
            # top-level (fallback)
            "generate", "create",
            # altri path utili
            "chats.generate", "chats.create_message", "chats.completions.create",
            "models.predict", "models.create",
            "interactions.generate", "files.create", "batches.create",
        ]

        def resolve_attr_path(obj, path):
            """Risolve 'a.b.c' su obj restituendo l'attributo / metodo o None se assente."""
            cur = obj
            for part in path.split("."):
                if not hasattr(cur, part):
                    return None
                cur = getattr(cur, part)
            return cur

        def try_invoke(callable_obj, model, prompt):
            """
            Prova diverse firme possibili su callable_obj fino a ottenere una risposta:
            - kwargs comuni (model/prompt, model/input, model/messages)
            - positional (prompt), (model,prompt)
            - request/dict come single positional o kwarg (varie shape)
            - payload 'messages' per chats
            Restituisce la response se una chiamata ha successo, altrimenti rilancia l'ultima eccezione.
            """
            import traceback
            last_exc = None

            if not callable(callable_obj):
                raise TypeError("Oggetto non callable")

            # payload per chats
            messages_payload = [{"author": "user", "content": [{"type": "text", "text": prompt}]}]

            # lista di tentativi in ordine (descrizione, lambda che invoca)
            attempts = [
                ("kwargs: model+prompt", lambda: callable_obj(model=model, prompt=prompt)),
                ("kwargs: prompt+model", lambda: callable_obj(prompt=prompt, model=model)),
                ("kwargs: model+input", lambda: callable_obj(model=model, input=prompt)),
                ("kwargs: input+model", lambda: callable_obj(input=prompt, model=model)),
                ("kwargs: model+messages", lambda: callable_obj(model=model, messages=messages_payload)),
                ("kwargs: messages+model", lambda: callable_obj(messages=messages_payload, model=model)),
                ("kwargs: messages only", lambda: callable_obj(messages=messages_payload)),
                ("positional: (prompt,)", lambda: callable_obj(prompt)),
                ("positional: (model, prompt)", lambda: callable_obj(model, prompt)),
                ("positional dict: {'model','prompt'}", lambda: callable_obj({"model": model, "prompt": prompt})),
                ("positional dict: {'model','input'}", lambda: callable_obj({"model": model, "input": prompt})),
                ("positional dict: {'model','instances':[prompt]}", lambda: callable_obj({"model": model, "instances": [prompt]})),
                ("request kw: {'model','prompt'}", lambda: callable_obj(request={"model": model, "prompt": prompt})),
                ("request kw: {'model','input'}", lambda: callable_obj(request={"model": model, "input": prompt})),
                ("request kw: {'model','messages'}", lambda: callable_obj(request={"model": model, "messages": messages_payload})),
                ("request kw: {'instances':[prompt]}", lambda: callable_obj(request={"model": model, "instances": [prompt]})),
                ("kwargs: model+instances", lambda: callable_obj(model=model, instances=[prompt])),
                ("kwargs: model+content", lambda: callable_obj(model=model, content=prompt)),
                ("kwargs: request messages+model", lambda: callable_obj(request={"messages": messages_payload, "model": model})),
            ]

            for desc, fn in attempts:
                try:
                    result = fn()
                    return result
                except Exception as e:
                    last_exc = e
                    # non loggare eccessivamente qui; la funzione chiamante stampa dettagli
                    continue

            # se siamo qui, tutte le prove sono fallite: rilancia l'ultima eccezione
            if last_exc:
                raise last_exc
            raise RuntimeError("Nessun tentativo di invocazione è stato effettuato")

        try:
            try:
                import google.genai as genai
            except Exception as ex:
                logging.warning(f"[DEBUG_CALL] Impossibile importare google.genai: {ex}")
                genai = None

            for client_source, client_obj in (("self.client", getattr(self, "client", None)),
                                              ("genai.Client", None)):
                if client_source == "self.client" and client_obj:
                    client = client_obj
                    logging.info("[DEBUG_CALL] Provo self.client")
                    print(f"[DEBUG_CALL] Usando client da self.client: {repr(client)}", flush=True)
                elif client_source == "genai.Client" and genai is not None and hasattr(genai, "Client"):
                    try:
                        logging.info("[DEBUG_CALL] Provo genai.Client")
                        client = genai.Client(api_key=api_key)
                        print(f"[DEBUG_CALL] Creato genai.Client con api_key presente: {'YES' if api_key else 'NO'}", flush=True)
                    except Exception as e:
                        logging.warning(f"[DEBUG_CALL] Creazione genai.Client fallita: {e}")
                        print(f"[DEBUG_CALL] Creazione genai.Client fallita: {e}", flush=True)
                        continue
                else:
                    continue

                # stampa attributi pubblici client e di sotto-oggetti utili (per debug)
                try:
                    public_attrs = [a for a in dir(client) if not a.startswith("_")]
                    print(f"[DEBUG_CALL] Attributi pubblici client (prime 60): {public_attrs[:60]}", flush=True)
                    for sub in ("chats", "models", "interactions", "files"):
                        sub_obj = getattr(client, sub, None)
                        if sub_obj is not None:
                            try:
                                sub_attrs = [a for a in dir(sub_obj) if not a.startswith("_")]
                                print(f"[DEBUG_CALL] Attributi pubblici client.{sub} (prime 60): {sub_attrs[:60]}", flush=True)
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[DEBUG_CALL] Errore listing client attrs: {e}", flush=True)
                # --- Inserire QUI: tentativi mirati per Google GenAI (interactions/chats) ---
                _interactions = getattr(client, "interactions", None)
                if _interactions is not None and hasattr(_interactions, "create"):
                    try:
                        resp = _interactions.create(input=prompt, model=getattr(self, "model_name", None) or "gemini-2.5-flash")
                        print(f"[DEBUG_GEMINI_RAW] interactions.create resp={repr(resp)}", flush=True)
                        try:
                            response_text = self._estrai_testo_da_response(resp)
                        except Exception as e:
                            response_text = None
                            print(f"[DEBUG_CALL] Errore estrazione testo interactions: {e}", flush=True)
                        print(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}", flush=True)
                        if response_text:
                            return response_text
                    except Exception as e:
                        print(f"[DEBUG_CALL] interactions.create ha sollevato: {e}", flush=True)

                # Fallback: client.chats.create(model=..., history=[...]) — usa history, non messages
                _chats = getattr(client, "chats", None)
                if _chats is not None and hasattr(_chats, "create"):
                    try:
                        history = [{"type": "text", "text": prompt}]
                        resp = _chats.create(model=getattr(self, "model_name", None) or "gemini-2.5-flash", history=history)
                        print(f"[DEBUG_GEMINI_RAW] chats.create resp={repr(resp)}", flush=True)
                        try:
                            response_text = self._estrai_testo_da_response(resp)
                        except Exception as e:
                            response_text = None
                            print(f"[DEBUG_CALL] Errore estrazione testo chats: {e}", flush=True)
                        print(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}", flush=True)
                        if response_text:
                            return response_text
                    except Exception as e:
                        print(f"[DEBUG_CALL] chats.create ha sollevato: {e}", flush=True)
                # --- Fine blocco mirato ---
                
                # tenta tutti i method-path candidati
                for path in candidate_method_paths:
                    target = resolve_attr_path(client, path)
                    present = target is not None
                    logging.info(f"[DEBUG_CALL] Provo path '{path}' (presente={present}) sul client {client_source}")
                    print(f"[DEBUG_CALL] Provo path '{path}' (presente={present}) sul client {client_source}", flush=True)
                    if not present:
                        continue

                    # se target non è callable, esploriamo metodi comuni all'interno del sub-object
                    if not callable(target):
                        for subname in ("create", "generate", "predict", "create_message", "completions", "completion"):
                            sub_target = resolve_attr_path(target, subname)
                            if sub_target is None:
                                continue
                            if not callable(sub_target):
                                # es. target.completions.create -> proviamo deep .create/.generate
                                for deep in ("create", "generate"):
                                    deep_target = resolve_attr_path(sub_target, deep)
                                    if deep_target and callable(deep_target):
                                        try:
                                            resp = try_invoke(deep_target, getattr(self, "model_name", None), prompt)
                                        except Exception as e:
                                            print(f"[DEBUG_CALL] Errore invoking {path}.{subname}.{deep}: {e}", flush=True)
                                            continue
                                        logging.info(f"[DEBUG_GEMINI_RAW] path={path}.{subname}.{deep} resp={repr(resp)}")
                                        print(f"[DEBUG_GEMINI_RAW] path={path}.{subname}.{deep} resp={repr(resp)}", flush=True)
                                        try:
                                            response_text = self._estrai_testo_da_response(resp)
                                        except Exception as e:
                                            response_text = None
                                            print(f"[DEBUG_CALL] Errore estrazione testo: {e}", flush=True)
                                        print(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}", flush=True)
                                        return response_text
                                continue
                            # sub_target è callable: prova direttamente
                            try:
                                resp = try_invoke(sub_target, getattr(self, "model_name", None), prompt)
                            except Exception as e:
                                print(f"[DEBUG_CALL] Errore invoking {path}.{subname}: {e}", flush=True)
                                continue
                            logging.info(f"[DEBUG_GEMINI_RAW] path={path}.{subname} resp={repr(resp)}")
                            print(f"[DEBUG_GEMINI_RAW] path={path}.{subname} resp={repr(resp)}", flush=True)
                            try:
                                response_text = self._estrai_testo_da_response(resp)
                            except Exception as e:
                                response_text = None
                                print(f"[DEBUG_CALL] Errore estrazione testo: {e}", flush=True)
                            print(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}", flush=True)
                            return response_text

                    else:
                        # target è callable: invoca direttamente
                        try:
                            resp = try_invoke(target, getattr(self, "model_name", None), prompt)
                        except Exception as e:
                            print(f"[DEBUG_CALL] Metodo {path} ha sollevato: {e}", flush=True)
                            print(traceback.format_exc(limit=2), flush=True)
                            continue

                        logging.info(f"[DEBUG_GEMINI_RAW] path={path} resp={repr(resp)}")
                        print(f"[DEBUG_GEMINI_RAW] path={path} resp={repr(resp)}", flush=True)
                        try:
                            response_text = self._estrai_testo_da_response(resp)
                        except Exception as e:
                            response_text = None
                            print(f"[DEBUG_CALL] Errore estrazione testo: {e}", flush=True)
                        print(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}", flush=True)
                        return response_text

            logging.error("[DEBUG_CALL] Nessuna interfaccia GenAI utilizzabile trovata")
            return None

        except Exception as e:
            logging.exception(f"[DEBUG_GEMINI_EXCEPTION] Errore nella chiamata IA: {e}")
            print(f"[DEBUG_CALL] Errore nella chiamata IA: {e}", flush=True)
            traceback.print_exc(file=sys.stdout)
            return None

    # ===== NUOVO: METODI CACHE =====
    def _pulisci_cache_vecchia(self):
        now = time.time()
        keys_to_remove = [symbol for symbol, cached in self.cache_analisi.items()
                          if now - cached['timestamp'] > self.cache_timeout]
        for key in keys_to_remove:
            del self.cache_analisi[key]
            logging.debug(f"🗑️ Cache scaduta rimossa: {key}")

    def _usa_cache_se_valida(self, symbol):
        self._pulisci_cache_vecchia()
        if symbol in self.cache_analisi:
            cached = self.cache_analisi[symbol]
            age = time.time() - cached['timestamp']
            if age < self.cache_timeout:
                logging.info(f"📦 CACHE HIT per {symbol} (età: {age:.0f}s)")
                return cached['analisi']
        return None

    def _salva_in_cache(self, symbol, analisi):
        self.cache_analisi[symbol] = {
            'timestamp': time.time(),
            'analisi': analisi.copy()
        }
        logging.debug(f"💾 Salvato in cache: {symbol}")

    def _applica_rate_limiting(self):
        elapsed = time.time() - self.ultimo_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.ultimo_request_time = time.time()

    def _estrai_testo_da_response(self, response):
        """
        Estrae in modo robusto il testo/JSON dalla response dei client GenAI.
        Restituisce stringa pulita (o None se non trova testo).
        """
        import json, re, traceback

        def clean_code_fence(s: str) -> str:
            # rimuove ```json ... ``` o ``` ... ``` o singoli backticks
            s = s.strip()
            # rimuovi iniziali/trailing triple backticks con lang
            s = re.sub(r'^\s*```(?:json|text)?\s*', '', s, flags=re.I)
            s = re.sub(r'\s*```\s*$', '', s)
            # rimuovi singoli backticks
            s = s.replace("`", "")
            return s.strip()

        try:
            if response is None:
                return None

            # se è già stringa
            if isinstance(response, str):
                s = response.strip()
                return clean_code_fence(s) if s else None

            # primo punto: SDK Interaction/Chat -> outputs
            try:
                if hasattr(response, "outputs"):
                    outs = getattr(response, "outputs")
                    if isinstance(outs, (list, tuple)) and outs:
                        for out in outs:
                            # 1) attributo .text
                            if hasattr(out, "text"):
                                try:
                                    t = getattr(out, "text")
                                    if isinstance(t, str) and t.strip():
                                        return clean_code_fence(t)
                                except Exception:
                                    pass
                            # 2) attributo .content (lista o singolo)
                            if hasattr(out, "content"):
                                try:
                                    cont = getattr(out, "content")
                                    # lista
                                    if isinstance(cont, (list, tuple)) and cont:
                                        for itm in cont:
                                            if isinstance(itm, str) and itm.strip():
                                                return clean_code_fence(itm)
                                            if hasattr(itm, "text") and isinstance(getattr(itm, "text"), str) and getattr(itm, "text").strip():
                                                return clean_code_fence(getattr(itm, "text"))
                                            if isinstance(itm, dict):
                                                for k in ("text", "content", "message"):
                                                    if k in itm and isinstance(it[k], str) and itm[k].strip():
                                                        return clean_code_fence(it[k])
                                    # singolo stringa
                                    if isinstance(cont, str) and cont.strip():
                                        return clean_code_fence(cont)
                                    # oggetto con .text
                                    if hasattr(cont, "text") and isinstance(getattr(cont, "text"), str) and getattr(cont, "text").strip():
                                        return clean_code_fence(getattr(cont, "text"))
                                except Exception:
                                    pass
                            # 3) altri attributi utili nello stesso out
                            for attr in ("summary", "output_text", "message", "body", "result"):
                                if hasattr(out, attr):
                                    try:
                                        v = getattr(out, attr)
                                        if isinstance(v, str) and v.strip():
                                            return clean_code_fence(v)
                                    except Exception:
                                        pass
                            # 4) se out è dict-like
                            try:
                                if isinstance(out, dict):
                                    for k in ("text", "content", "message"):
                                        if k in out and isinstance(out[k], str) and out[k].strip():
                                            return clean_code_fence(out[k])
                                    if "content" in out and isinstance(out["content"], (list, tuple)):
                                        for c in out["content"]:
                                            if isinstance(c, str) and c.strip():
                                                return clean_code_fence(c)
                            except Exception:
                                pass
            except Exception:
                pass

            # se è dict-like top-level
            if isinstance(response, dict):
                d = response
                for key in ("output", "outputs", "completion", "completions", "candidates", "choices", "result", "results", "body"):
                    if key in d and d[key]:
                        val = d[key]
                        if isinstance(val, (list, tuple)) and val:
                            for it in val:
                                if isinstance(it, str) and it.strip():
                                    return clean_code_fence(it)
                                if isinstance(it, dict):
                                    for sub in ("text", "content", "message"):
                                        if sub in it and isinstance(it[sub], str) and it[sub].strip():
                                            return clean_code_fence(it[sub])
                                    if "content" in it and isinstance(it["content"], (list, tuple)):
                                        for c in it["content"]:
                                            if isinstance(c, str) and c.strip():
                                                return clean_code_fence(c)
                            try:
                                return clean_code_fence(json.dumps(val[0], default=str))
                            except Exception:
                                return clean_code_fence(str(val[0]))
                        if isinstance(val, dict):
                            for sub in ("text", "content", "message"):
                                if sub in val and isinstance(val[sub], str) and val[sub].strip():
                                    return clean_code_fence(val[sub])
                            try:
                                return clean_code_fence(json.dumps(val, default=str))
                            except Exception:
                                return clean_code_fence(str(val))
                        if isinstance(val, str) and val.strip():
                            return clean_code_fence(val)
                # fallback: prima stringa trovata tra valori
                for v in d.values():
                    if isinstance(v, str) and v.strip():
                        return clean_code_fence(v)
                try:
                    return clean_code_fence(json.dumps(d, default=str))
                except Exception:
                    return clean_code_fence(str(d))

            # altri attributi SDK generici
            for attr in ("text", "content", "message", "response", "body"):
                if hasattr(response, attr):
                    try:
                        val = getattr(response, attr)
                        if isinstance(val, str) and val.strip():
                            return clean_code_fence(val)
                        if isinstance(val, (list, tuple)) and val:
                            for itm in val:
                                if isinstance(itm, str) and itm.strip():
                                    return clean_code_fence(itm)
                                if hasattr(itm, "text") and isinstance(getattr(itm, "text"), str) and getattr(itm, "text").strip():
                                    return clean_code_fence(getattr(itm, "text"))
                    except Exception:
                        pass

            # cerca JSON nella repr (es. {"voto": ...})
            try:
                rep = repr(response)
                m = re.search(r'(\{[^{}]*"voto"[^{}]*\})', rep, re.DOTALL)
                if m:
                    return clean_code_fence(m.group(1))
            except Exception:
                pass

            # fallback: rappresentazione stringa sensata
            s = str(response)
            return clean_code_fence(s) if s and s.strip() else None

        except Exception:
            traceback.print_exc()
            try:
                return str(response)
            except Exception:
                return None

    def _pulisci_e_valida_json(self, testo_grezzo):
        try:
            if not testo_grezzo:
                logging.warning("[DEBUG_GEMINI] Risposta vuota da Gemini")
                return None
            pulito = re.sub(r'```json\s?|```', '', testo_grezzo).strip()
            start = pulito.find('{')
            end = pulito.rfind('}') + 1
            if start == -1 or end == 0:
                logging.warning("❌ JSON non trovato nella risposta Gemini")
                return None
            json_str = pulito[start:end]
            try:
                result = json.loads(json_str)
            except Exception as e:
                logging.warning(f"[DEBUG_GEMINI] JSON malformato o parse error: {str(e)} | Risposta: {json_str}")
                return None
            if not isinstance(result, dict):
                logging.warning("[DEBUG_GEMINI] Risposta JSON non è dict")
                return None
            return result
        except Exception as e:
            logging.warning(f"❌ Errore parsing JSON: {e}")
            return None

    def _ottieni_feedback_storico(self, symbol):
        try:
            if not self.feedback_engine:
                return "Nessun feedback storico disponibile."
            feedback = self.feedback_engine.genera_feedback_per_ia()
            return feedback if feedback else "Nessun feedback conclusivo disponibile."
        except Exception as e:
            logging.error(f"❌ Errore recupero feedback: {e}")
            return "Errore recupero feedback storico."

    def _applica_guardrail_logico(self, voto_gemini, guardrail):
        try:
            if not guardrail:
                return voto_gemini, []
            voto_min = guardrail.get('voto_minimo', VOTO_MIN_DEFAULT)
            voto_max = guardrail.get('voto_massimo', VOTO_MAX_DEFAULT)
            ragioni = guardrail.get('ragioni', [])
            if voto_gemini is None or voto_gemini < 0:
                voto_gemini = 0
            elif voto_gemini > 10:
                voto_gemini = 10
            voto_corretto = max(voto_min, min(voto_max, voto_gemini))
            if voto_corretto != voto_gemini:
                logging.info(f"🛡️ Guardrail applicato: {voto_gemini:.1f} → {voto_corretto:.1f}")
                for ragione in ragioni:
                    logging.info(f"   {ragione}")
            return voto_corretto, ragioni
        except Exception as e:
            logging.error(f"❌ Errore applicazione guardrail: {e}")
            return voto_gemini, []

    def ottieni_predizione_lstm(self, dati_recenti):
        try:
            if not self.lstm_predictor or not dati_recenti:
                return None
            predizione = self.lstm_predictor.predici(dati_recenti)
            logging.info(f"🔍 DEBUG LSTM RAW: {predizione}")
            if predizione and predizione.get('is_valido'):
                logging.info(f"🔮 LSTM Predizione: {predizione['direzione']} ({predizione['confidence']:.1f}%)")
                return predizione
            else:
                logging.warning("⚠️ Predizione LSTM non valida o non disponibile")
                return None
        except Exception as e:
            logging.error(f"❌ Errore predizione LSTM: {e}")
            return None

    def valuta_trade(self, voto_gemini, guardrail):
        voto_corretto, ragioni_applicate = self._applica_guardrail_logico(voto_gemini, guardrail)
        if voto_corretto < 7:
            print("Non si apre trade: voto troppo basso!", ragioni_applicate)
        else:
            print("Trade permesso!")
        for r in ragioni_applicate:
            print("Motivo:", r)

    def analizza_asset(self, dati, macro_data, sentiment_globale, history_feedback_generico, 
                       contesto_istituzionale=None, posizione_attuale=None, guardrail=None,
                       dati_storici_lstm=None):
        logging.info("[DEBUG_BREAK] Entrato in analizza_asset")
        print("[DEBUG_BREAK] Entrato in analizza_asset")

        if dati and 'symbol' in dati:
            dati['symbol'] = ASSET_MAPPING.get(dati['symbol'], dati['symbol'])
        symbol = dati.get('symbol', 'N/A') if dati else 'N/A'
        print(f"[DEBUG ASSET] symbol after patch: {symbol}")

        default_error = {
            "voto": 0,
            "direzione": "FLAT",
            "orizzonte": "INTRADAY",
            "modalita": "SPOT",
            "sl": 0,
            "tp": 0,
            "ragionamento_mentore": "IA Errore/Timeout - Analisi non disponibile",
            "analisi_logica": {},
            "guardrail_applicato": False,
            "lstm_predizione": "N/A",
            "asset": symbol
        }

        if not dati:
            logging.error("❌ Dati asset non forniti")
            print("[DEBUG_BREAK] Return anticipato: dati mancanti")
            return default_error

        cached_analisi = self._usa_cache_se_valida(symbol)
        if cached_analisi:
            logging.info(f"[DEBUG_BREAK] Cache valida trovata per {symbol}")
            print("[DEBUG_BREAK] Return anticipato: cache valida restituita")
            return cached_analisi

        if hasattr(self, 'lstm_predictor') and self.lstm_predictor is not None:
            logging.info("[DEBUG] lstm_predictor presente, valutazione training")
            print("[DEBUG] lstm_predictor presente, valutazione training")
            if dati_storici_lstm and len(dati_storici_lstm) > 100:
                try:
                    accuracy = self.lstm_predictor.allena_modello(dati_storici_lstm)
                    if accuracy is not None and accuracy > 0:
                        logging.info(f"✅ LSTM Training completato: Accuracy {accuracy:.2%}")
                        print(f"[DEBUG] LSTM training completato: {accuracy:.2%}")
                except Exception as e:
                    logging.warning(f"⚠️ Errore training LSTM: {e}")
                    print(f"[DEBUG] Errore training LSTM: {e}")

        lstm_predizione = "N/A"
        try:
            res_lstm = self.ottieni_predizione_lstm(dati_storici_lstm)
            if res_lstm:
                lstm_predizione = res_lstm
                logging.info(f"[DEBUG] LSTM predizione ottenuta: {lstm_predizione}")
                print(f"[DEBUG] LSTM predizione ottenuta")
        except Exception as e:
            lstm_predizione = "N/A"
            logging.warning(f"⚠️ Errore ottieni_predizione_lstm: {e}")
            print(f"[DEBUG] Errore ottieni_predizione_lstm: {e}")

        memoria_trade = "STATO: Nessuna posizione aperta."
        if posizione_attuale:
            memoria_trade = f"ATTENZIONE: Posizione {posizione_attuale.get('direzione')} aperta a {posizione_attuale.get('p_entrata')}."

        if not self.model_name:
            logging.error("❌ Modello Gemini non disponibile")
            print("[DEBUG_BREAK] Return anticipato: modello Gemini non disponibile")
            return default_error

        stringa_contesto = ""
        if contesto_istituzionale:
            try:
                vwap = contesto_istituzionale.get('vwap', 'N/A')
                cvd = contesto_istituzionale.get('cvd', 'N/A')
                poc = contesto_istituzionale.get('poc', 'N/A')
                stringa_contesto = (
                    f"\n--- CONTESTO ISTITUZIONALE ---\n"
                    f"- VWAP: {vwap} | CVD: {cvd} | POC: {poc}\n"
                )
            except Exception as e:
                logging.warning(f"⚠️ Errore contesto: {e}")
                print(f"[DEBUG] Errore formattazione contesto: {e}")

        stringa_multitf = ""
        if dati and 'multitimeframe' in dati:
            try:
                mtf = dati['multitimeframe']
                stringa_multitf = (
                    f"\n--- ANALISI MULTITIMEFRAME ---\n"
                    f"- 1D: {mtf.get('1D', {}).get('trend')} | 4h: {mtf.get('4h', {}).get('trend')} | 1h: {mtf.get('1h', {}).get('trend')}\n"
                )
            except Exception as e:
                logging.warning(f"⚠️ Errore multi-timeframe: {e}")
                print(f"[DEBUG] Errore multi-timeframe: {e}")

        stringa_lstm = ""
        if isinstance(lstm_predizione, dict):
            try:
                stringa_lstm = (
                    f"\n--- NEURAL PREDICTION (LSTM) ---\n"
                    f"Direzione: {lstm_predizione.get('direzione')}\n"
                    f"Variazione: {lstm_predizione.get('variazione_perc', 0):+.2f}%\n"
                    f"Prezzo Predetto: {lstm_predizione.get('prezzo_predetto', 0):.2f}\n"
                    f"Confidence: {lstm_predizione.get('confidence', 0):.1f}%\n"
                )
            except Exception as e:
                logging.warning(f"⚠️ Errore formattazione stringa LSTM: {e}")
                print(f"[DEBUG] Errore formattazione stringa LSTM: {e}")
        else:
            stringa_lstm = "\n--- NEURAL PREDICTION (LSTM) ---\nPredizione non disponibile.\n"

        feedback_totale = f"{self._ottieni_feedback_storico(symbol)}"
        stringa_guardrail = ""
        if guardrail:
            try:
                voto_min = guardrail.get('voto_minimo', 0)
                voto_max = guardrail.get('voto_massimo', 10)
                ragioni_guardrail = guardrail.get('ragioni', [])
                stringa_guardrail = (
                    f"\n--- VINCOLI LOGICI (GUARDRAIL) ---\n"
                    f"Voto obbligatorio tra {voto_min} e {voto_max}.\n"
                    f"Motivi limitazione: {', '.join(ragioni_guardrail) if ragioni_guardrail else 'Nessuno'}\n"
                )
            except Exception as e:
                logging.warning(f"⚠️ Errore iniezione guardrail: {e}")
                print(f"[DEBUG] Errore iniezione guardrail: {e}")

        try:
            prezzo_real = dati.get('prezzo_real', 'N/A')
            dati_per_json = {k: v for k, v in dati.items() if k not in ['multitimeframe', 'symbol']}
            funding_rate = dati.get("funding_rate", 0)
            if isinstance(funding_rate, tuple):
                funding_rate = funding_rate[0]
            if funding_rate is None:
                funding_rate = 0
            oi_data = contesto_istituzionale.get('open_interest') if contesto_istituzionale else None
            if oi_data and isinstance(oi_data, dict):
                oi_val = oi_data.get('oi', 'N/A')
                oi_var = oi_data.get('oi_24h', 0)

                oi_info = f"OI: {oi_val} (Var: {oi_var:+.2f}%)"
            else:
                oi_info = "OI: Non disponibile"

            prompt = (
                f"Analisi Professionale Asset: {symbol} | Prezzo: {prezzo_real}\n"
                f"Ruolo: Master Trader SMC/VSA. Obiettivo: Istruire Andrea.\n"
                f"{memoria_trade}\n"
                f"{stringa_multitf}{stringa_contesto}"
                f"FUNDING: {funding_rate:.5f} | {oi_info}\n"
                f"{stringa_lstm}\n"
                f"DATI: {json.dumps(dati_per_json, default=str)}\n"
                f"MACRO: {json.dumps(macro_data, default=str)}\n"
                f"{stringa_guardrail}\n"
                "\nISTRUZIONI: Rispondi SOLO con un JSON valido. Sii critico."
                "\nSTRUTTURA JSON RICHIESTA:\n"
                "{\n"
                '  "voto": float,\n'
                '  "direzione": "LONG/SHORT/FLAT",\n'
                '  "orizzonte": "INTRADAY",\n'
                '  "modalita": "SPOT/LEVA",\n'
                '  "sl": float, "tp": float,\n'
                '  "ragionamento_mentore": "Spiegazione SMC/VSA per Andrea",\n'
                '  "analisi_logica": {"mtf": "...", "istituzionali": "...", "oi_vol": "...", "lstm": "..."}\n'
                "}"
            )
            with open("prompt_brain_debug.log", "a", encoding="utf-8") as f:
                f.write(f"--- {symbol} {time.strftime('%H:%M:%S')} ---\n{prompt[:1000]}\n\n")
            logging.info(f"[DEBUG] Prompt costruito per {symbol}, lunghezza {len(prompt)}")
            print(f"[DEBUG] Prompt costruito per {symbol}, lunghezza {len(prompt)}")
        except Exception as e:
            logging.error(f"❌ Errore costruzione prompt: {e}")
            print(f"[DEBUG_BREAK] Return anticipato: errore costruzione prompt: {e}")
            return default_error

        tentativi = 0
        max_tentativi_reali = 2
        while tentativi < max_tentativi_reali:
            try:
                self._applica_rate_limiting()
                logging.info(f"[DEBUG] Chiamata a genera_analisi_ia per {symbol}, tentativo {tentativi+1}")
                print(f"[DEBUG_CALL] Chiamata a genera_analisi_ia per {symbol}, tentativo {tentativi+1}")
                response_text = self.genera_analisi_ia(prompt, api_key=self.api_key)
                logging.info(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}")
                print(f"[DEBUG] Response raw length: {len(response_text) if response_text else 0}")
                if not response_text:
                    print("[DEBUG] Risposta Gemini vuota, sollevamento eccezione per retry")
                    raise ValueError("Risposta Gemini vuota")
                analisi = self._pulisci_e_valida_json(response_text)
                if not analisi or "voto" not in analisi:
                    print("[DEBUG] JSON non valido o incompleto ricevuto")
                    raise ValueError("JSON non valido o incompleto")
                voto_originale = analisi.get("voto", 0)
                voto_protetto, ragioni_applicate = self._applica_guardrail_logico(voto_originale, guardrail)
                analisi.update({
                    "voto": voto_protetto,
                    "guardrail_applicato": (voto_originale != voto_protetto),
                    "asset": symbol,
                    "lstm_predizione": lstm_predizione
                })
                if not analisi.get("ragionamento_mentore"):
                    analisi["ragionamento_mentore"] = "Analisi SMC completata."
                for campo in ["sl", "tp"]:
                    if analisi.get(campo) is None:
                        analisi[campo] = 0
                logging.info(f"✅ Analisi completata per {symbol}: Voto {voto_protetto}")
                print(f"[DEBUG_BREAK] Analisi completata per {symbol}: Voto {voto_protetto}")
                self._salva_in_cache(symbol, analisi)
                return analisi
            except Exception as e:
                tentativi += 1
                attesa = 5
                # Log sintetico e completo del traceback
                logging.warning(f"⚠️ Tentativo {tentativi} fallito per {symbol}: {e}")
                logging.exception("Traceback completo dell'eccezione:")
                # Proviamo a loggare la response grezza se esistente (evita NameError)
                resp_val = locals().get('response_text', None)
                if resp_val is not None:
                    logging.debug(f"[DEBUG_FULL_RESPONSE] repr(response_text): {repr(resp_val)}")
                    print(f"[DEBUG_FULL_RESPONSE] repr(response_text): {repr(resp_val)}", flush=True)
                else:
                    logging.debug("[DEBUG_FULL_RESPONSE] response_text non definita in questo contesto")
                    print("[DEBUG_FULL_RESPONSE] response_text non definita in questo contesto", flush=True)
                print(f"[DEBUG] Tentativo {tentativi} fallito per {symbol}: {e}", flush=True)
                if tentativi < max_tentativi_reali:
                    print(f"[DEBUG] Attendo {attesa}s prima del prossimo tentativo", flush=True)
                    time.sleep(attesa)
                else:
                    print(f"[DEBUG_BREAK] Fine tentativi per {symbol}, esco con default_error", flush=True)
                    break

        logging.error(f"❌ Impossibile analizzare {symbol} dopo {tentativi} tentativi")
        default_error["asset"] = symbol
        default_error["lstm_predizione"] = lstm_predizione
        print(f"[DEBUG_BREAK] Return finale default_error per {symbol}")
        return default_error

    def valuta_posizione_live(self, posizione, dati_correnti, contesto_istituzionale, pnl_percentuale):
        try:
            if not posizione or not dati_correnti or not contesto_istituzionale:
                logging.warning("❌ Dati insufficienti per valutazione live")
                return None
            prezzo_att = dati_correnti.get('prezzo_real', 0)
            rsi = dati_correnti.get('rsi', 50)
            atr = dati_correnti.get('atr', 0)
            if prezzo_att <= 0:
                return None
            prompt = f"""
Tu sei un Master Trader che MONITORA un trade aperto.

POSIZIONE ATTUALE:
- Direzione: {posizione.get('direzione', 'UNKNOWN')}
- Entry: {posizione.get('p_entrata', 0)}
- SL: {posizione.get('sl', 0)}
- TP: {posizione.get('tp', 0)}
- P&L: {pnl_percentuale:.2f}%

SITUAZIONE MERCATO ORA:
- Prezzo: {prezzo_att}
- RSI 1h: {rsi:.1f}
- ATR: {atr:.2f}
- VWAP: {contesto_istituzionale.get('vwap', 0)}
- CVD: {contesto_istituzionale.get('cvd', 0)}
- POC: {contesto_istituzionale.get('poc', 0)}

RAGIONA COME UN VERO TRADER (NON REGOLE RIGIDE):

1. Confidence nella posizione (0-100%)?
2. Cosa fare adesso? Scegli UNA:
   - HOLD (mantieni)
   - REDUCE_SIZE (riduci rischio)
   - TIGHTEN_SL (stringi stop)
   - CLOSE (chiudi)
3. Perché? (ragionamento)
4. Se il prezzo sale/scende del 2%, cosa fai?
5. Se CVD diventa molto negativo, cosa cambia?

RISPONDI IN JSON:
{{
  "confidence": int (0-100),
  "azione": "HOLD/REDUCE/TIGHTEN_SL/CLOSE",
  "ragione": "spiegazione breve",
  "nuovo_sl_suggerito": float o null,
  "nuovo_tp_suggerito": float o null,
  "scenario_se_su_2_pct": "cosa fai",
  "scenario_se_cvd_negativo": "cosa fai",
  "flessibilita": "note sulla situazione (es: mercato confuso, trend forte, ecc)"
}}
"""
            self._applica_rate_limiting()
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            logging.info(f"[DEBUG_GEMINI_RAW] {response}")
            if not response or not response.text:
                logging.warning("⚠️ Risposta Gemini vuota per valutazione live")
                return None
            valutazione = self._pulisci_e_valida_json(response.text)
            if not valutazione or "confidence" not in valutazione:
                logging.warning("⚠️ JSON invalido per valutazione live")
                return None
            valutazione["confidence"] = max(0, min(100, int(valutazione.get("confidence", 50))))
            valutazione["azione"] = valutazione.get("azione", "HOLD").upper()
            valutazione["ragione"] = valutazione.get("ragione", "Valutazione completata")
            valutazione["flessibilita"] = valutazione.get("flessibilita", "")
            logging.info(
                f"🔍 LIVE EVAL: {valutazione['azione']} "
                f"({valutazione['confidence']}% conf) - {valutazione['ragione'][:50]}"
            )
            return valutazione
        except Exception as e:
            logging.error(f"❌ Errore valutazione live: {e}")
            import traceback; traceback.print_exc()
            return None

# ---------------------------
# Helper a livello modulo (spostato fuori dalla classe per riuso globale)
# ---------------------------
def _estrai_testo_da_response(response):
    """
    Estrae in modo robusto una stringa di testo dalla response del client.
    """
    try:
        # Se è oggetto con .text
        if hasattr(response, "text"):
            return response.text
        # Se è dict
        if isinstance(response, dict):
            if "output" in response:
                out = response["output"]
                if isinstance(out, list):
                    parts = []
                    for it in out:
                        if isinstance(it, dict):
                            parts.append(it.get("content") or it.get("text") or str(it))
                        else:
                            parts.append(str(it))
                    return " ".join(parts)
                return str(out)
            if "candidates" in response:
                cand = response["candidates"]
                if isinstance(cand, list) and cand:
                    first = cand[0]
                    if isinstance(first, dict):
                        return first.get("content") or first.get("text") or str(first)
                    return str(first)
            if "text" in response:
                return response["text"]
            # altrimenti fallback
            return str(response)
        # fallback generico
        return str(response)
    except Exception:
        import traceback; traceback.print_exc()
    return str(response)