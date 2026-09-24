# blurkey

> A free, offline CLI that finds API keys, tokens, emails and IPs in screenshots and GIFs and covers them with opaque black bars.

![demo](demo/demo.png)

```bash
uvx blurkey demo.gif   # -> demo.redacted.gif
```

100% local (RapidOCR/ONNX, no network). GIF-aware. Pre-commit / CI ready.

## Install

```bash
uvx blurkey screenshot.png
# or
pip install blurkey
blurkey demo.gif --preview
```

Install size: ~120MB (ONNX models ship in the wheel so it works offline).
Requires Python 3.10+.

## Usage

```
blurkey FILE [FILE...]
  -o, --output PATH       default: <name>.redacted.<ext>, never overwrites
  --out-dir DIR           write redacted copies into DIR (never overwrites)
  --force                 allow overwriting existing outputs
  --in-place              overwrite original (opt-in)
  --preview               outline detected boxes instead of filling them
  --check                 write nothing; exit 1 if secrets found
  --json                  machine-readable report
  -q, --quiet             only print errors and --json output
  --only / --skip KINDS   e.g. --skip ipv4,email
  --allow REGEX           never redact matches of this pattern
  --min-conf 0.5          OCR confidence floor 0-1
  --pad 4                 extra pixels around each box
  --frame-step N          OCR every Nth GIF frame
  --version               show version
```

Exit codes: `0` ok, `1` secrets found in `--check`, `2` error.
Full secret values are never printed; at most a 4-char prefix in debug.

Kinds: `aws github openai anthropic stripe slack google jwt bearer assignment private_key email ipv4 high_entropy`

## Accuracy (synthetic set, v0.1)

Measured with `tests/make_fixtures.py` + `tests/measure_recall.py`
(terminal/editor/browser, light/dark, documented fake keys only):

| Set | Recall | Notes |
|---|---|---|
| AWS `AKIAIOSFODNN7EXAMPLE` | 100% (4/4 fixtures) | lenient to OCR-inserted space (`AKIA...7 EXAMPLE`) |
| email / ipv4 | 100% (8/8) | lenient to spaces around `@` / `.` |
| clean screenshots | 0 FP on prose | high-entropy threshold 4.0, SHA/UUID excluded |

GIF: `kinds` counts unique OCR detections (static frames reuse boxes without
inflating counts); `--json` also reports `frames` and `frames_with_hits`.
Pipeline overhead for 100 static frames ~0.1s excl. OCR model
(`tests/measure_perf.py`); real cost is OCR calls saved by frame-diffing.

Re-run OCR on redacted output: secret text gone, boxes uniform black (`test_redact.py`).

## Limitations

- OCR can miss or garble keys (`O`/`0`, `l`/`1`). **Always `--preview` + review output.** Not a compliance tool.
- Character-to-pixel mapping is proportional (monospace assumption) + `--pad`; may over-cover.
- GIF: frame-diff + ±2-frame smoothing; long GIFs use `--frame-step 2/3`.
- Name says "blur" but uses solid bars: a real blur can be undone.

## Pre-commit

```yaml
- repo: https://github.com/anomalyco/blurkey
  rev: v0.1.0
  hooks:
    - id: blurkey-check
```

See `.pre-commit-hooks.yaml`.
