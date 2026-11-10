"""Tests du bouton Arrêter : processus interrompu, réponse ignorée, titres non publiés."""
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ollama_cancel_control import start_job, stop_job, completed_job
from ollama_titles_worker import normaliser_titres, _local_endpoint


class TestCancelableOllama(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def worker(self, code: str) -> Path:
        path = self.folder / 'worker.py'
        path.write_text(code, encoding='utf-8')
        return path

    def test_stop_terminates_running_generation(self):
        path = self.worker('import time,sys,json\njson.load(sys.stdin)\ntime.sleep(30)\nprint(json.dumps({"titres":["Titre tardif"]}))\n')
        proc = start_job({'model':'fake'}, path)
        self.assertIsNone(proc.poll())
        start = time.monotonic()
        stop_job(proc)
        self.assertLess(time.monotonic() - start, 4.0)
        self.assertIsNotNone(proc.poll())

    def test_completion_returns_titles(self):
        path = self.worker('import json,sys\njson.load(sys.stdin)\nprint(json.dumps({"titres":["Fusion des tables"],"mode":"LLM_SANS_RAG"}))\n')
        proc = start_job({'model':'fake'}, path)
        proc.wait(timeout=5)
        self.assertEqual(completed_job(proc)['titres'], ['Fusion des tables'])

    def test_failure_does_not_produce_titles(self):
        path = self.worker('import json,sys\njson.load(sys.stdin)\nprint(json.dumps({"error":"Ollama indisponible"}))\nsys.exit(1)\n')
        proc = start_job({'model':'fake'}, path)
        proc.wait(timeout=5)
        with self.assertRaisesRegex(RuntimeError, 'Ollama indisponible'):
            completed_job(proc)

    def test_normalisation(self):
        self.assertEqual(normaliser_titres([' Fusion des tables ', 'fusion des tables', 'Jointures SQL']),
                         ['Fusion des tables', 'Jointures SQL'])
        with self.assertRaises(ValueError):
            normaliser_titres([])

    def test_forbid_remote_ollama(self):
        with self.assertRaises(ValueError):
            _local_endpoint('https://example.com')
        self.assertEqual(_local_endpoint('http://127.0.0.1:11434'), 'http://127.0.0.1:11434')


if __name__ == '__main__':
    unittest.main()
