from core.command import Command

import requests
from rich.markup import escape


class SendCapoeiraHostCommand(Command):
    name = "send-capoeira-host"
    description = "Envia um prompt em texto plano para um LLM via API do CapoeiraHost"
    help_text = (
        "Uso: /send-capoeira-host --prompt \"<prompt>\" [--host <host>] [--port <port>]\n"
        "                         [--model <model>] [--system <system>]\n"
        "                         [--new-chat <true|false>] [--timeout <segundos>]\n"
        "Exemplo: /send-capoeira-host --host 127.0.0.1 --port 8080 --prompt \"um texto \\\"qualquer\\\"\""
    )

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = "8765"
    DEFAULT_MODEL = "gemini-pro"
    DEFAULT_TIMEOUT = 180

    def execute(self, args):
        parsed = self.parse_args(args)

        prompt = parsed.get("prompt")

        if not prompt:
            print("[erro] Informe o prompt (--prompt \"<texto>\")")
            return False, {"error": "informe o prompt"}

        host = parsed.get("host", self.DEFAULT_HOST)
        port = str(parsed.get("port", self.DEFAULT_PORT))
        model = parsed.get("model", self.DEFAULT_MODEL)
        system = parsed.get("system")
        new_chat = parsed.get("new-chat")
        timeout = self._parse_timeout(parsed.get("timeout"))

        url = f"http://{host}:{port}/api/generate"

        data = {"model": model, "prompt": prompt}
        if system:
            data["system"] = system
        if new_chat is not None:
            data["new_chat"] = "false" if str(new_chat).lower() in ("false", "0", "no") else "true"

        print(f"[cyan]Enviando prompt para {url}[/cyan]")

        try:
            response = requests.post(url, data=data, timeout=timeout)
        except requests.exceptions.Timeout:
            print(f"[erro] Timeout de {timeout}s ao acessar {url}")
            return False, {"error": f"timeout ao acessar {url}", "host": host, "port": port}
        except requests.exceptions.ConnectionError:
            print(f"[erro] Nao foi possivel conectar em {url}")
            print("Verifique se o CapoeiraHost esta em execucao e se a extensao esta conectada.")
            return False, {"error": f"nao foi possivel conectar em {url}", "host": host, "port": port}
        except requests.exceptions.RequestException as e:
            print(f"[erro] Erro ao acessar {url}: {e}")
            return False, {"error": str(e), "host": host, "port": port}

        body = response.text
        success = response.status_code == 200

        print()
        if body:
            print(escape(body))
        else:
            print("[yellow](resposta vazia)[/yellow]")

        result = {
            "host": host,
            "port": port,
            "model": model,
            "prompt": prompt,
            "status_code": response.status_code,
            "output": body,
        }

        if not success:
            print()
            print(f"[red]CapoeiraHost retornou status {response.status_code}[/red]")
            result["error"] = f"status {response.status_code}"
            return False, result

        return True, result

    def _parse_timeout(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return self.DEFAULT_TIMEOUT
