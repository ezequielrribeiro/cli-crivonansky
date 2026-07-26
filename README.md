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

---

## Comandos disponíveis

| Comando | Descrição |
|---|---|
| `/help` | Lista todos os comandos disponíveis |
| `/clear` | Limpa a tela |
| `/quit` | Sai da aplicação |
| `/task` | Controle de tarefas (start/resume/report) |
| `/environment` | Gerencia ambientes Docker via docker-compose |
| `/metrics-report` | Relatório trimestral de métricas |
| `/load-app` | Lança apps e move para desktops virtuais |
| `/db-tools` | Otimizador/instalador de dumps MySQL |
| `/container-terminal` | Terminal PowerShell em container Docker |
| `/convert-site` | Converte URL para Markdown |
| `/site-capture` | Captura página via Selenium como Markdown |
| `/generate-plugin --name <nome>` | Gera um novo plugin de comando |
| `/run` | Task runner (gulp.js-style). Subcomandos: `run <task>`, `--tasks`, `watch <task>`, `init` |

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
│   └── run_command.py    # Comando /run
├── commands/complements/  # Dependências internas (não auto-descobertas)
│   ├── task_plugin/
│   ├── db_tools_plugin/
│   ├── load_app_plugin/
│   └── work_analysis.py
├── tui_app.py             # Interface TUI (Textual)
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
| `cmd(command_line)` | Executa um comando da CLI como parte da task |

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
- [watchdog](https://github.com/gorakhargosh/watchdog) — Watch mode
- `importlib` — Carga dinâmica de plugins

---

## Licença

MIT
