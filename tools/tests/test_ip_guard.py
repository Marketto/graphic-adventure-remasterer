"""The guard that keeps the public repository clean: secrets, personal e-mails, staged
content, commit messages and private texts. Fake keys are built at run time, so this file
itself contains no secret-looking string."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import ip_guard  # noqa: E402

HEX = "0123456789abcdef"


def fake(prefix, n, alphabet=HEX):
    return prefix + (alphabet * 10)[:n]


def test_secrets_and_emails_are_found():
    lines = {
        "token GitHub": "token: " + fake("gh" + "p_", 36, "AbCdEf0123456789"),
        "chiave Anthropic": fake("sk-" + "ant-", 40, "abcXYZ0123456789"),
        "chiave ElevenLabs": "x = " + fake("sk" + "_", 48),
        "chiave fal.ai": fake("", 8) + "-" + fake("", 4) + "-" + fake("", 4) + "-" + fake("", 4) + "-" + fake("", 12)
        + ":" + fake("", 32),
        "chiave privata": "-----BEGIN RSA PRIVATE " + "KEY-----",
        "segreto assegnato": "ELEVENLABS_API_KEY=" + fake("", 32),
    }
    for what, line in lines.items():
        found = ip_guard.check_text("f.txt", line, set())
        assert any(what in p for p in found), (what, found)
    mail = "scrivi a mario.rossi" + "@" + "gmail.com"
    assert any("e-mail" in p for p in ip_guard.check_text("f.txt", mail, set()))
    ok = "Autore <Utente" + "@users.noreply.github.com>, FAL_KEY=$FAL_KEY, api_key = <la tua chiave>"
    assert ip_guard.check_text("f.txt", ok, set()) == []


def test_private_catalogue_columns(tmp_path):
    cat = tmp_path / "catalog.tsv"
    cat.write_text("key\tlang\tsource\ttext\tkind\tlocation\tspeaker\tbox_w\tstatus\tnote\n"
                   "a1\ten\tthe old lighthouse keeper never sleeps at night\t\tballoon\tmolo\tguardiano\t120\ttodo\t\n",
                   encoding="utf-8")
    grams = ip_guard.private_grams_of(str(cat))
    assert "old lighthouse keeper never sleeps at" in grams
    assert not any("kind location speaker" in g for g in grams)  # header columns are not game text
    found = ip_guard.check_text("doc.md", "Esempio: the old lighthouse keeper never sleeps at night.", set(), grams)
    assert found and "testo del gioco" in found[0]


def test_staged_content_and_message(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)  # noqa: E731
    run("git", "init", "-q")
    (repo / "a.txt").write_text("contenuto pulito\n")
    run("git", "add", "a.txt")
    (repo / "a.txt").write_text("ora " + fake("gh" + "p_", 36, "AbCdEf0123456789") + "\n")  # not staged
    old_root = ip_guard.ROOT
    try:
        ip_guard.ROOT = str(repo)
        assert ip_guard.scan(["a.txt"], set(), [], staged=True) == []      # what will be committed
        assert ip_guard.scan(["a.txt"], set(), [], staged=False) != []     # the working copy
    finally:
        ip_guard.ROOT = old_root
    msg = tmp_path / "MSG"
    msg.write_text("Correzione\n\n# commento ignorato\nCo-Authored-By: Claude <noreply" + "@anthropic.com>\n")
    assert subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "ip_guard.py"), "--message",
                           str(msg)], capture_output=True).returncode == 0
    msg.write_text("Correzione per mario.rossi" + "@" + "gmail.com\n")
    assert subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "ip_guard.py"), "--message",
                           str(msg)], capture_output=True).returncode == 1
