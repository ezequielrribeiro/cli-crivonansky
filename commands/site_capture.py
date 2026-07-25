from core.command import Command
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from datetime import datetime
import re

_driver = None


class SiteCaptureCommand(Command):
    name = "site-capture"
    description = "Abre sessao Chrome controlada e captura paginas como Markdown"
    help_text = "Uso: /site-capture start\n     /site-capture capture [--format md]\n     /site-capture stop"

    def execute(self, args):
        global _driver

        subcommand = args[0] if args and not args[0].startswith("--") else "capture"

        if subcommand == "start":
            self._start()
        elif subcommand == "stop":
            self._stop()
        elif subcommand == "capture":
            self._capture(args)
        else:
            print(f"[erro] Subcomando desconhecido: {subcommand}")
            print("Uso: site-capture [start|capture|stop] [--format md]")

    def _start(self):
        global _driver
        if _driver is not None:
            print("[erro] Chrome ja esta em execucao")
            return
        try:
            opts = Options()
            opts.add_argument("--start-maximized")
            _driver = webdriver.Chrome(options=opts)
            print(
                "Chrome iniciado. Navegue ate a pagina desejada "
                "e execute o comando novamente para capturar."
            )
        except Exception as e:
            print(f"[erro] Falha ao iniciar Chrome: {e}")

    def _stop(self):
        global _driver
        if _driver is None:
            print("[erro] Chrome nao esta em execucao")
            return
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
        print("Chrome encerrado")

    def _capture(self, args):
        global _driver
        if _driver is None:
            print(
                "[erro] Chrome nao esta em execucao. "
                "Execute 'site-capture' primeiro para iniciar."
            )
            return

        parsed = self.parse_args(args)
        fmt = parsed.get("format", "md")

        if fmt != "md":
            print(f"[erro] Formato '{fmt}' nao suportado. Use 'md'.")
            return

        try:
            url = _driver.current_url
            html = _driver.page_source
        except Exception as e:
            print(f"[erro] Falha ao capturar pagina: {e}")
            return

        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else url

        for tag in soup.find_all(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()

        body = soup.body

        if not body:
            print("[erro] Pagina nao possui conteudo no body")
            return

        markdown_content = md(str(body), heading_style="ATX")

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{self._sanitize_filename(title)}-{timestamp}.{fmt}"
        filepath = f"{filename}"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{markdown_content}")

        print(f"Pagina capturada: {filepath}")

    def _sanitize_filename(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\u00c0-\u024f\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        text = text.strip("-") or "pagina"
        return text[:80]
