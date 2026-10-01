#!/usr/bin/env python3
"""Servidor web para executar os perfis de insights via Ollaya."""
import json
import os
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
OLLAYA_URL = os.environ.get("OLLAYA_BASE_URL", "http://127.0.0.1:11435").rstrip("/")
PORT = int(os.environ.get("PORT", "8080"))
MAX_TEXT_LENGTH = 20_000
MAX_BATCH_SIZE = 50

PROFILES = {
    "triagem": {
        "name": "Triagem de chamados",
        "description": "Departamento, urgência e intenção de reembolso",
        "questions": "questions.json",
        "accent": "#d95d39",
    },
    "telecom": {
        "name": "Decisão executiva",
        "description": "Prioridade, impacto e frente de gestão em telecom",
        "questions": "questions.telecom.json",
        "accent": "#087e8b",
    },
    "futebol": {
        "name": "Futebol",
        "description": "Brasileirão e Libertadores",
        "questions": "questions.futebol.json",
        "accent": "#217a3c",
    },
}


def load_questions(profile):
    return json.loads((ROOT / PROFILES[profile]["questions"]).read_text(encoding="utf-8"))


def ollaya_request(path, payload=None, timeout=300):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    request = urllib.request.Request(
        OLLAYA_URL + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def evaluate(profile, text):
    if profile not in PROFILES:
        raise ValueError("Perfil desconhecido.")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Informe um texto para avaliar.")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"O texto deve ter no máximo {MAX_TEXT_LENGTH} caracteres.")

    start = time.perf_counter()
    result = ollaya_request("/api/decide", {
        "model": "laya:multilingual",
        "state": text.strip(),
        "questions": load_questions(profile),
        "keep_alive": "10m",
    })
    if result.get("state_truncated"):
        raise ValueError("O modelo truncou o texto. Reduza o conteúdo e tente novamente.")
    return {
        "text": text.strip(),
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
        "answers": result.get("answers", {}),
        "usage": result.get("usage", {}),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}", flush=True)

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/config":
            profiles = {}
            for key, profile in PROFILES.items():
                profiles[key] = {**profile, "questions": load_questions(key)}
            self.send_json({"profiles": profiles, "max_batch_size": MAX_BATCH_SIZE})
            return
        if self.path == "/api/health":
            try:
                tags = ollaya_request("/api/tags", timeout=5)
                names = [model.get("name") for model in tags.get("models", [])]
                ready = "laya:multilingual" in names
                self.send_json({"status": "ready" if ready else "model_missing", "models": names},
                               HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE)
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                self.send_json({"status": "unavailable", "error": str(exc)},
                               HTTPStatus.SERVICE_UNAVAILABLE)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/evaluate":
            self.send_json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 1_000_000:
                raise ValueError("Corpo da requisição vazio ou muito grande.")
            payload = json.loads(self.rfile.read(content_length))
            profile = payload.get("profile", "")
            if "items" in payload:
                items = payload["items"]
                if not isinstance(items, list) or not 1 <= len(items) <= MAX_BATCH_SIZE:
                    raise ValueError(f"Envie de 1 a {MAX_BATCH_SIZE} itens por lote.")
                results = []
                for index, item in enumerate(items):
                    text = item.get("texto", "") if isinstance(item, dict) else ""
                    result = evaluate(profile, text)
                    result["title"] = item.get("titulo", f"Item {index + 1}")
                    results.append(result)
                self.send_json({"profile": profile, "results": results})
                return
            self.send_json({"profile": profile, "result": evaluate(profile, payload.get("text", ""))})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            self.send_json({"error": f"Ollaya respondeu HTTP {exc.code}.", "detail": detail},
                           HTTPStatus.BAD_GATEWAY)
        except (urllib.error.URLError, TimeoutError) as exc:
            self.send_json({"error": "Não foi possível acessar a Ollaya.", "detail": str(exc)},
                           HTTPStatus.BAD_GATEWAY)


if __name__ == "__main__":
    print(f"Interface em http://0.0.0.0:{PORT} | Ollaya: {OLLAYA_URL}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
