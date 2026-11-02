# Harness — plugin autocontido do Crivonansky

Ponto de entrada único do harness de desenvolvimento assistido para o sistema legado
(PHP/MySQL/JS). Recebe blocos `crivonansky` (colados do LLM), executa tarefas do catálogo
e devolve um bloco `crivonansky-result` (no terminal e no clipboard).

A troca com o LLM é **manual**: você copia o bloco do chat, cola na TUI (ou usa
`exec --clip`) e copia o resultado de volta.

## Tudo dentro do plugin

A partir desta versão, o harness não depende de scripts em `C:\projetos`:

```text
commands/complements/harness/
├── install.ps1                  # instalador (venvs + clones + config)
├── requirements.txt             # deps Python do plugin
├── harness.example.yaml         # template da configuração
├── fixture/exemplo-locadora/    # fixture RotaCar (versionada)
├── workspace/                   # harness.yaml + knowledge/ + runs/ (gitignored)
├── vendor/                      # local-rag-system + codeknow (gitignored)
└── .venv/                       # deps do plugin + codeknow (gitignored)
```

O `install.ps1` clona `local-rag-system` e `codeknow` em `vendor/`, cria o venv do
plugin e o venv do RAG, e gera `workspace/harness.yaml` com caminhos absolutos.
O pacote `bootstrap.py` adiciona o site-packages do plugin ao `sys.path` do
crivonansky quando o venv do host não tem as dependências.

## Instalação

O plugin é instalado por `/harness install` (TUI) ou pelo comando equivalente:

```powershell
python crivonansky.py harness install
```

Também é possível executar o instalador diretamente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File commands\complements\harness\install.ps1
```

### O que o `install` faz

1. valida Python 3.13+, Git e Docker (este último é opcional com `--skip-docker`);
2. confere `requirements.txt` e a fixture;
3. clona/atualiza `local-rag-system` e `codeknow` em `vendor/`;
4. cria `commands/complements/harness/.venv` e instala `requirements.txt`;
5. instala `codeknow` em modo editável nesse venv;
6. cria/reaproveita o venv do RAG em `vendor/local-rag-system/.venv`, instala
   `requirements.txt` e extras (`scikit-learn`, `requests`, `pytest`, `httpx`);
7. gera `workspace/harness.yaml` a partir de `harness.example.yaml`, substituindo o
   marcador de raiz do plugin pelo caminho absoluto.

O comando é idempotente: rodar de novo atualiza os clones e revalida as dependências.
Ele **não** sobe contêiner nem inicia a API do RAG.

| Flag | Efeito |
|---|---|
| `--check-only` | Só valida pré-requisitos e mostra os caminhos; não instala |
| `--skip-docker` | Permite instalar em máquina sem Docker |
| `--force` | Regenera `workspace/harness.yaml` mesmo se já existir |

Para reinstalar dependências do zero, remova `vendor/` e/ou `.venv/` e rode
`/harness install` novamente.

## Operação

| Subcomando | O que faz | Flags |
|---|---|---|
| `start` | Sobe MySQL/PHP da fixture e a API do RAG | `--no-rag`, `--no-docker` |
| `stop` | Para o RAG e derruba a fixture | `--purge` |
| `prepare` | `start` + coleta completa + `rag:sync` | `--full`, `--no-rag` |
| `preprocess` | codeknow (cópia + grafo + relatório + wiki) | `--sync`, `--full`, `--no-codeknow`, `--no-wiki` |
| `config` | Mostra caminhos do plugin/workspace/vendor/fixture/venv | — |

```text
/harness start                # MySQL/PHP + API do RAG
/harness start --no-rag       # só a fixture
/harness start --no-docker    # só a API do RAG (não inicia a fixture)
/harness stop                 # para o RAG e a fixture
/harness stop --purge         # e remove o volume do MySQL
/harness prepare              # start + db:snapshot, db:links, docs:import, code:preprocess, rag:sync
/harness prepare --full       # ingestão completa do RAG
/harness preprocess --sync    # code:preprocess + rag:sync
/harness preprocess --no-codeknow  # só copia as fontes
/harness config               # mostra caminhos usados
```

**`start`** verifica o daemon do Docker, executa `fixture/exemplo-locadora/setup.ps1`
(`docker compose up -d --build`, aguarda os `healthcheck` e cria os usuários MySQL) e
define `HARNESS_DB_USER=rotacar_read` / `HARNESS_DB_PASSWORD=readpass` se ainda não
existirem. Se `--no-rag` não for passado, inicia a API em `http://127.0.0.1:8000`.

- `--no-rag`: sobe só a fixture.
- `--no-docker`: não inicia a fixture; sobe só a API do RAG. Não exige Docker e não
  toca nos contêineres.
- `--no-docker --no-rag`: não inicia nada (no-op) e retorna `nada a iniciar`.

**`prepare`** para no primeiro erro e informa em qual tarefa parou. A ordem é fixa:
`db:snapshot` → `db:links` → `docs:import` → `code:preprocess` → `rag:sync`.

**`preprocess`** não exige Docker; trabalha sobre `legacy.repo_path`. `--sync` encadeia
o `rag:sync`; `--full` força o codeknow e a ingestão completa; `--no-wiki` gera grafo e
relatório sem exportar a wiki.

## Uso do contrato

```text
/harness exec --clip | --file F | --stdin [--yes] [--dry-run]
/harness run <task> [--param k=v ...] [--k v] [--yes] [--dry-run]
/harness ask "<pergunta>" [--context rag,code,db]
/harness prompt
/harness tasks
/harness runs [--last N]
/harness hooks install|uninstall|status
/harness env:check
```

Opção global: `--config CAMINHO` (ou a variável `HARNESS_CONFIG`).

### `exec`

Lê blocos `crivonansky` de uma das fontes:

- `--clip` (padrão): área de transferência;
- `--file CAMINHO`: arquivo;
- `--stdin`: entrada padrão.

Cada bloco é validado contra o contrato e o catálogo antes de executar. Blocos
inválidos, tarefa desconhecida ou parâmetro fora do schema retornam `error`/`denied`
sem executar nada. Vários blocos são executados em ordem até
`output.max_blocks_per_message` (padrão 5), parando no primeiro status negativo, salvo
`continue_on_failure: true`. `--yes` é ignorado para blocos vindos de resposta do LLM;
`--dry-run` valida bloco e política, mas não executa.

### `run`

Executa uma tarefa do catálogo diretamente. Parâmetros aceitam `--param k=v` ou
`--k v`:

```text
/harness run db:schema --table tb_veiculos
/harness run db:schema --param table=tb_veiculos
/harness run rag:search --query "como cadastrar cliente" --source_kind db_schema
```

Tarefas de leitura rodam sem confirmação. Tarefas de escrita pedem `y/N`; `--yes` pula a
confirmação somente na linha de comando. `--dry-run` valida a tarefa e a política, mas
não executa.

### `ask` / `prompt`

`ask` monta um prompt com a pergunta e, conforme `--context`, inclui:

- `rag`: trechos de `rag:search` (requer a API do RAG no ar);
- `code`: trechos de `code:query` (requer o grafo gerado);
- `db`: resumo de tabelas/colunas de `workspace/knowledge/db/schema-catalog.json`
  (requer `db:snapshot`).

O padrão é `rag,code`. O texto é copiado para o clipboard e impresso. `prompt` copia
apenas o prompt de instrução do LLM (contrato + regras + catálogo).

### `tasks` / `runs` / `hooks` / `env:check`

- `tasks`: lista `tarefa`, `intent` (`read`/`write`) e descrição.
- `runs --last N`: lista as últimas execuções de `workspace/runs/runs.jsonl`.
- `hooks install|uninstall|status`: instala/remove hooks `post-commit` e `post-merge` no
  repositório legado; `status` mostra o log em `workspace/runs/hooks.log`.
- `env:check`: verifica `git`, `docker info`, `codeknow --version` e `GET /health` do
  RAG. Retorna `failure` se algum item falhar.

## Flags comuns

| Flag | Aplicação | Efeito |
|---|---|---|
| `--config CAMINHO` | qualquer subcomando | Usa outro `harness.yaml` |
| `--yes` | `run`, `exec` | Pula confirmação de escrita (não vale para blocos do LLM) |
| `--dry-run` | `run`, `exec` | Valida tarefa/bloco e política, sem executar |
| `--param k=v` | `run` | Parâmetro da tarefa |
| `--clip` / `--file F` / `--stdin` | `exec` | Fonte dos blocos |
| `--last N` | `runs` | Quantidade listada (padrão 10) |
| `--context rag,code,db` | `ask` | Contextos do prompt |
| `--no-rag` | `start`, `prepare` | Não inicia a API do RAG |
| `--no-docker` | `start` | Não inicia a fixture; sobe somente o RAG |
| `--purge` | `stop` | Remove o volume do MySQL |
| `--full` | `prepare`, `preprocess` | Força codeknow/ingestão completa |
| `--force` | `install` | Regenera o `harness.yaml` |
| `--skip-docker` | `install` | Não exige Docker |
| `--check-only` | `install` | Só valida |
| `--no-codeknow` | `preprocess` | Só copia as fontes |
| `--no-wiki` | `preprocess` | Não exporta a wiki |

## Status e artefatos

| Status | Significado |
|---|---|
| `success` | Tarefa concluída; exit code 0 |
| `failure` | Rodou, mas o resultado foi negativo (ex.: teste falhou) |
| `error` | Erro de bloco, parâmetro ou do harness |
| `denied` | Barrado pela política ou pelo usuário |
| `timeout` | O prazo expirou; o processo foi encerrado |

O `exec` só retorna sucesso se todos os blocos executados tiverem `status: success`.
Cada execução grava `workspace/runs/<id>/command.yaml`, `result.md` e `full.log`, além
de uma linha em `workspace/runs/runs.jsonl`. O clipboard recebe o bloco truncado por
`output.max_chars.clipboard` (padrão 12.000 caracteres); o log completo fica em disco.

A API do RAG grava PID e logs em `workspace/runs/rag-api.pid`, `rag-api.log` e
`rag-api.err.log`.

## Exemplos

```powershell
python crivonansky.py harness run db:snapshot
python crivonansky.py harness run db:schema --table tb_veiculos
python crivonansky.py harness run db:links
python crivonansky.py harness run docs:import
python crivonansky.py harness run code:index
python crivonansky.py harness run code:preprocess
python crivonansky.py harness run rag:serve --action start
python crivonansky.py harness run rag:sync
python crivonansky.py harness run rag:search --query "como cadastrar cliente" --source_kind db_schema
```

## Contrato

Entrada (um bloco por ação):

```crivonansky
harness: 1
task: db:schema
params:
  table: tb_veiculos
return: auto
```

Saída:

```crivonansky-result
harness: 1
id: c-0007
task: db:schema
status: success
exit_code: 0
duration_ms: 12
summary: "schema da tabela tb_veiculos"
truncated: false
details: |
  # Tabela: tb_veiculos
  ...
```

`status`: `success` | `failure` | `error` | `denied` | `timeout`.

## Tarefas

| Tarefa | Intent | Descrição |
|---|---|---|
| `env:check` | read | Verifica git, docker, codeknow e RAG |
| `context:pack` | read | Empacota arquivos em Markdown |
| `file:read` | read | Lê arquivo com números de linha |
| `code:index` | read | Gera o grafo com codeknow |
| `code:preprocess` | read | Copia fontes + grafo + wiki do codeknow p/ o RAG |
| `code:query` | read | Consulta o grafo |
| `code:impact` | read | Impacto de alterar um símbolo |
| `db:snapshot` | read | Schema MySQL (docker exec ou dump) |
| `db:schema` | read | Markdown de uma tabela |
| `db:query` | read | SELECT/SHOW/DESCRIBE/EXPLAIN |
| `db:links` | read | SQL embutido + FKs inferidas + includes + visões `tables/*.md` |
| `docs:import` | read | Manuais e tickets |
| `rag:serve` | read | Inicia/para/consulta a API local do RAG |
| `rag:sync` | read | Publica no RAG e ingere |
| `rag:search` | read | Busca no RAG |
| `git:run` | read/write | Comando git |
| `shell:run` | write | Shell do Windows |
| `py:run` | write | Script/módulo Python |
| `docker:exec` | write | Comando no contêiner |
| `logs:tail` | read | Logs de contêiner |
| `patch:apply` | write | Aplica diff e verifica |
| `test:run` / `verify` / `lint` | read | Pipelines do `harness.yaml` |
| `prompt` | read | Prompt do LLM no clipboard |

Tarefas `write` pedem confirmação. Blocos vindos do LLM nunca aceitam `--yes`.

## Configuração

Gerada em `workspace/harness.yaml` pelo `install.ps1`. O template
(`harness.example.yaml`) usa caminhos relativos ao plugin; o instalador troca o
marcador `{{PLUGIN_ROOT}}` pelo caminho absoluto. Também é possível apontar para
outro arquivo com `--config` ou `HARNESS_CONFIG`.

## Testes

```powershell
# de dentro de cli-crivonansky
.\.venv\Scripts\python.exe -m pytest tests/harness -q

# ou com o venv do plugin
commands\complements\harness\.venv\Scripts\python.exe -m pytest tests/harness -q
```
