#!/usr/bin/env python3
"""Avalia uma lista de textos em lote e exporta resultados para CSV/JSON.

Exemplos de uso:

    python3 scripts/batch.py examples/tickets.json --perfil triagem
    python3 scripts/batch.py meus_cenarios.json --perfil telecom -o resultados.csv

O arquivo de entrada deve conter uma lista JSON de objetos com pelo menos o
 campo "texto". Opcionalmente inclua "titulo" (qualquer perfil) ou
"departamento_esperado" (perfil triagem) para comparação.
"""
import argparse
import csv
import json
import sys
import urllib.error
from pathlib import Path

from demo import PROFILES, decide

ROOT = Path(__file__).resolve().parent.parent


def flatten_triage(item):
    answers = item["resposta"]["answers"]
    return {
        "texto": item["texto"],
        "departamento": answers["departamento"]["choice"],
        "urgencia": answers["urgencia"]["score"],
        "pede_reembolso": answers["pede_reembolso"]["noul"],
        "tempo_cliente_ms": item["tempo_cliente_ms"],
        "departamento_esperado": item.get("departamento_esperado", ""),
        "acertou": item.get("acertou", ""),
    }


def flatten_telecom(item):
    answers = item["resposta"]["answers"]
    return {
        "titulo": item.get("titulo", ""),
        "texto": item["texto"],
        "frente_prioritaria": answers["frente_prioritaria"]["choice"],
        "prioridade": answers["prioridade"]["score"],
        "impacto_negocio": answers["impacto_negocio"]["score"],
        "requer_decisao_executiva": answers["requer_decisao_executiva"]["noul"],
        "faltam_dados": answers["faltam_dados"]["noul"],
        "tempo_cliente_ms": item["tempo_cliente_ms"],
    }


def flatten_futebol(item):
    answers = item["resposta"]["answers"]
    return {
        "titulo": item.get("titulo", ""),
        "texto": item["texto"],
        "competicao": answers["competicao"]["choice"],
        "assunto_principal": answers["assunto_principal"]["choice"],
        "relevancia": answers["relevancia"]["score"],
        "exige_dados_atualizados": answers["exige_dados_atualizados"]["noul"],
        "faltam_dados": answers["faltam_dados"]["noul"],
        "tempo_cliente_ms": item["tempo_cliente_ms"],
    }


def write_csv(rows, output_path, fieldnames):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", help="Arquivo JSON com a lista de textos")
    parser.add_argument("--perfil", choices=PROFILES, default="triagem",
                        help="Perfil de perguntas a usar")
    parser.add_argument("-o", "--saida", help="Caminho do CSV de saída")
    parser.add_argument("--json", action="store_true",
                        help="Gravar também o resultado completo em JSON")
    args = parser.parse_args()

    entrada = Path(args.entrada)
    if not entrada.is_absolute():
        entrada = ROOT / entrada
    itens = json.loads(entrada.read_text(encoding="utf-8"))

    if not isinstance(itens, list):
        raise ValueError("O arquivo de entrada deve conter uma lista JSON.")

    results = []
    erros = 0
    for i, item in enumerate(itens, start=1):
        texto = item.get("texto", "")
        if not texto:
            print(f"Ignorando item {i}: campo 'texto' vazio.", file=sys.stderr)
            erros += 1
            continue
        try:
            result = decide(texto, args.perfil)
            if args.perfil == "triagem":
                esperado = item.get("departamento_esperado")
                if esperado:
                    atual = result["resposta"]["answers"]["departamento"]["choice"]
                    result["departamento_esperado"] = esperado
                    result["acertou"] = atual == esperado
            if args.perfil != "triagem" and item.get("titulo"):
                result["titulo"] = item["titulo"]
            results.append(result)
            print(f"{i}/{len(itens)} processado em {result['tempo_cliente_ms']:.0f} ms")
        except Exception as exc:
            print(f"Erro no item {i}: {exc}", file=sys.stderr)
            erros += 1

    flatten = {
        "triagem": flatten_triage,
        "telecom": flatten_telecom,
        "futebol": flatten_futebol,
    }[args.perfil]
    rows = [flatten(r) for r in results]

    if not args.saida:
        nome_base = entrada.stem
        args.saida = ROOT / "results" / f"{nome_base}.csv"
    output_csv = Path(args.saida)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_csv(rows, output_csv, fieldnames=list(rows[0].keys()) if rows else [])
    print(f"CSV salvo: {output_csv}")

    if args.json:
        output_json = output_csv.with_suffix(".json")
        output_json.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"JSON salvo: {output_json}")

    if args.perfil == "triagem":
        total = sum(1 for r in results if "acertou" in r)
        acertos = sum(1 for r in results if r.get("acertou"))
        if total:
            print(f"Acurácia sobre itens com rótulo: {acertos}/{total} "
                  f"({100 * acertos / total:.1f}%)")

    if erros:
        print(f"{erros} item(ns) com erro.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"API retornou HTTP {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Não foi possível consultar a API: {exc}. "
              f"Execute ./scripts/ollaya list para iniciar.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"Resposta inválida: {exc}", file=sys.stderr)
        sys.exit(1)
