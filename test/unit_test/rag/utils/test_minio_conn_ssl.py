
#
"""
Unit tests for MinIO client SSL/secure configuration (_build_minio_http_client).
Covers issue #13158.
"""
import ssl
from unittest.mock import patch


class TestBuildMinioHttpClient:
    """Test _build_minio_http_client helper."""

    @patch("rag.utils.minio_conn.settings")
    def test_returns_none_when_verify_true(self, mock_settings):
        mock_settings.MINIO = {"verify": True}
        from rag.utils.minio_conn import _build_minio_http_client
        client = _build_minio_http_client()
        assert client is None

    @patch("rag.utils.minio_conn.settings")
    def test_returns_none_when_verify_missing(self, mock_settings):
        mock_settings.MINIO = {}
        from rag.utils.minio_conn import _build_minio_http_client
        client = _build_minio_http_client()
        assert client is None

    @patch("rag.utils.minio_conn.settings")
    def test_returns_pool_manager_when_verify_false(self, mock_settings):
        mock_settings.MINIO = {"verify": False}
        from rag.utils.minio_conn import _build_minio_http_client
        client = _build_minio_http_client()
        assert client is not None
        assert hasattr(client, "connection_pool_kw")
        assert client.connection_pool_kw.get("cert_reqs") == ssl.CERT_NONE

    @patch("rag.utils.minio_conn.settings")
    def test_returns_pool_manager_when_verify_string_false(self, mock_settings):
        mock_settings.MINIO = {"verify": "false"}
        from rag.utils.minio_conn import _build_minio_http_client
        client = _build_minio_http_client()
        assert client is not None
        assert client.connection_pool_kw.get("cert_reqs") == ssl.CERT_NONE

    @patch("rag.utils.minio_conn.settings")
    def test_returns_none_when_verify_string_1(self, mock_settings):
        mock_settings.MINIO = {"verify": "1"}
        from rag.utils.minio_conn import _build_minio_http_client
        client = _build_minio_http_client()
        assert client is None
