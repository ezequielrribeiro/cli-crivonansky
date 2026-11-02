# Crivonansky CLI

Framework de CLI extensível com interface TUI (Terminal User Interface) baseada em [Textual](https://textual.textualize.io/).

![Crivonansky TUI](https://img.shields.io/badge/CLI-TUI-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

---

## Funcionalidades

- Interface TUI com input, output com scroll e dropdown de comandos
- Carregamento dinâmico de plugins (basta criar um arquivo em `commands/`)
- Comandos com prefixo `/` e suporte a argumentos (`--flag valor`)
- Histórico de comandos navegável com `↑`/`↓`
- Dropdown de comandos ao digitar `/`
- Geração automática de novos plugins via comando interno
- Task runner no estilo gulp.js (tasks com src/dest, series/parallel, watch mode)
- Integração híbrida: tasks podem chamar comandos da CLI via `cmd()`
- API REST (FastAPI) que executa comandos da CLI via HTTP

---

## Requisitos

- Python 3.10+
- pip

## Instalação

```bash
cd crivonansky
pip install -r requirements.txt
```

## Execução

```bash
python crivonansky.py
```

### REST API

Para subir a API REST (FastAPI) e executar comandos via HTTP:

```bash
python api_server.py            # ou .\api.ps1 (ativa o .venv)
```

Opções: `--host` (default `127.0.0.1`), `--port` (default `8000`), `--reload` (hot-reload do uvicorn). Veja a seção [API REST](#api-rest).

---

## Comandos disponíveis

| Comando | Descrição |
|---|---|
| `/help` | Lista todos os comandos disponíveis |
| `/clear` | Limpa a tela |
| `/quit` | Sai da aplicação |
| `/task` | Controle de tarefas (start/resume/report) |
| `/environment` | Gerencia ambientes Docker via docker-compose. Subcomandos: `list`, `start`, `stop`, `init` |
| `/metrics-report` | Relatório trimestral de métricas |
| `/load-app` | Lança apps e move para desktops virtuais |
| `/db-tools` | Otimizador/instalador de dumps MySQL |
| `/container-terminal` | Terminal PowerShell em container Docker |
| `/convert-site` | Converte URL para Markdown |
| `/site-capture` | Captura página via Selenium como Markdown |
| `/generate-plugin --name <nome>` | Gera um novo plugin de comando |
| `/send-capoeira-host` | Envia um prompt para um LLM via API do [CapoeiraHost](https://github.com/ezequielrribeiro/capoeira-host) |
| `/run-git-cmd` | Executa um comando `git` em um diretório raiz informado |
| `/docker-container-run` | Executa um comando dentro de um container Docker Linux |
| `/run` | Task runner (gulp.js-style). Subcomandos: `run <task>`, `--tasks`, `watch <task>`, `init` |
| `/harness` | Harness de desenvolvimento assistido (plugin autocontido). Subcomandos: `install`, `start`, `stop`, `prepare`, `preprocess`, `run`, `exec`, `tasks`, `env:check` |

### Ambientes Docker (`/environment`)

O comando lê `environment_conf.json` na raiz do projeto. Para criar um arquivo de exemplo:

```text
/environment init
```

O arquivo criado tem o formato:

```json
{
  "environments": {
    "meu-projeto": "C:/caminho/para/o/docker-compose.yml"
  }
}
```

Cada chave é o nome usado nos demais subcomandos e o valor é o caminho absoluto do
`docker-compose.yml`. Use barras normais (`C:/...`) ou escape as invertidas (`C:\\...`).
Se o arquivo já existir, `init` não sobrescreve — use `init --force` para recriá-lo.

```text
/environment list                # status dos ambientes e containers
/environment list --running
/environment start meu-projeto
/environment stop meu-projeto
```

### Harness (`/harness`)

O comando `/harness` é um plugin autocontido em
`commands/complements/harness/`. Ele instala e opera o harness de desenvolvimento
assistido, com venv, dependências, fixture, workspace e configuração próprios.

Quando chamado com argumentos, executa o subcomando e sai com exit code (sem abrir a
TUI). Sem argumentos, abre a TUI normalmente.

| Subcomando | Uso | O que faz |
|---|---|---|
| `install` | `install [--force] [--skip-docker] [--check-only]` | Valida pré-requisitos, clona `vendor/`, cria os venvs e gera `workspace/harness.yaml` |
| `start` | `start [--no-rag] [--no-docker]` | Sobe a fixture MySQL/PHP e a API do RAG (`--no-docker` sobe só o RAG) |
| `stop` | `stop [--purge]` | Para o RAG e a fixture (`--purge` remove o volume) |
| `prepare` | `prepare [--full] [--no-rag]` | Executa `db:snapshot`, `db:links`, `docs:import`, `code:preprocess`, `rag:sync` |
| `preprocess` | `preprocess [--sync] [--full] [--no-codeknow] [--no-wiki]` | Copia o legado e roda o codeknow |
| `config` | `config` | Mostra plugin, config, workspace, vendor, fixture e venv |
| `exec` | `exec --clip \| --file F \| --stdin [--yes] [--dry-run]` | Executa blocos `crivonansky` |
| `run` | `run <task> [--param k=v ...] [--yes] [--dry-run]` | Executa uma tarefa do catálogo |
| `ask` | `ask "pergunta" [--context rag,code,db]` | Monta prompt com contexto e copia para o clipboard |
| `prompt` | `prompt` | Copia o prompt de instrução do LLM |
| `tasks` | `tasks` | Lista o catálogo de tarefas |
| `runs` | `runs [--last N]` | Lista o histórico de execuções |
| `hooks` | `hooks install\|uninstall\|status` | Gerencia hooks `post-commit`/`post-merge` |
| `env:check` | `env:check` | Diagnostica git, Docker, codeknow e RAG |

Opções globais e ambiente:

- `--config CAMINHO` ou `HARNESS_CONFIG` escolhem outro `harness.yaml`;
- `HARNESS_DB_USER` / `HARNESS_DB_PASSWORD` alimentam as tarefas `db:*`
  (o `start` define `rotacar_read`/`readpass` por padrão).

Exemplos:

```powershell
# ciclo completo
python crivonansky.py harness install
python crivonansky.py harness start
python crivonansky.py harness start --no-docker   # só o RAG, sem fixture
python crivonansky.py harness prepare
python crivonansky.py harness stop --purge

# uso do contrato
python crivonansky.py harness run db:schema --table tb_veiculos
python crivonansky.py harness exec --clip
python crivonansky.py harness ask "como funciona o aluguel?" --context rag,code

# diagnóstico
python crivonansky.py harness config
python crivonansky.py harness env:check
```

Tarefas de leitura rodam direto; tarefas de escrita pedem confirmação `y/N`. O `--yes`
não vale para blocos vindos de resposta do LLM. Toda execução grava
`commands/complements/harness/workspace/runs/<id>/` e gera um bloco
`crivonansky-result`. A referência completa (flags, status e artefatos) e o passo a passo
para apontar o harness para um projeto real estão em
`commands/complements/harness/README.md`.

### Comandos utilitários

```bash
# Envia um prompt em texto plano para um LLM via CapoeiraHost
/send-capoeira-host --host 127.0.0.1 --port 8080 --prompt "um texto \"qualquer\""
/send-capoeira-host --prompt "resuma este texto" --model claude-sonnet --system "seja breve"

# Executa um comando git em um diretório raiz (o comando deve iniciar com "git")
/run-git-cmd --root-dir "C:\projetos\projeto-exemplo" --command "git diff --check"

# Executa um comando dentro de um container Docker Linux
/docker-container-run --container php-5 --command "php -v"
```

Os três comandos imprimem o output na tela do Crivonansky **e** o devolvem em
`data.output` (`(sucesso, dados)`), permitindo consumir o resultado em fluxos
criados com `/run` (via `cmd()`).

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Enter` | Executa comando ou seleciona item do dropdown |
| `↑` / `↓` | Navega no histórico de comandos |
| `/` | Abre dropdown de comandos |
| `Escape` | Fecha dropdown |

---

## Estrutura do projeto

```
crivonansky/
├── core/                  # Núcleo do framework
│   ├── command.py         # Classe base abstrata
│   ├── registry.py        # Registro de comandos
│   ├── context.py         # Injeção de dependências
│   ├── parser.py          # Parsing de entrada (shlex)
│   ├── executor.py        # Orquestração (captura stdout)
│   ├── loader.py          # Carga dinâmica de plugins
│   ├── bootstrap.py       # build_executor() — wiring comum (TUI/API)
│   └── run/               # Task runner (gulp.js-style)
│       ├── __init__.py    # Re-exports públicos
│       ├── vinyl.py       # Arquivo virtual (VinylFile)
│       ├── task.py        # Definição de task
│       ├── task_registry.py # Registro de tasks
│       ├── series_parallel.py # series() / parallel()
│       ├── pipeline.py    # PipeStream (.pipe/.dest)
│       ├── src.py         # src() — leitura via glob
│       ├── dest.py        # dest() — escrita em disco
│       ├── transforms.py  # Transformações built-in
│       ├── watcher.py     # Watch mode (watchdog)
│       ├── loader.py      # load_runfile() dinâmico
│       └── api.py         # API pública (task, src, dest, cmd)
├── commands/              # Plugins (descoberta automática)
│   ├── help.py
│   ├── environment.py
│   ├── task.py
│   ├── metrics_report.py
│   ├── load_app.py
│   ├── db_tools.py
│   ├── container_terminal.py
│   ├── convert_site.py
│   ├── site_capture.py
│   ├── generate_plugin.py
│   ├── send_capoeira_host.py
│   ├── run_git_cmd.py
│   ├── docker_container_run.py
│   ├── run_command.py     # Comando /run
│   └── harness.py         # Comando /harness
├── commands/complements/  # Dependências internas (não auto-descobertas)
│   ├── task_plugin/
│   ├── db_tools_plugin/
│   ├── load_app_plugin/
│   ├── work_analysis.py
│   └── harness/           # Plugin autocontido (install, vendor, fixture, workspace)
├── tui_app.py             # Interface TUI (Textual)
├── api_server.py          # API REST (FastAPI)
├── api.ps1                # Launcher da API (ativa o .venv)
├── crivonansky.py         # Entry point
├── runfile.py             # Tasks do usuário (opcional)
└── requirements.txt       # Dependências
```

---

## Task Runner (`/run`)

O Crivonansky possui um task runner inspirado no gulp.js. Defina tasks em um arquivo `runfile.py` na raiz do projeto:

```python
from core.run import task, src, dest, series, parallel, watch, cmd

@task
def build():
    """Compila arquivos para dist"""
    return src("src/**/*").pipe(dest("dist"))

@task(deps=["clean"])
def rebuild():
    """Clean + build em sequência"""
    return series(clean, build)

@task
def dev():
    """Watch mode"""
    watch("src/**/*", build)

@task
def up():
    """Sobe ambiente usando comando existente"""
    cmd("/environment start dev")
```

### Comandos do task runner

| Comando | Descrição |
|---|---|
| `/run init` | Cria um `runfile.py` de exemplo |
| `/run --tasks` ou `list` | Lista todas as tasks registradas |
| `/run run <taskname>` | Executa uma task (`default` se omitido) |
| `/run watch <taskname>` | Executa a task e monitora arquivos |

### API disponível no runfile.py

| Função | Descrição |
|---|---|
| `task(name?, deps?)` | Decorator — registra uma função como task |
| `src(patterns, base?)` | Lê arquivos via glob, retorna PipeStream |
| `dest(directory)` | Cria um transform que escreve arquivos no disco |
| `series(...tasks)` | Compõe tasks em execução sequencial |
| `parallel(...tasks)` | Compõe tasks em execução paralela (threads) |
| `watch(patterns, ...tasks, debounce=200)` | Monitora arquivos e executa tasks |
| `cmd(command_line)` | Executa um comando da CLI como parte da task e devolve seus dados de retorno (`{"success": bool, **dados}`, incluindo `output`) |

---

## API REST

O Crivonansky expõe uma API REST (FastAPI) que executa os mesmos comandos da TUI via HTTP, usando o mesmo parser (`shlex`) e executor.

### Endpoints

| Endpoint | Descrição |
|---|---|
| `GET /health` | Health check — `{"status": "ok"}` |
| `GET /commands` | Lista todos os comandos registrados (`name`, `description`) |
| `GET /commands/{name}` | Detalhe + uso/ajuda do comando (aceita com ou sem `/` inicial) |
| `POST /execute` | Executa uma linha de comando |

### Executando comandos

`POST /execute` recebe `{"command": "/environment start dev"}` e retorna `{success, output, data, error}`:

```bash
curl -X POST http://127.0.0.1:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "/help"}'
```

```json
{
  "success": true,
  "output": "Comandos disponíveis:\n\n/help - Lista comandos disponíveis\n...",
  "data": {"count": 11},
  "error": null
}
```

- **`success`** — indica sucesso/falha da execução (negócio).
- **`output`** — texto capturado do `print()` do comando (com markup Rich).
- **`data`** — dicionário opcional retornado pelo comando; **`error`** — mensagem de falha quando houver.
- Para comandos bloqueantes (`/run watch`, `/site-capture`), envie `timeout` em segundos: `{"command": "/run watch default", "timeout": 30}`.

### Códigos de status

| Status | Significado |
|---|---|
| `200` | Executou (com `success: true/false` conforme o resultado) |
| `400` | Comando vazio |
| `404` | Comando inexistente |
| `408` | Timeout excedido |

Note que cada requisição cria um executor **novo** (via `core/bootstrap.py:build_executor()`), garantindo isolamento de estado entre requisições concorrentes.

---

## Como criar um plugin

### Via comando interno

```bash
/generate-plugin --name meu-comando
```

Isso cria `commands/meu_comando.py` com a estrutura básica. Reinicie a CLI para usar o novo comando.

### Manualmente

Crie um arquivo em `commands/` seguindo o modelo:

```python
from core.command import Command


class MeuComandoCommand(Command):
    name = "meu-comando"
    description = "Descreva o que este comando faz"

    def execute(self, args):
        print("Executando meu-comando")
```

### Como funciona

- O framework descobre automaticamente classes que herdam de `Command` dentro de `commands/`
- O nome do comando é prefixado com `/` automaticamente
- O argumento `args` contém a lista de palavras após o nome do comando
- `self.context.registry` dá acesso ao registro de comandos

---

## Tecnologias

- [Textual](https://textual.textualize.io/) — Framework TUI
- [Rich](https://rich.readthedocs.io/) — Output estilizado
- [FastAPI](https://fastapi.tiangolo.com/) — API REST
- [uvicorn](https://www.uvicorn.org/) — Servidor ASGI
- [watchdog](https://github.com/gorakhargosh/watchdog) — Watch mode
- `importlib` — Carga dinâmica de plugins

---

## Licença

MIT
