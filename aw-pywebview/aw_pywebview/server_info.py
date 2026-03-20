import time
from urllib.parse import urljoin

import requests
from aw_server.config import config


def get_root_url(testing: bool) -> str:
    section = "server-testing" if testing else "server"
    host = config[section]["host"]
    port = int(config[section]["port"])
    return f"http://{host}:{port}"


def wait_for_server(root_url: str, timeout: int = 20) -> bool:
    deadline = time.time() + timeout
    info_url = urljoin(root_url + "/", "api/0/info")

    while time.time() < deadline:
        try:
            resp = requests.get(info_url, timeout=1)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)

    return False
