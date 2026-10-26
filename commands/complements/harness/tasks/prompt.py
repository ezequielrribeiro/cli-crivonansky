"""Tarefa prompt: copia o prompt de instrução do LLM."""

from ..catalog import register
from ..types import TaskResult, TaskSpec

PROMPT = """Você está conectado a um harness local de desenvolvimento de um sistema legado (PHP, MySQL, JS).
Você NÃO tem acesso direto a arquivos, terminal ou banco de dados.

Para pedir uma ação, responda com UM ou mais blocos de código no formato:

```crivonansky
harness: 1
task: <tarefa do catálogo>
params: { ... }
```

Regras:
1. Use apenas tarefas do catálogo: env:check, context:pack, file:read, code:query, code:impact,
   db:schema, db:query (somente SELECT), db:links, rag:search, git:run, shell:run, py:run,
   docker:exec, logs:tail, patch:apply, test:run, verify, lint.
2. Prefira tarefas de leitura para investigar antes de propor mudanças.
3. Para alterar código, use patch:apply com diff unificado e verify: true.
4. Após emitir blocos, PARE e aguarde o bloco ```crivonansky-result.
5. Nunca invente resultados; baseie-se apenas nos blocos de resultado recebidos.
6. Se o status for failure/error/denied/timeout, analise o summary/details antes de tentar de novo."""


def handle(ctx, params):
    copied = False
    try:
        import pyperclip

        pyperclip.copy(PROMPT)
        copied = True
    except Exception:  # noqa: BLE001
        copied = False

    summary = "prompt copiado para o clipboard" if copied else "prompt gerado (clipboard indisponível)"
    return TaskResult(True, summary, details=PROMPT)


register(
    TaskSpec(
        name="prompt",
        intent="read",
        description="Copia o prompt de instrução do LLM para o clipboard",
        required=[],
        optional=[],
        handler=handle,
    )
)
