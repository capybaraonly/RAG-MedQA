
#

import json
import logging
import os


class Base:
    """Base class for OCR / document-parsing models."""

    def __init__(self, key="", model_name="", lang="Chinese", base_url="", **kwargs):
        self.model_name = model_name
        self.lang = lang
        self.base_url = base_url

    def parse_pdf(self, filepath=None, binary=None, callback=None, **kwargs):
        raise NotImplementedError


class MinerU(Base):
    """MinerU-based PDF parser, registered as an OCR model factory.

    The MinerU config is stored as a JSON string in the ``key`` field:
    {
      "MINERU_APISERVER": "",
      "MINERU_SERVER_URL": "",
      "MINERU_OUTPUT_DIR": "",
      "MINERU_BACKEND": "pipeline",
      "MINERU_DELETE_OUTPUT": 1
    }
    Values fall back to the corresponding environment variables when empty.
    """

    _FACTORY_NAME = "MinerU"

    def __init__(self, key="", model_name="", lang="Chinese", base_url="", **kwargs):
        super().__init__(key=key, model_name=model_name, lang=lang, base_url=base_url, **kwargs)

        cfg: dict = {}
        if key:
            try:
                cfg = json.loads(key)
            except Exception:
                logging.warning("MinerU: failed to parse config JSON from key field: %r", key)

        from common.constants import MINERU_DEFAULT_CONFIG

        def _get(k: str):
            return cfg.get(k) or os.environ.get(k, MINERU_DEFAULT_CONFIG[k])

        self.api_url = _get("MINERU_APISERVER")
        self.server_url = _get("MINERU_SERVER_URL")
        self.output_dir = _get("MINERU_OUTPUT_DIR")
        self.backend = _get("MINERU_BACKEND")
        self.delete_output = bool(int(_get("MINERU_DELETE_OUTPUT") or 1))

    def parse_pdf(self, filepath=None, binary=None, callback=None,
                  parse_method="auto", lang=None, **kwargs):
        from parser.mineru_parser import MinerUPdfParser

        parser = MinerUPdfParser(
            api_url=self.api_url,
            server_url=self.server_url,
            output_dir=self.output_dir,
            backend=self.backend,
            delete_output=self.delete_output,
        )
        return parser.parse_pdf(
            filepath=filepath,
            binary=binary,
            callback=callback,
            parse_method=parse_method,
            lang=lang or self.lang,
            **kwargs,
        )
