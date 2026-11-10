"""Gestion locale des travaux Ollama annulables, sans dépendance Streamlit.

Chaque requête tourne dans un processus Python propre. Un arrêt termine le
processus client et ferme sa connexion à Ollama. Aucun fichier scientifique
ou avis enseignant n'est écrit par ce module.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def start_job(payload: dict, worker_path: Path, *, executable: str | None = None) -> subprocess.Popen:
    worker_path = Path(worker_path).resolve()
    if not worker_path.is_file():
        raise FileNotFoundError(f"Worker Ollama absent : {worker_path}")
    process = subprocess.Popen(
        [executable or sys.executable, "-u", str(worker_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        if process.stdin is None:
            raise RuntimeError("Impossible de transmettre les données à Ollama.")
        process.stdin.write(json.dumps(payload, ensure_ascii=False))
        process.stdin.close()
        # communicate() ne doit pas essayer de vider un stdin déjà fermé.
        process.stdin = None
    except Exception:
        stop_job(process)
        raise
    return process


def stop_job(process: subprocess.Popen, *, grace_seconds: float = 1.0) -> None:
    """Annule vraiment le processus réseau, même s'il attend la réponse Ollama."""
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=grace_seconds)
        process.communicate(timeout=grace_seconds)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        if process.poll() is None:
            process.kill()
            process.wait()
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass


def completed_job(process: subprocess.Popen) -> dict | None:
    """Retourne None tant que le processus tourne, sinon les titres ou l'erreur."""
    if process.poll() is None:
        return None
    try:
        stdout, stderr = process.communicate(timeout=1)
    except (subprocess.TimeoutExpired, ValueError) as exc:
        raise RuntimeError(f"Impossible de lire le résultat de génération : {exc}") from exc
    if not stdout.strip():
        details = (stderr or "").strip()[-400:]
        raise RuntimeError("La génération s'est terminée sans résultat. " + details)
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Réponse du générateur de titres non conforme.") from exc
    if not isinstance(response, dict):
        raise RuntimeError("Réponse Ollama invalide.")
    if process.returncode != 0 or response.get("error"):
        raise RuntimeError(str(response.get("error") or "Génération échouée.")[:500])
    titles = response.get("titres")
    if not isinstance(titles, list) or not (1 <= len(titles) <= 5):
        raise RuntimeError("Aucun titre exploitable retourné par Ollama.")
    return response
