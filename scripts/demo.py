#!/usr/bin/env python3
"""Cliente da API local, sem dependências externas."""
import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:11435"


PROFILES = {
    "triagem": ("questions.json", "examples/tickets.json", "demo.json"),
    "telecom": ("questions.telecom.json", "examples/telecom.json", "telecom.json"),
    "futebol": ("questions.futebol.json", "examples/futebol.json", "futebol.json"),
}


def validate_answers(result, questions):
    answers = result["answers"]
    for name, question in questions.items():
        answer = answers[name]
        kind = question["type"]
        if answer.get("type") != kind:
            raise ValueError(f"Tipo inesperado na resposta {name}")
        if kind == "choice":
            if answer["choice"] not in question["criteria"]:
                raise ValueError(f"Opção desconhecida em {name}")
        else:
            value = answer[kind]
            maximum = len(question["criteria"]) - 1 if kind == "score" else 1
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or not 0 <= value <= maximum):
                raise ValueError(f"Valor fora da escala em {name}: {value}")


def decide(text, profile="triagem"):
    if not text.strip():
        raise ValueError("Informe uma situação para avaliar.")
    questions = json.loads((ROOT / PROFILES[profile][0]).read_text(encoding="utf-8"))
    body = {
        "model": "laya:multilingual",
        "state": text,
        "questions": questions,
        "keep_alive": "10m",
    }
    request = urllib.request.Request(
        BASE_URL + "/api/decide",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.load(response)
    if result.get("state_truncated"):
        raise ValueError("Texto truncado pelo modelo; reduza o tamanho da situação.")
    validate_answers(result, questions)
    return {"texto": text, "tempo_cliente_ms": round((time.perf_counter() - start) * 1000, 2), "resposta": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("texto", nargs="?", help="Chamado a classificar; omitido: executa os exemplos")
    parser.add_argument("--perfil", choices=PROFILES, default="triagem",
                        help="Perfil de perguntas: triagem, telecom ou futebol")
    args = parser.parse_args()
    if args.texto:
        print(json.dumps(decide(args.texto, args.perfil), ensure_ascii=False, indent=2))
        return
    tickets = json.loads((ROOT / PROFILES[args.perfil][1]).read_text(encoding="utf-8"))
    results = []
    for ticket in tickets:
        item = decide(ticket["texto"], args.perfil)
        if args.perfil != "triagem":
            results.append(item)
            answers = item["resposta"]["answers"]
            print(f"\n{ticket['titulo']} ({item['tempo_cliente_ms']:.0f} ms)")
            for name, answer in answers.items():
                value = answer.get("choice", answer.get("score", answer.get("noul")))
                print(f"  {name}: {value}")
            continue
        expected = ticket["departamento_esperado"]
        actual = item["resposta"]["answers"]["departamento"]["choice"]
        item.update(departamento_esperado=expected, acertou=actual == expected)
        results.append(item)
        print(f"{actual:18} | esperado: {expected:18} | {item['tempo_cliente_ms']:.0f} ms")
    output = ROOT / "results" / PROFILES[args.perfil][2]
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.perfil != "triagem":
        print(f"\nAvaliações: {len(results)}. Resultado completo: {output}")
        print("Classificações geradas pelo modelo; confirme fatos em fontes atualizadas.")
        return
    correct = sum(item["acertou"] for item in results)
    print(f"\nClassificação: {correct}/{len(results)} exemplos. Resultado: {output}")
    print("Amostra ilustrativa; não mede a acurácia em produção. A primeira chamada inclui o carregamento.")
    if correct != len(results):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"API retornou HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Não foi possível consultar a API: {exc}. Execute ./scripts/ollaya list para iniciar.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Resposta inválida: {exc}", file=sys.stderr)
        sys.exit(1)
