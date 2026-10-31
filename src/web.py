"""Local web interface: python -m src.web, then open http://localhost:8000"""
import argparse
import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import classes
from .build import PROFILES, TARGETS, BuildRequest, build
from .damage import ELEMENTS

WEB_DIR = Path(__file__).resolve().parent.parent / 'web'

REQUEST_FIELDS = {
    'classe': str, 'niveau': int, 'pa': int, 'pm': int, 'elements': list, 'exos': list, 'max_exos': int,
    'parchemins': int, 'points': bool, 'profil': str, 'cible': str, 'top': int, 'diversite': int,
    'no_dofus': bool, 'no_pet': bool,
}


def classes_payload():
    return [
        {'id': c['id'], 'nom': c['nom'], 'img': c.get('img'),
         'logo': f"https://api.dofusdb.fr/img/breeds/logo_transparent_{c['id']}.png"}
        for c in sorted(classes.load_classes().values(), key=lambda c: c['id'])
    ]


def build_request(payload):
    values = {}
    for name, kind in REQUEST_FIELDS.items():
        if payload.get(name) in (None, ''):
            continue
        values[name] = kind(payload[name]) if kind is not list else list(payload[name])
    if values.get('profil', 'degats') not in PROFILES or values.get('cible', 'aucune') not in TARGETS:
        raise ValueError("profil ou cible inconnu")
    if any(e not in ELEMENTS and e != 'multi' for e in values.get('elements', [])):
        raise ValueError("élément inconnu")
    values['top'] = max(1, min(values.get('top', 1), 3))
    return BuildRequest(**values)


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/api/classes':
            return self.send_json(200, classes_payload())
        path = 'index.html' if self.path in ('/', '') else self.path.lstrip('/').split('?')[0]
        target = (WEB_DIR / path).resolve()
        if WEB_DIR not in target.parents or not target.is_file():
            return self.send_json(404, {'erreur': 'introuvable'})
        body = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/build':
            return self.send_json(404, {'erreur': 'introuvable'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            request = build_request(json.loads(self.rfile.read(length) or b'{}'))
            return self.send_json(200, build(request))
        except (ValueError, KeyError, TypeError) as e:
            return self.send_json(400, {'erreur': str(e)})
        except Exception as e:  # report solver / data errors to the page
            traceback.print_exc()
            return self.send_json(500, {'erreur': str(e)})

    def log_message(self, fmt, *args):
        if '/api/' in (args[0] if args else ''):
            super().log_message(fmt, *args)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Interface web de l\'optimiseur')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Interface disponible sur http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
