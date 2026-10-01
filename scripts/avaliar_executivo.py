#!/usr/bin/env python3
"""Avalia uma situação de telecom para apoio à decisão executiva.

Uso:
    python3 scripts/avaliar_executivo.py 'descrição da situação'
    python3 scripts/avaliar_executivo.py --json 'descrição da situação'

Envia a situação para a API local (perfil telecom) e apresenta a frente
prioritária, prioridade e impacto no negócio (escalas 0–3), além das
probabilidades (0–1) de necessidade de decisão executiva e de falta de dados.
As respostas apoiam a análise do executivo; não autorizam ações ou
investimentos.
"""
import argparse
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo import PROFILES, decide  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_questions():
    return json.loads((ROOT / PROFILES["telecom"][0]).read_text(encoding="utf-8"))


def score_label(value, criteria):
    index = max(0, min(round(value), len(criteria) - 1))
    return criteria[index]


def summarize(text):
    result = decide(text, profile="telecom")
    answers = result["resposta"]["answers"]
    questions = load_questions()
    frente = answers["frente_prioritaria"]
    return {
        "tempo_cliente_ms": result["tempo_cliente_ms"],
        "frente_prioritaria": {
            "codigo": frente["choice"],
            "descricao": questions["frente_prioritaria"]["criteria"][frente["choice"]],
        },
        "prioridade": {
            "valor": answers["prioridade"]["score"],
            "descricao": score_label(answers["prioridade"]["score"],
                                     questions["prioridade"]["criteria"]),
        },
        "impacto_negocio": {
            "valor": answers["impacto_negocio"]["score"],
            "descricao": score_label(answers["impacto_negocio"]["score"],
                                     questions["impacto_negocio"]["criteria"]),
        },
        "requer_decisao_executiva": answers["requer_decisao_executiva"]["noul"],
        "faltam_dados": answers["faltam_dados"]["noul"],
    }


def print_summary(text, summary):
    print(f"Situação: {text}\n")
    print(f"Frente prioritária:  {summary['frente_prioritaria']['codigo']}"
          f" — {summary['frente_prioritaria']['descricao']}")
    print(f"Prioridade (0–3):    {summary['prioridade']['valor']:.2f}"
          f" — {summary['prioridade']['descricao']}")
    print(f"Impacto no negócio:  {summary['impacto_negocio']['valor']:.2f}"
          f" — {summary['impacto_negocio']['descricao']}")
    print(f"Decisão executiva:   {summary['requer_decisao_executiva']:.0%}")
    print(f"Faltam dados:        {summary['faltam_dados']:.0%}")
    print(f"\nTempo de chamada: {summary['tempo_cliente_ms']:.0f} ms")
    print("Avaliação do modelo para apoiar a análise; não autoriza ações ou investimentos.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("situacao", help="Situação de telecom a avaliar")
    parser.add_argument("--json", action="store_true", help="Saída completa em JSON")
    args = parser.parse_args()
    summary = summarize(args.situacao)
    if args.json:
        print(json.dumps({"situacao": args.situacao, "avaliacao": summary},
                         ensure_ascii=False, indent=2))
        return
    print_summary(args.situacao, summary)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"API retornou HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Não foi possível consultar a API: {exc}. Execute ./scripts/ollaya list para iniciar.",
              file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Resposta inválida: {exc}", file=sys.stderr)
        sys.exit(1)
