

print("Start RAG-MedQA server...")

import time
start_ts = time.time()

import logging
import os
import signal
import sys
import threading
import uuid
import faulthandler

from api.apps import app
from api.db.runtime_config import RuntimeConfig
from api.db.services.document_service import DocumentService
from common.file_utils import get_project_base_directory
from common import settings
from api.db.db_models import init_database_tables as init_web_db
from api.db.init_data import init_web_data, init_superuser
from common.versions import get_RAG-MedQA_version
from common.config_utils import show_configs
from common.log_utils import init_root_logger
from rag.utils.redis_conn import RedisDistributedLock

stop_event = threading.Event()

RAG-MedQA_DEBUGPY_LISTEN = int(os.environ.get('RAG-MedQA_DEBUGPY_LISTEN', "0"))

def update_progress():
    lock_value = str(uuid.uuid4())
    redis_lock = RedisDistributedLock("update_progress", lock_value=lock_value, timeout=60)
    logging.info(f"update_progress lock_value: {lock_value}")
    while not stop_event.is_set():
        try:
            if redis_lock.acquire():
                DocumentService.update_progress()
                redis_lock.release()
        except Exception:
            logging.exception("update_progress exception")
        finally:
            try:
                redis_lock.release()
            except Exception:
                logging.exception("update_progress exception")
            stop_event.wait(6)

def signal_handler(sig, frame):
    logging.info("Received interrupt signal, shutting down...")
    shutdown_all_mcp_sessions()
    stop_event.set()
    stop_event.wait(1)
    sys.exit(0)

if __name__ == '__main__':
    faulthandler.enable()
    init_root_logger("RAG-MedQA_server")
    logging.info(r"""
        ____   ___    ______ ______ __
       / __ \ /   |  / ____// ____// /____  _      __
      / /_/ // /| | / / __ / /_   / // __ \| | /| / /
     / _, _// ___ |/ /_/ // __/  / // /_/ /| |/ |/ /
    /_/ |_|/_/  |_|\____//_/    /_/ \____/ |__/|__/

    """)
    logging.info(
        f'RAG-MedQA version: {get_RAG-MedQA_version()}'
    )
    logging.info(
        f'project base: {get_project_base_directory()}'
    )
    show_configs()
    settings.init_settings()
    settings.print_rag_settings()

    if RAG-MedQA_DEBUGPY_LISTEN > 0:
        logging.info(f"debugpy listen on {RAG-MedQA_DEBUGPY_LISTEN}")
        import debugpy
        debugpy.listen(("0.0.0.0", RAG-MedQA_DEBUGPY_LISTEN))

    # init db
    init_web_db()
    init_web_data()
    # init runtime config
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version", default=False, help="RAG-MedQA version", action="store_true"
    )
    parser.add_argument(
        "--debug", default=False, help="debug mode", action="store_true"
    )
    parser.add_argument(
        "--init-superuser", default=False, help="init superuser", action="store_true"
    )
    args = parser.parse_args()
    if args.version:
        print(get_RAG-MedQA_version())
        sys.exit(0)

    if args.init_superuser:
        init_superuser()
    RuntimeConfig.DEBUG = args.debug
    if RuntimeConfig.DEBUG:
        logging.info("run on debug mode")

    RuntimeConfig.init_env()
    RuntimeConfig.init_config(JOB_SERVER_HOST=settings.HOST_IP, HTTP_PORT=settings.HOST_PORT)


    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def delayed_start_update_progress():
        logging.info("Starting update_progress thread (delayed)")
        t = threading.Thread(target=update_progress, daemon=True)
        t.start()

    if RuntimeConfig.DEBUG:
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            threading.Timer(1.0, delayed_start_update_progress).start()
    else:
        threading.Timer(1.0, delayed_start_update_progress).start()

    # start http server
    try:
        logging.info(f"RAG-MedQA server is ready after {time.time() - start_ts}s initialization.")
        app.run(host=settings.HOST_IP, port=settings.HOST_PORT, use_reloader=RuntimeConfig.DEBUG, debug=False)
    except Exception as e:
        logging.exception(f"Unhandled exception: {e}")
        stop_event.set()
        stop_event.wait(1)
        os.kill(os.getpid(), signal.SIGKILL)
