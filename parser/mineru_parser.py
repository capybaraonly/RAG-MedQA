
#

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class MinerUPdfParser:
    """Parse PDF files using MinerU and return RAG-MedQA (sections, tables) format.

    Two operation modes:
    - **CLI mode** (default, ``backend="pipeline"``): calls the ``mineru`` /
      ``magic-pdf`` command-line tool.  Requires MinerU to be installed in the
      Python environment.
    - **API mode** (when ``api_url`` or ``server_url`` is set): forwards the PDF
      to a running MinerU API server via HTTP POST.

    The parser converts MinerU's markdown output into:
    - ``sections`` – list of ``(text, "")`` tuples, one per paragraph / heading.
    - ``tables``   – list of ``((None, html_table), "")`` tuples for each markdown
      table found in the output.
    """

    def __init__(self, api_url="", server_url="", output_dir="",
                 backend="pipeline", delete_output=True):
        self.api_url = (api_url or "").rstrip("/")
        self.server_url = (server_url or "").rstrip("/")
        self.output_dir = output_dir or ""
        self.backend = backend or "pipeline"
        self.delete_output = bool(int(delete_output if delete_output is not None else 1))

    # ------------------------------------------------------------------
    # Installation check
    # ------------------------------------------------------------------

    def check_installation(self):
        if self.api_url or self.server_url:
            return True
        return bool(self._find_cli())

    def _find_cli(self) -> str | None:
        for cmd in ("mineru", "magic-pdf"):
            try:
                r = subprocess.run([cmd, "--version"], capture_output=True, timeout=10)
                if r.returncode == 0:
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    # ------------------------------------------------------------------
    # CLI mode
    # ------------------------------------------------------------------

    def _parse_via_cli(self, pdf_path: str, out_dir: str,
                       parse_method: str, callback) -> str:
        cmd = self._find_cli()
        if not cmd:
            raise RuntimeError(
                "MinerU CLI not found. Install with: pip install mineru  "
                "or set MINERU_APISERVER / MINERU_SERVER_URL to use API mode."
            )

        args = [cmd, "-p", pdf_path, "-o", out_dir, "-m", parse_method or "auto"]
        logging.info("MinerU CLI: %s", " ".join(args))

        if callback:
            callback(0.2, "MinerU: parsing PDF …")

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            raise RuntimeError("MinerU CLI timed out (>10 min)")

        if result.returncode != 0:
            raise RuntimeError(
                f"MinerU CLI exited with code {result.returncode}:\n{result.stderr}"
            )

        if callback:
            callback(0.6, "MinerU: reading output …")

        # Locate the generated markdown file.
        # MinerU writes to: <out_dir>/<pdf_stem>/auto/<pdf_stem>.md
        pdf_stem = Path(pdf_path).stem
        candidates = [
            Path(out_dir) / pdf_stem / "auto" / f"{pdf_stem}.md",
            Path(out_dir) / pdf_stem / f"{pdf_stem}.md",
            Path(out_dir) / f"{pdf_stem}.md",
        ]
        for p in candidates:
            if p.exists():
                return p.read_text(encoding="utf-8")

        # Fallback: find any .md in the output tree
        md_files = sorted(Path(out_dir).rglob("*.md"))
        if md_files:
            return md_files[0].read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"MinerU output markdown not found under {out_dir!r}"
        )

    # ------------------------------------------------------------------
    # API mode
    # ------------------------------------------------------------------

    def _parse_via_api(self, binary: bytes, parse_method: str, callback) -> str:
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests package is required for MinerU API mode")

        base = self.api_url or self.server_url
        if callback:
            callback(0.2, "MinerU: sending PDF to API server …")

        errors = []
        for endpoint in ("/file_parse", "/predict", "/parse", "/api/v1/parse"):
            url = f"{base}{endpoint}"
            try:
                resp = requests.post(
                    url,
                    files={"file": ("document.pdf", binary, "application/pdf")},
                    data={"parse_method": parse_method or "auto"},
                    timeout=600,
                )
                if resp.status_code != 200:
                    errors.append(f"{url}: HTTP {resp.status_code}")
                    continue

                data = resp.json()
                if callback:
                    callback(0.6, "MinerU: API response received …")

                for field in ("md_content", "markdown", "content", "result", "data"):
                    if field in data:
                        val = data[field]
                        return val if isinstance(val, str) else str(val)

                # Last resort: stringify the whole response
                return str(data)

            except Exception as exc:
                errors.append(f"{url}: {exc}")
                continue

        raise RuntimeError(
            f"All MinerU API endpoints failed for {base!r}. Errors:\n"
            + "\n".join(errors)
        )

    # ------------------------------------------------------------------
    # Markdown → RAG-MedQA format conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _md_to_sections_and_tables(md_text: str):
        """Convert MinerU markdown to ``(sections, tables)`` for RAG-MedQA."""
        sections = []
        tables = []

        if not md_text or not md_text.strip():
            return sections, tables

        lines = md_text.splitlines()
        current_para: list[str] = []
        table_lines: list[str] = []
        in_table = False

        def _is_table_row(line: str) -> bool:
            s = line.strip()
            return s.startswith("|") and s.count("|") >= 2

        def flush_para():
            text = "\n".join(current_para).strip()
            if text:
                sections.append((text, ""))
            current_para.clear()

        def flush_table():
            if not table_lines:
                return
            try:
                from markdown import markdown
                html = markdown(
                    "\n".join(table_lines),
                    extensions=["markdown.extensions.tables"],
                )
                tables.append(((None, html), ""))
            except Exception:
                sections.append(("\n".join(table_lines), ""))
            table_lines.clear()

        for line in lines:
            stripped = line.strip()

            # Skip bare image references that MinerU injects
            if re.match(r"^!\[.*?\]\(.*?\)\s*$", stripped):
                continue

            is_table = _is_table_row(line)

            if is_table:
                if not in_table:
                    flush_para()
                    in_table = True
                table_lines.append(line)
                continue

            if in_table:
                flush_table()
                in_table = False

            if not stripped:
                flush_para()
                continue

            current_para.append(line)

        # Flush remainder
        if in_table:
            flush_table()
        flush_para()

        return sections, tables

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def parse_pdf(self, filepath=None, binary=None, callback=None,
                  parse_method="auto", lang="Chinese", **kwargs):
        """Parse a PDF and return ``(sections, tables)``.

        Args:
            filepath: Path to the PDF file on disk (str or Path).  Used in CLI
                      mode; if *binary* is provided and the file does not exist,
                      a temporary file is created automatically.
            binary:   Raw PDF bytes.  Used directly in API mode; in CLI mode a
                      temp file is written when *filepath* is unavailable.
            callback: Progress callback ``(progress: float, message: str)``.
            parse_method: MinerU parse method (``"auto"``, ``"ocr"``, ``"txt"``).
            lang:     Language hint (currently informational).

        Returns:
            Tuple ``(sections, tables)`` in RAG-MedQA format.
        """
        use_api = bool(self.api_url or self.server_url)
        tmp_file_path: str | None = None
        tmp_out_dir: str | None = None

        try:
            if use_api:
                if binary is None:
                    if not filepath:
                        raise ValueError("Either filepath or binary must be provided")
                    with open(str(filepath), "rb") as fh:
                        binary = fh.read()
                elif not isinstance(binary, bytes):
                    binary = binary.read()
                md_text = self._parse_via_api(binary, parse_method, callback)

            else:  # CLI mode
                # Resolve or create a PDF file on disk
                if filepath and os.path.exists(str(filepath)):
                    pdf_path = str(filepath)
                else:
                    if binary is None:
                        raise ValueError("Either filepath or binary must be provided")
                    if not isinstance(binary, bytes):
                        binary = binary.read()
                    tmp_fd, tmp_file_path = tempfile.mkstemp(suffix=".pdf")
                    os.close(tmp_fd)
                    with open(tmp_file_path, "wb") as fh:
                        fh.write(binary)
                    pdf_path = tmp_file_path

                # Resolve output directory
                if self.output_dir:
                    out_dir = self.output_dir
                    tmp_out_dir = None
                else:
                    tmp_out_dir = tempfile.mkdtemp()
                    out_dir = tmp_out_dir

                md_text = self._parse_via_cli(pdf_path, out_dir, parse_method, callback)

            sections, tables = self._md_to_sections_and_tables(md_text)

            if callback:
                callback(0.8, f"MinerU: {len(sections)} sections, {len(tables)} tables")

            return sections, tables

        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception:
                    pass
            if self.delete_output and tmp_out_dir and os.path.exists(tmp_out_dir):
                try:
                    shutil.rmtree(tmp_out_dir, ignore_errors=True)
                except Exception:
                    pass
