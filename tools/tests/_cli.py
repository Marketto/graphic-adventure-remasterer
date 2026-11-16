"""rstool in the same process (no interpreter start, no re-import): same result shape as subprocess.run.
One real subprocess smoke test stays in test_pipeline.py."""
import contextlib
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rstool  # noqa: E402


def run(argv, cwd=None, check=False, **_ignored):
    argv = [str(x) for x in argv]
    out, err, code = io.StringIO(), io.StringIO(), 0
    old = os.getcwd()
    try:
        if cwd:
            os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = rstool.main(argv)
                code = rc if isinstance(rc, int) else 0
            except SystemExit as e:
                if isinstance(e.code, str):
                    err.write(e.code + "\n")
                    code = 1
                else:
                    code = e.code or 0
    finally:
        os.chdir(old)
    res = subprocess.CompletedProcess(argv, code, out.getvalue(), err.getvalue())
    if check and code:
        raise subprocess.CalledProcessError(code, argv, res.stdout, res.stderr)
    return res
