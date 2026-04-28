
#

from .oauth import OAuthClient
from .oidc import OIDCClient
from .github import GithubOAuthClient


CLIENT_TYPES = {
    "oauth2": OAuthClient,
    "oidc": OIDCClient,
    "github": GithubOAuthClient
}


def get_auth_client(config)->OAuthClient:
    channel_type = str(config.get("type", "")).lower()
    if channel_type == "":
        if config.get("issuer"):
            channel_type = "oidc"
        else:
            channel_type = "oauth2"
    client_class = CLIENT_TYPES.get(channel_type)
    if not client_class:
        raise ValueError(f"Unsupported type: {channel_type}")

    return client_class(config)
