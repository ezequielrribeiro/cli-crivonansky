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
| `/generate-plugin --name <nome>` | Gera um novo plugin de comando |

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
├── core/              # Núcleo do framework
│   ├── command.py     # Classe base abstrata
│   ├── registry.py    # Registro de comandos
│   ├── context.py     # Injeção de dependências
│   ├── parser.py      # Parsing de entrada
│   ├── executor.py    # Orquestração
│   └── loader.py      # Carga dinâmica de plugins
├── commands/          # Plugins (descoberta automática)
│   ├── help.py        # Comando /help
│   └── generate_plugin.py  # Gerador de novos plugins
├── tui_app.py         # Interface TUI
├── crivonansky.py     # Entry point
└── requirements.txt   # Dependências
```

---

## Como criar um plugin

### Via comando interno

```bash
generate-plugin --name meu-comando
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
- `importlib` — Carga dinâmica de plugins

---

## Licença

MIT
