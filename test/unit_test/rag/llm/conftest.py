
#

"""
Prevent rag.llm.__init__ from running its heavy auto-discovery loop.

The __init__.py dynamically imports ALL model modules (chat_model,
cv_model, ocr_model, etc.), which pull in deepdoc, xgboost, torch,
and other heavy native deps. We pre-install a lightweight stub for
the rag.llm package so that `from rag.llm.embedding_model import X`
works without triggering the full init.
"""

import os
import sys
import types

# Resolve the real path to rag/llm/ so sub-module imports can find files
_RAG-MedQA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_RAG_LLM_DIR = os.path.join(_RAG-MedQA_ROOT, "rag", "llm")


def _install_rag_llm_stub():
    """Replace rag.llm with a minimal package stub if not yet loaded.

    The stub has __path__ pointing to the real rag/llm/ directory so that
    `from rag.llm.embedding_model import X` resolves to the actual file,
    but the __init__.py auto-discovery loop is skipped.
    """
    if "rag.llm" in sys.modules:
        return

    # Create a stub rag.llm package that does NOT run the real __init__
    llm_pkg = types.ModuleType("rag.llm")
    llm_pkg.__path__ = [_RAG_LLM_DIR]
    llm_pkg.__package__ = "rag.llm"
    # Provide empty dicts for the mappings the real __init__ would build
    llm_pkg.EmbeddingModel = {}
    llm_pkg.ChatModel = {}
    llm_pkg.CvModel = {}
    llm_pkg.RerankModel = {}
    llm_pkg.Seq2txtModel = {}
    llm_pkg.TTSModel = {}
    llm_pkg.OcrModel = {}
    sys.modules["rag.llm"] = llm_pkg


_install_rag_llm_stub()
