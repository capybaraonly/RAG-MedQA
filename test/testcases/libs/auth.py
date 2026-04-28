
#
from requests.auth import AuthBase


class RAG-MedQAHttpApiAuth(AuthBase):
    def __init__(self, token):
        self._token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self._token}"
        return r


class RAG-MedQAWebApiAuth(AuthBase):
    def __init__(self, token):
        self._token = token

    def __call__(self, r):
        r.headers["Authorization"] = self._token
        return r
