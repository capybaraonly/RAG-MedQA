
#
import pytest
import requests

from configs import HOST_ADDRESS, VERSION


@pytest.mark.p3
def test_route_not_found_returns_json():
    url = f"{HOST_ADDRESS}/api/{VERSION}/__missing_route__"
    res = requests.get(url)
    assert res.status_code == 404
    payload = res.json()
    assert payload["error"] == "Not Found"
    assert f"/api/{VERSION}/__missing_route__" in payload["message"]
