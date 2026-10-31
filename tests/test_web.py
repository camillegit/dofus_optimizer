import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from src.web import Handler, build_request


def test_build_request_validation():
    request = build_request({'classe': '1', 'pa': '12', 'elements': ['air'], 'exos': ['pa'], 'top': 9, 'max_exos': None})
    assert request.pa == 12 and request.elements == ['air'] and request.top == 3 and request.max_exos is None
    for bad in ({'classe': '1', 'elements': ['lumière']}, {'classe': '1', 'profil': 'boss'}):
        with pytest.raises(ValueError):
            build_request(bad)


@pytest.fixture(scope='module')
def server():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_static_and_classes(server):
    page = urllib.request.urlopen(server + '/').read().decode()
    assert 'Forge de Builds' in page
    classes = json.loads(urllib.request.urlopen(server + '/api/classes').read())
    assert len(classes) == 19 and classes[0]['nom'] == 'Féca'
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(server + '/%2e%2e/src/web.py')
    assert error.value.code == 404


def test_build_endpoint_rejects_bad_payload(server):
    request = urllib.request.Request(server + '/api/build', data=b'{"classe": "1", "elements": ["x"]}', method='POST')
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request)
    assert error.value.code == 400
