
#

from io import BytesIO

from pypdf import PdfReader as pdf2_read

from rag.nlp import find_codec


def get_text(fnm: str, binary=None) -> str:
    txt = ""
    if binary is not None:
        encoding = find_codec(binary)
        txt = binary.decode(encoding, errors="ignore")
    else:
        with open(fnm, "r") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                txt += line
    return txt


def total_page_number(fnm, binary=None):
    """Return total page count of a PDF, or approximate from text line count."""
    try:
        if binary is not None:
            with pdf2_read(BytesIO(binary)) as pdf:
                return len(pdf.pages)
        with pdf2_read(fnm) as pdf:
            return len(pdf.pages)
    except Exception:
        # Fallback: count lines in text-accessible content
        try:
            txt = get_text(fnm, binary)
            return max(1, txt.count("\n") // 40)
        except Exception:
            return 1


def extract_pdf_outlines(source):
    try:
        with pdf2_read(source if isinstance(source, str) else BytesIO(source)) as pdf:
            outlines = []

            def dfs(nodes, depth):
                for node in nodes:
                    if isinstance(node, list):
                        dfs(node, depth + 1)
                    else:
                        outlines.append((node["/Title"], depth, pdf.get_destination_page_number(node) + 1))

            dfs(pdf.outline, 0)
            return outlines
    except Exception:
        return []
