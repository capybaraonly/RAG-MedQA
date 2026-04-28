
#

import os
import subprocess

RAG-MedQA_VERSION_INFO = "unknown"


def get_RAG-MedQA_version() -> str:
    global RAG-MedQA_VERSION_INFO
    if RAG-MedQA_VERSION_INFO != "unknown":
        return RAG-MedQA_VERSION_INFO
    version_path = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)), os.pardir, "VERSION"
        )
    )
    if os.path.exists(version_path):
        with open(version_path, "r") as f:
            RAG-MedQA_VERSION_INFO = f.read().strip()
    else:
        RAG-MedQA_VERSION_INFO = get_closest_tag_and_count()
    return RAG-MedQA_VERSION_INFO


def get_closest_tag_and_count():
    try:
        # Get the current commit hash
        version_info = (
            subprocess.check_output(["git", "describe", "--tags", "--match=v*", "--first-parent", "--always"])
            .strip()
            .decode("utf-8")
        )
        return version_info
    except Exception:
        return "unknown"
