# Ollaya — prova de conceito local

Triagem de chamados em português com `laya:multilingual`: departamento,
urgência (0–2) e probabilidade de pedido de reembolso (0–1).
O cenário é ilustrativo e pode ser adaptado em `questions.json`.

## Executar

No terminal, dentro desta pasta:

```sh
./scripts/ollaya list
python3 scripts/demo.py
python3 scripts/demo.py 'Fui cobrado duas vezes e quero meu dinheiro de volta.'
```

`list` inicia a API em segundo plano quando necessário. A demonstração com
três exemplos grava respostas completas e tempos em `results/demo.json`.
A primeira chamada inclui o carregamento do modelo; os tempos seguintes
representam chamadas com o modelo já carregado.

## Interface gráfica com Docker

Com a API Ollaya iniciada no macOS, suba o dashboard:

```sh
./scripts/ollaya list
docker compose up --build -d
```

Abra `http://localhost:8080`. A interface oferece os perfis de triagem,
decisão executiva em telecom e futebol, com análise individual, lote JSON,
histórico da sessão e exportação dos resultados.

O contêiner contém apenas a aplicação web. Ele acessa a API e os modelos no
host por `host.docker.internal:11435`, evitando copiar os modelos para a
imagem. Para acompanhar ou encerrar:

```sh
docker compose logs -f insights
docker compose down
```

### AI Gateway e modelos externos

O seletor de modelos inclui Ollaya local, OpenAI, OpenRouter e Groq. Provedores
externos ficam desabilitados até receberem uma chave no backend. Copie
`.env.example` para `.env`, preencha somente o provedor desejado e reconstrua:

```sh
cp .env.example .env
# Edite .env sem compartilhar ou versionar as chaves.
docker compose up --build -d
```

O arquivo `.env` é ignorado pelo Git e as chaves nunca são enviadas ao
navegador. Para adicionar outro endpoint compatível com OpenAI, configure
`AI_GATEWAY_MODELS` conforme o exemplo comentado em `.env.example` e repasse a
variável de chave correspondente no `docker-compose.yml`.

Para usar o modelo personalizado pela CLI:

```sh
./scripts/ollaya create triagem-poc -f Modelfile
./scripts/ollaya run triagem-poc 'Esqueci a senha da minha conta.'
```

Depois de editar as perguntas, execute `create` novamente para atualizar
`triagem-poc`. O cliente Python lê `questions.json` a cada execução.

## Configuração

## Avaliação executiva de telecom

```sh
python3 scripts/demo.py --perfil telecom
python3 scripts/demo.py --perfil telecom 'Uma falha deixou 80 mil clientes sem internet e a recuperação deve levar quatro horas. É necessário coordenar rede e atendimento hoje.'
```

O perfil `telecom` envia a situação para `/api/decide` com as perguntas de
`questions.telecom.json`. Retorna a frente prioritária, prioridade e impacto
no negócio (escalas 0–3), além das probabilidades (0–1) de necessidade de decisão
executiva e de falta de dados. Os escores podem ser fracionários; as legendas e
probabilidades completas estão no JSON retornado.

Sem texto, avalia três situações fictícias: interrupção de rede, cancelamentos
e expansão 5G, e salva `results/telecom.json`. São exemplos de integração, sem
rótulos de acerto executivo. A probabilidade expressa a avaliação do modelo,
não uma medição do risco real. As respostas apoiam a análise do executivo;
não constituem aprovação de investimento ou execução automática de ações.

Para chamar a função em Python: `decide(situacao, profile="telecom")`.
O perfil padrão de triagem permanece disponível sem `--perfil`.

## Futebol: Brasileirão e Libertadores

O perfil `futebol` classifica perguntas e textos sobre Campeonato Brasileiro e
Libertadores por competição, assunto e relevância. Também estima se a resposta
exige dados atualizados e se faltam informações no texto.

```sh
python3 scripts/demo.py --perfil futebol
python3 scripts/demo.py --perfil futebol 'Quais resultados podem alterar o G4 do Brasileirão nesta rodada?'
python3 scripts/batch.py examples/futebol.json --perfil futebol -o results/futebol_batch.csv --json
```

As perguntas do perfil estão em `questions.futebol.json` e os dez casos de
teste em `examples/futebol.json`. O modelo classifica o conteúdo fornecido, mas
não consulta automaticamente resultados, tabelas ou escalações em tempo real.

Para uma avaliação única com resumo executivo, use o script dedicado:

```sh
python3 scripts/avaliar_executivo.py 'descrição da situação'
python3 scripts/avaliar_executivo.py --json 'descrição da situação'
```

O script `scripts/avaliar_executivo.py` reutiliza `decide()` do perfil
telecom e apresenta frente prioritária, prioridade e impacto com as legendas
das escalas, além das probabilidades em percentual. `--json` retorna a
avaliação completa para integração com outras ferramentas.

## Configuração do ambiente

- Ollaya CLI: versão 0.8.0, instalada em `.runtime/`.
- Modelo: `laya:multilingual`, executado em CPU.
- API local: `http://127.0.0.1:11435`.
- Modelos: `.data/models/`; logs: `.data/logs/server.log`.
- Até um modelo carregado; descarregamento após 10 minutos sem uso.
- Cliente: Python 3, somente biblioteca padrão.

Use `./scripts/ollaya` para aplicar a configuração deste projeto.
As configurações estão explícitas nesse script. Não requer alteração do PATH.

```sh
./scripts/ollaya ps           # modelos na memória
./scripts/ollaya stop         # parar o servidor local
```

## Reinstalar

Requisitos: Mac Apple Silicon com macOS 14 ou posterior e Python 3.
O instalador oficial foi preservado em `scripts/install-official.sh`.
Ele verifica o SHA-256 dos arquivos publicados. Dentro desta pasta:

```sh
OLLAYA_VERSION=0.8.0 OLLAYA_INSTALL_DIR="$PWD/.runtime" \
  OLLAYA_NO_SERVICE=1 OLLAYA_NO_CUDA=1 sh scripts/install-official.sh
./scripts/ollaya pull laya:multilingual
./scripts/ollaya create triagem-poc -f Modelfile
python3 scripts/demo.py
```

A instalação e o download do modelo precisam de internet. Depois do download,
as inferências usam a API e o modelo locais. O modelo é baixado pelo nome/tag
do registro, que pode mudar; `./scripts/ollaya list` mostra o ID instalado.

## Avaliação

Validação local em 01/10/2026: **3/3 departamentos corretos**. Primeira chamada:
4.680 ms incluindo carregamento; seguintes: 60 ms e 64 ms. Modelo instalado:
`laya:multilingual`, ID `2840506e1f97`. Respostas completas em `results/demo.json`.

Os três exemplos verificam integração e classificações básicas; não demonstram
acurácia em produção. Para avaliar o seu caso, amplie `examples/tickets.json`
com chamados representativos e rótulos esperados. A demonstração termina com
código 1 se uma classificação divergir. Requisições com texto truncado também
são rejeitadas pelo cliente.

Fontes: [projeto oficial](https://github.com/ollaya-dev/ollaya),
[instalação](https://ollaya.dev/download),
[CLI e configuração](https://ollaya.dev/docs/cli),
[API](https://ollaya.dev/docs/api).
