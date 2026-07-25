# 🧾 Spec — Framework de CLI Extensível com TUI

## 📌 Identificação

**Título:** [CLI] — Framework extensível com suporte a plugins dinâmicos e interface TUI

**Tipo:**
- ( ) Bug
- ( ) Melhoria
- (x) Nova funcionalidade
- ( ) Técnico / Débito técnico

**Prioridade:**
- ( ) Baixa
- ( ) Média
- (x) Alta
- ( ) Crítica

---

## 🧭 Visão Geral

### Objetivo
Criar um framework de CLI em Python com as seguintes capacidades:

- Execução interativa via prompt
- Suporte a comandos modulares
- Carregamento dinâmico de plugins
- Injeção de dependências via contexto
- Interface semi-gráfica (TUI) baseada em Textual

### Motivação

- Facilitar criação de ferramentas CLI reutilizáveis
- Reduzir acoplamento entre comandos
- Permitir crescimento incremental do sistema
- Melhorar experiência de uso com interface rica

### Impacto

- Desenvolvedores que criarão novos comandos
- Usuários finais que utilizarão a CLI

---

## 🎯 Resultado Esperado

O sistema deve:

- Permitir execução de comandos via interface TUI
- Carregar automaticamente novos comandos (plugins)
- Exibir saída estruturada e com scroll (RichLog)
- Suportar passagem de argumentos aos comandos
- Permitir fácil extensão sem alterar o core

---

## 🏗️ Escopo

### ✅ Dentro do escopo

- Estrutura modular do CLI
- Parser de comandos e argumentos
- Registry de comandos
- Loader dinâmico (plugins)
- Contexto de execução (injeção de dependência)
- Executor de comandos
- Interface TUI com Textual
- Comandos base (/help, task hello)

### ❌ Fora do escopo

- Persistência em banco de dados
- Autenticação/autorização
- Distribuição via pip (fase futura)
- Execução remota/API

### 📁 Estrutura de Diretórios

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
│   ├── *.py           # Comandos individuais
│   └── complements/   # Dependências internas dos plugins
├── *.json             # Arquivos de configuração
└── crivonansky.py     # Entry point
```

---

## 🧠 Premissas Técnicas

- Linguagem: Python 3.10+
- Framework TUI: textual
- Output estilizado: rich
- Estrutura baseada em pacotes Python

---

## 🗄️ Dados e Persistência

### Estruturas envolvidas

- Não há persistência obrigatória nesta fase

---

## 🖥️ Front-end / UX

### Interface

- Input de comandos no rodapé
- Área de saída com scroll (RichLog)
- Exibição de comandos executados
- Feedback visual com cores

### Comportamento

- Cada comando executado deve aparecer no log
- Resposta deve ser exibida abaixo do comando

### Atalhos de Teclado

| Tecla | Ação |
|---|---|
| `Enter` | Executa comando ou seleciona item do dropdown |
| `↑` / `↓` | Navega dropdown / histórico de comandos |
| `Escape` | Fecha dropdown |
| `/` | Abre dropdown de comandos disponíveis |

### Esquema de Cores

| Contexto | Cor |
|---|---|
| Comando digitado | `cyan` |
| Erro | `red` |
| Sucesso | `green` |
| Informação | `yellow` |

---

## 💾 Back-end

### Fluxo

1. Usuário digita comando
2. Parser divide comando e argumentos
3. Executor resolve comando via registry
4. Command.execute(args) é chamado
5. Output é capturado e exibido na TUI

---

## ⚙️ Regras de Negócio

- Se comando não existir → exibir erro
- Se comando válido → executar e exibir resultado
- Se entrada vazia → ignorar
- Plugins devem herdar de Command
- Comandos devem ser carregados automaticamente

---

## 📐 Contratos e Interfaces

### Command (Classe Base)

| Método / Atributo | Assinatura | Obrigatório | Descrição |
|---|---|---|---|
| `execute` | `execute(self, args: list[str]) -> None` | Sim | Executa o comando. Output via `print()` |
| `parse_args` | `parse_args(self, args: list[str]) -> dict` | Não | Utilitário nativo para parsing de `--flag valor` |
| `get_usage` | `get_usage(self) -> str` | Não | Retorna texto de ajuda do comando |
| `help_text` | `help_text: str` | Não | Atributo de classe com sintaxe de uso. Usado por `get_usage()` |

**Comportamento padrão de `--help`:** O executor intercepta `--help` ou `-h` nos argumentos antes de chamar `execute()` e exibe o texto retornado por `get_usage()`. Plugins podem sobrescrever `help_text` para personalizar a ajuda.

### CLIContext

| Propriedade | Tipo | Descrição |
|---|---|---|
| `registry` | `CommandRegistry` | Acesso ao registro de comandos |

### CommandRegistry

| Método | Assinatura | Descrição |
|---|---|---|
| `register` | `register(name: str, command: Command)` | Registra um comando |
| `get` | `get(name: str) -> Command \| None` | Busca por nome |
| `all` | `all() -> dict[str, Command]` | Retorna todos os comandos |

---

## 🧪 Critérios de Aceite

### Funcionalidades base

- Dado que o CLI inicia, quando digitar `/help`, então deve listar todos os comandos registrados com nome e descrição
- Dado que digitar `task hello`, então deve retornar "hello world"
- Dado que comando inválido, então deve exibir mensagem de erro no formato `[red]Comando não encontrado[/red]`
- Dado novo plugin criado em `commands/`, quando reiniciar o CLI, então o comando deve estar disponível

### Tratamento de erros

- Dado que um plugin lança uma exceção em `execute()`, então a TUI deve exibir o erro sem travar
- Dado que dois plugins registram o mesmo nome, então o último sobrescreve o anterior (sem erro)
- Dado entrada vazia, então o CLI deve ignorar silenciosamente

### Parser

- Dado argumentos com aspas (`--name "João Silva"`), então o parser deve preservar o valor completo
- Dado flag booleana (`--verbose` sem valor), então o parser deve retornar `True`

### TUI

- Dado que o usuário digita `/`, então deve aparecer um dropdown com comandos disponíveis
- Dado que o usuário pressiona `↑/↓`, então deve navegar pelo histórico de comandos
- Dado que o usuário pressiona `Escape`, então deve fechar o dropdown
- Dado que o usuário pressiona `Enter` com dropdown visível, então deve popular o input sem executar

---

## 📎 Observações Técnicas

- Utilizar importlib para carga dinâmica
- Usar io.StringIO para capturar stdout
- Isolar UI da lógica de execução

---

## ⚙️ Arquivos de Configuração

O framework suporta arquivos JSON na raiz do projeto para configurar comandos específicos:

| Arquivo | Comando | Propósito |
|---|---|---|
| `metrics_report_conf.json` | `metrics-report` | Define o caminho padrão do arquivo de métricas |
| `environment_conf.json` | `environment` | Define os ambientes Docker disponíveis |

### Formato dos arquivos

```json
{
  "metrics_file": "caminho/para/metrics.json"
}
```

```json
{
  "environments": {
    "nome": "caminho/para/docker-compose.yml"
  }
}
```

---

## 🔌 Exemplo de Plugin (Pseudo-código Python)

Abaixo um exemplo de como criar um novo plugin de comando para o framework:

```python
# commands/user_create.py

from core.command import Command


class UserCreateCommand(Command):
    name = "user-create"
    description = "Cria um novo usuário"
    help_text = "Uso: /user-create --name <nome>"

    def execute(self, args):
        # args é uma lista de strings vindas do CLI
        # Exemplo: user-create --name Ezequiel

        parsed_args = self.parse_args(args)

        name = parsed_args.get("name", "default")

        print(f"Usuário criado: {name}")
```

### 📌 Como funciona

- O plugin é apenas uma classe que herda de `Command`
- O framework descobre automaticamente via loader
- `execute(args)` recebe parâmetros do CLI
- `self.context` pode ser usado para acessar registry, config, etc.

### ▶️ Uso

```bash
user-create --name ezequiel
```

Saída:

```
Usuário criado: ezequiel
```

---

## ✅ Checklist

- [x] Estrutura modular definida
- [x] Plugins funcionais
- [x] TUI integrada
- [x] Injeção via contexto
- [x] Parser funcional

---

## 🧩 Tarefas de Desenvolvimento

### ✅ Concluídas

- Definição da arquitetura modular do CLI
- Implementação do Command Pattern
- Criação do CommandRegistry
- Implementação do parser de comandos básico
- Implementação do loader dinâmico (plugins)
- Criação do CLIContext para injeção de dependências
- Implementação do executor desacoplado
- Implementação da TUI com Textual
- Integração com RichLog para output com scroll
- Implementação de comandos base (`/help`, `task hello`)
- Implementação do comando `generate plugin`
- Sistema básico de parsing de argumentos (`--flag`)

### 🟡 Pendentes / Próximos passos

- Melhorar parser (suporte a aspas via shlex)
- Implementar validação de argumentos
- Adicionar autocomplete de comandos
- Implementar histórico persistente
- Estruturar plugins externos (pip install)
- Criar sistema de templates (ex: Jinja2)
- Adicionar logs estruturados
- Suporte a execução assíncrona de comandos
- Melhorar UI (painéis, sidebar, status)

### 🔵 Melhorias futuras (nível produto)

- Distribuição como pacote instalável (pyproject.toml)
- Integração com APIs externas
- CLI conversacional (modo chatbot)
- Sistema de permissões para comandos
- Sistema de versionamento de plugins

---

## 🧠 Nota

O projeto deve permitir evolução para:

- CLI conversacional
- Integração com APIs
- Sistema de plugins externos
- Distribuição via pip
