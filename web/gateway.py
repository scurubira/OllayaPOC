"""Gateway de modelos locais e APIs externas compatíveis com OpenAI."""
import json
import math
import os
import urllib.error
import urllib.request

DEFAULT_MODELS = (
    {
        "id": "openai",
        "name": "OpenAI",
        "provider": "openai-compatible",
        "model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "provider": "openai-compatible",
        "model": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini"),
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
    },
    {
        "id": "groq",
        "name": "Groq",
        "provider": "openai-compatible",
        "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
    },
)


def configured_models():
    models = [{
        "id": "local",
        "name": "Ollaya local",
        "provider": "ollaya",
        "model": "laya:multilingual",
        "available": True,
    }]
    candidates = list(DEFAULT_MODELS)
    custom = os.environ.get("AI_GATEWAY_MODELS", "").strip()
    if custom:
        parsed = json.loads(custom)
        if not isinstance(parsed, list):
            raise ValueError("AI_GATEWAY_MODELS deve ser uma lista JSON.")
        candidates.extend(parsed)

    used_ids = {"local"}
    for candidate in candidates:
        model_id = candidate.get("id", "")
        key_env = candidate.get("api_key_env", "")
        if (not model_id or model_id in used_ids or
                candidate.get("provider") != "openai-compatible"):
            continue
        used_ids.add(model_id)
        models.append({
            **candidate,
            "available": bool(key_env and os.environ.get(key_env)),
        })
    return models


def public_models():
    return [{key: value for key, value in model.items()
             if key not in {"api_key_env", "base_url"}}
            for model in configured_models()]


def get_model(model_id):
    for model in configured_models():
        if model["id"] == model_id:
            if not model["available"]:
                raise ValueError(f"O modelo {model['name']} não possui credencial configurada.")
            return model
    raise ValueError("Modelo desconhecido.")


def build_prompt(text, questions):
    schema = {}
    for name, question in questions.items():
        kind = question["type"]
        if kind == "choice":
            schema[name] = {
                "type": "choice",
                "choice": f"uma destas opções: {list(question['criteria'])}",
                "confidence": "número de 0 a 1",
                "probabilities": "objeto com todas as opções e probabilidades de 0 a 1",
            }
        elif kind == "score":
            maximum = len(question["criteria"]) - 1
            schema[name] = {
                "type": "score",
                "score": f"número de 0 a {maximum}",
                "confidence": "número de 0 a 1",
                "probabilities": f"objeto com chaves de 0 a {maximum}",
            }
        else:
            schema[name] = {"type": "noul", "noul": "probabilidade de 0 a 1"}
    return (
        "Analise o texto segundo todas as perguntas fornecidas. Responda somente "
        "com JSON válido, sem markdown ou explicações. Não invente fatos ausentes.\n\n"
        f"PERGUNTAS:\n{json.dumps(questions, ensure_ascii=False)}\n\n"
        f"FORMATO EXATO DE answers:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"TEXTO:\n{text}"
    )


def parse_json_content(content):
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(content)
    return parsed.get("answers", parsed)


def validate_answers(answers, questions):
    if not isinstance(answers, dict):
        raise ValueError("O modelo externo não retornou um objeto de respostas.")
    for name, question in questions.items():
        answer = answers.get(name)
        if not isinstance(answer, dict) or answer.get("type") != question["type"]:
            raise ValueError(f"Resposta externa inválida para {name}.")
        kind = question["type"]
        if kind == "choice":
            if answer.get("choice") not in question["criteria"]:
                raise ValueError(f"Opção externa desconhecida em {name}.")
        else:
            value = answer.get(kind)
            maximum = len(question["criteria"]) - 1 if kind == "score" else 1
            if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                    not math.isfinite(value) or not 0 <= value <= maximum):
                raise ValueError(f"Valor externo fora da escala em {name}.")
    return answers


def external_decide(model, text, questions, timeout=120):
    api_key = os.environ[model["api_key_env"]]
    payload = {
        "model": model["model"],
        "messages": [
            {"role": "system", "content": "Você é um classificador rigoroso que produz somente JSON."},
            {"role": "user", "content": build_prompt(text, questions)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        model["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Ollaya-Insights/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    content = result["choices"][0]["message"]["content"]
    answers = validate_answers(parse_json_content(content), questions)
    usage = result.get("usage", {})
    return {"answers": answers, "usage": usage}
