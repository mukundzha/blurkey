import re

from blurkey.detect import VALID_KINDS, detect_line


def kinds(text, **kw):
    return [(m.kind, m.value) for m in detect_line(text, **kw)]


def test_aws():
    ms = detect_line("key AKIAIOSFODNN7EXAMPLE here")
    assert any(m.kind == "aws" and m.value == "AKIAIOSFODNN7EXAMPLE" for m in ms)


def test_github():
    ms = detect_line("token ghp_abcdefghijklmnopqrstuvwxyz0123456789 here")
    assert any(m.kind == "github" for m in ms)
    ms2 = detect_line("github_pat_abcdefghij1234567890XYZ here")
    assert any(m.kind == "github" for m in ms2)


def test_openai_anthropic_order():
    ms = detect_line("sk-ant-abc123XYZ4567890123456789")
    assert ms and ms[0].kind == "anthropic"
    ms = detect_line("sk-abc123XYZ4567890123456789")
    assert any(m.kind == "openai" for m in ms)


def test_stripe_slack_google():
    assert any(m.kind == "stripe" for m in detect_line("sk_live_abcdefghijklmnop1234"))
    assert any(m.kind == "slack" for m in detect_line("xoxb-123456789012-abcdefghij"))
    assert any(m.kind == "google" for m in detect_line("AIzaSyA-abcdefghijklmnopqrstuvwxyZ123456"))


def test_jwt_bearer():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c"
    assert any(m.kind == "jwt" for m in detect_line(jwt))
    ms = detect_line("Bearer abcdefghijklmnopqrstuvwx")
    assert any(m.kind == "bearer" for m in ms)
    # bearer redacts token only, keeps label visible
    b = next(m for m in ms if m.kind == "bearer")
    assert b.value == "abcdefghijklmnopqrstuvwx"
    assert b.start == len("Bearer ")


def test_assignment_redacts_value_only():
    ms = detect_line('api_key="mysecretvalue123"')
    assert len(ms) == 1 and ms[0].kind == "assignment"
    assert ms[0].value == "mysecretvalue123"
    # AWS-style env names
    ms2 = detect_line("AWS_SECRET_ACCESS_KEY=foobar12345")
    assert any(m.kind == "assignment" and m.value == "foobar12345" for m in ms2)
    ms3 = detect_line("export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
    # aws-specific wins over generic assignment on the same value
    assert any(m.kind == "aws" for m in ms3)


def test_lenient_ocr_garbles():
    # OCR-inserted space in AWS key
    ms = detect_line("key AKIAIOSFODNN7 EXAMPLE here")
    assert any(m.kind == "aws" and m.value == "AKIAIOSFODNN7EXAMPLE" for m in ms)
    # OCR-inserted spaces in email
    assert any(m.kind == "email" for m in detect_line("contact alice @example.com ok"))
    assert any(m.kind == "email" for m in detect_line("contact a@b .com ok"))
    # skip/only/allow respect lenient spans
    assert detect_line("key AKIAIOSFODNN7 EXAMPLE here", skip={"aws"}) == []
    assert detect_line("key AKIAIOSFODNN7 EXAMPLE here", only={"aws"})
    assert detect_line("key AKIAIOSFODNN7 EXAMPLE here", only={"email"}) == []


def test_private_key():
    assert detect_line("-----BEGIN RSA PRIVATE KEY-----")[0].kind == "private_key"


def test_email_ipv4():
    assert any(m.kind == "email" for m in detect_line("contact me@ex.com ok"))
    assert any(m.kind == "ipv4" for m in detect_line("server 192.168.1.10 up"))
    assert not any(m.kind == "ipv4" for m in detect_line("version 999.999.1.1 x"))


def test_high_entropy_and_exclusions():
    assert any(m.kind == "high_entropy" for m in detect_line("tok dGhpc2lzYWhpZ2hlbnRyb3B5c3RyaW5nMTIz"))
    # uuid excluded
    assert not any(m.kind == "high_entropy" for m in detect_line("id 123e4567-e89b-12d3-a456-426614174000 ok"))
    # git sha excluded
    assert not any(m.kind == "high_entropy" for m in detect_line("commit da39a3ee5e6b4b0d3255bfef95601890afd80709 ok"))


def test_only_skip_allow():
    assert detect_line("a@b.com", skip={"email"}) == []
    assert detect_line("a@b.com", only={"email"})
    assert detect_line("a@b.com", only={"aws"}) == []
    assert detect_line("AKIAIOSFODNN7EXAMPLE", allow=re.compile("EXAMPLE")) == []


def test_overlap_merge_specific_wins():
    # sk-ant contains sk- pattern; should yield single anthropic match
    ms = detect_line("sk-ant-abc123XYZ4567890123456789")
    assert len(ms) == 1 and ms[0].kind == "anthropic"


def test_valid_kinds_complete():
    assert set(VALID_KINDS) >= {"aws", "email", "ipv4", "high_entropy"}


# negative examples: no false positives on ordinary prose
def test_no_fp_prose():
    assert detect_line("hello world, fix the bug in app.py") == []
    assert detect_line("version 2.4.1 released today") == []
