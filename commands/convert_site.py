from core.command import Command
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from datetime import datetime
import re


class ConvertSiteCommand(Command):
    name = "convert-site"
    description = "Faz scraping de um site e converte o conteudo para Markdown"
    help_text = "Uso: /convert-site --site <url> [--format md]"

    def execute(self, args):
        parsed = self.parse_args(args)

        url = parsed.get("site")
        fmt = parsed.get("format", "md")

        if not url:
            print("[erro] Informe a URL do site (--site <url>)")
            return

        if fmt != "md":
            print(f"[erro] Formato '{fmt}' nao suportado. Use 'md'.")
            return

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
        except requests.exceptions.Timeout:
            print(f"[erro] Timeout ao acessar {url}")
            return
        except requests.exceptions.ConnectionError:
            print(f"[erro] Nao foi possivel conectar em {url}")
            return
        except requests.exceptions.HTTPError as e:
            print(f"[erro] Servidor retornou status {e.response.status_code}")
            return
        except requests.exceptions.RequestException as e:
            print(f"[erro] Erro ao acessar {url}: {e}")
            return

        soup = BeautifulSoup(response.text, "html.parser")

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

        print(f"Pagina convertida: {filepath}")

    def _sanitize_filename(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\u00c0-\u024f\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        text = text.strip("-") or "pagina"
        return text[:80]
