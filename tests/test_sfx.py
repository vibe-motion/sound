import argparse
from contextlib import contextmanager, redirect_stdout
from email.message import Message
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

spec = importlib.util.spec_from_file_location('sfx', Path(__file__).parents[1] / 'scripts/sfx.py')
sfx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sfx)
URL = 'https://cdn.freesound.org/previews/1/123_456-hq.mp3'
ROW = dict(key='fs:123', title='soft whoosh', author='example', license='CC0', url=URL,
           source='https://freesound.org/people/example/sounds/123/')


@contextmanager
def project():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as folder:
        os.chdir(folder)
        try:
            yield Path(folder)
        finally:
            os.chdir(previous)


class SecurityTests(unittest.TestCase):
    def test_url_rejections(self):
        for url in ('http://cdn.freesound.org/a.mp3', 'file:///etc/passwd',
                    'https://cdn.freesound.org.evil.test/a.mp3',
                    'https://user@cdn.freesound.org/a.mp3',
                    'https://cdn.freesound.org:9090/a.mp3',
                    'https://127.0.0.1/a.mp3'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                sfx.validate_url(url, {'cdn.freesound.org'})
        self.assertEqual(sfx.validate_url(URL, {'cdn.freesound.org'}), URL)

    def test_redirect_checked_before_request(self):
        handler = sfx.SafeRedirect({'cdn.freesound.org'})
        req = urllib.request.Request(URL)
        with self.assertRaises(ValueError):
            handler.redirect_request(req, None, 302, '', {}, 'https://evil.test/a.mp3')
        redirected = handler.redirect_request(req, None, 302, '', {}, URL)
        self.assertEqual(redirected.full_url, URL)

    def test_response_validation(self):
        for body, mime in ((b'<html>blocked</html>', 'text/html'),
                           (b'not audio', 'audio/mpeg'),
                           (b'ID3' + b'x' * (32 * 1024 * 1024), 'audio/mpeg')):
            headers = Message()
            headers['Content-Type'] = mime
            response = io.BytesIO(body)
            response.headers = headers
            response.geturl = lambda: URL
            with patch.object(sfx.urllib.request, 'build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(ValueError):
                    sfx.fetch(URL, audio=True)

    def test_paths_and_symlinks(self):
        with project() as root:
            self.assertEqual(sfx.project_path('sfx/a.mp3'), root / 'sfx/a.mp3')
            with self.assertRaises(ValueError):
                sfx.project_path('../escaped.mp3')
            (root / 'link').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                sfx.project_path('link/a.mp3')
            (root / 'dangling').symlink_to(root / 'missing')
            with self.assertRaises(ValueError):
                sfx.project_path('dangling')

    def run_get(self, row=ROW, key='fs:123', license='cc0'):
        args = argparse.Namespace(out_dir='sfx', keys=[key], license=license, json=True)
        with patch.object(sfx, 'load_index', return_value={key: row}), \
             patch.object(sfx, 'fetch', return_value=b'ID3audio') as fetch, \
             redirect_stdout(io.StringIO()) as output:
            try:
                sfx.get(args)
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, json.loads(output.getvalue()), fetch

    def test_download_and_provenance(self):
        with project():
            code, results, fetch = self.run_get()
            self.assertEqual(code, 0)
            record = json.loads(Path(results[0]['metadata']).read_text())
            self.assertEqual(record['source'], ROW['source'])
            self.assertEqual(record['license'], 'CC0')
            self.assertEqual(len(record['sha256']), 64)
            self.assertEqual(Path(results[0]['file']).read_bytes(), b'ID3audio')
            code, results, fetch = self.run_get()
            self.assertEqual(code, 1)
            fetch.assert_not_called()

    def test_license_enforced_on_download(self):
        with project():
            for license in ('BY', 'BY-NC', '?'):
                code, _, fetch = self.run_get({**ROW, 'license': license})
                self.assertEqual(code, 1)
                fetch.assert_not_called()
            code, _, _ = self.run_get({**ROW, 'license': 'BY'}, license='by')
            self.assertEqual(code, 0)

    def test_poisoned_cache_does_not_escape(self):
        with project():
            for row, key in ((ROW, 'fs:../../escaped'),
                             ({**ROW, 'url': 'file:///etc/passwd'}, 'fs:123'),
                             ({**ROW, 'source': 'https://evil.test/'}, 'fs:123')):
                code, _, fetch = self.run_get(row, key)
                self.assertEqual(code, 1)
                fetch.assert_not_called()

    def test_exclusive_write_refuses_symlink(self):
        with project() as root:
            (root / 'original').write_bytes(b'keep')
            (root / 'link').symlink_to(root / 'original')
            with self.assertRaises(FileExistsError):
                sfx.write_new(root / 'link', b'overwrite')
            self.assertEqual((root / 'original').read_bytes(), b'keep')

    def test_cache_roundtrip_and_symlink_refusal(self):
        with project() as root, patch.object(sfx, 'CACHE', root / 'cache'), \
             patch.object(sfx, 'INDEX', root / 'cache/index.json'):
            sfx.save_index([ROW])
            self.assertEqual(sfx.load_index()['fs:123'], ROW)
            sfx.INDEX.unlink()
            sfx.INDEX.symlink_to(root / 'other')
            with self.assertRaises(ValueError):
                sfx.save_index([ROW])
            self.assertFalse((root / 'other').exists())

    def test_search_filters_license_locally(self):
        block = ('class="bw-search__result" data-sound-id="123" data-username="example" '
                 'data-title="whoosh" data-num-downloads="5" data-duration="0.3" '
                 f'data-mp3="{URL}" title="License: Attribution NonCommercial"')
        args = argparse.Namespace(query='whoosh', sort='relevance', license='cc0',
                                  page=1, pages=1, n=8, urls=True, json=True)
        with patch.object(sfx, 'fetch', return_value=block.encode()), \
             patch.object(sfx, 'save_index'), redirect_stdout(io.StringIO()) as output:
            sfx.freesound(args)
        self.assertEqual(json.loads(output.getvalue()), [])


if __name__ == '__main__':
    unittest.main()
