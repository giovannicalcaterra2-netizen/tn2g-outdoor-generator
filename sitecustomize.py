"""Compatibilità runtime per i log di TeX Live su Streamlit Cloud.

Alcune installazioni di LaTeX emettono byte non UTF-8. L'app V2 usa
subprocess.run(text=True), quindi impostiamo una decodifica tollerante per
impedire che un singolo carattere nel log blocchi la generazione del PDF.
"""

import subprocess as _subprocess


_original_run = _subprocess.run


def _safe_run(*popenargs, **kwargs):
    if kwargs.get("text") is True or kwargs.get("universal_newlines") is True:
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return _original_run(*popenargs, **kwargs)


_subprocess.run = _safe_run
