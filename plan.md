# blurkey: Project Plan

> A free, offline CLI that finds API keys, tokens, emails and IPs in screenshots and GIFs and covers them with opaque black bars.

## 1. Overview

**Problem.** Developers share screenshots and demo GIFs in READMEs, tweets and bug reports. Secrets often sit in the frame unnoticed. Existing redaction tools are mostly paid, and few handle GIFs.

**Solution.** One command reads the image with OCR, detects secret-looking text, and writes a safe copy.

```
uvx blurkey demo.gif   ->   demo.redacted.gif
```

**Why it can spread.**
- Free and open source, where the alternatives are paid.
- 100% local: images never leave the machine.
- GIF support, which most tools skip.
- A pre-commit / CI mode gives it a second audience.

## 2. Goals and Non-Goals

**v0.1 goals**
- Redact PNG, JPG, WebP and GIF.
- Irreversible redaction (solid bars, metadata stripped).
- Works with `uvx` on a clean machine in under 2 minutes.
- Honest published accuracy numbers.

**Non-goals for v0.1:** video files, watch mode, GUI, cloud or LLM detection, consistent labels such as `[KEY-1]`.

## 3. Users

| User | Need |
|---|---|
| Developer posting a demo GIF | Make sure no key is visible |
| Technical writer / DevRel | Clean screenshots for docs |
| Team lead | Block leaky images in pull requests |

## 4. CLI Design

```
blurkey FILE [FILE...]
  -o, --output PATH       default: <name>.redacted.<ext>, never overwrites
  --in-place              overwrite original (opt-in)
  --preview               outline detected boxes instead of filling them
  --check                 write nothing; exit 1 if secrets found
  --json                  machine-readable report
  --only / --skip KINDS   e.g. --skip ip,email
  --allow REGEX           never redact matches of this pattern
  --min-conf 0.5          OCR confidence floor
  --pad 4                 extra pixels around each box
```

Exit codes: `0` ok, `1` secrets found in `--check`, `2` error. Full secret values are never printed; show at most a 4-character prefix.

## 5. How It Works

1. **Load** the image as RGB.
2. **OCR** through an adapter returning `TextLine(text, box, conf)`. Pin the OCR package version and wrap it so the engine can be swapped.
3. **Detect** secrets in each line's text with regexes.
4. **Locate** each match in pixels. OCR boxes cover whole lines, so map the character range proportionally and pad slightly.
5. **Redact** by drawing filled black rectangles onto a fresh image. No metadata survives.
6. **Report** a summary, e.g. `Redacted 4 items: 2 API keys, 1 email, 1 IP`.

### Detectors (v0.1)

| Kind | Example rule |
|---|---|
| AWS key | `AKIA[0-9A-Z]{16}` |
| GitHub token | `gh[pousr]_...`, `github_pat_...` |
| OpenAI / Anthropic | `sk-...`, `sk-ant-...` |
| Stripe, Slack, Google | prefix-based patterns |
| JWT, Bearer token | structural patterns |
| Assignments | `api_key=`, `secret:`, `password=` (redact the value) |
| Private key header | `-----BEGIN ... PRIVATE KEY-----` |
| Email, IPv4 | standard patterns |
| High entropy | long random strings, excluding git SHAs and UUIDs |

Run specific detectors before generic ones and merge overlapping boxes.

### GIF pipeline (the differentiator)

- Keep each frame's duration and the loop count.
- Compare downscaled frames; skip OCR when a frame barely changed and reuse previous boxes.
- Apply each detected box to the neighbouring frames (about 2 before and after) so one OCR miss never flashes a secret.
- Performance target to measure: a 100-frame GIF in under 60 seconds on a laptop CPU. Provide `--frame-step N` as an escape hatch.

## 6. Tech Stack and Layout

**Python 3.10+.** Dependencies: `pillow`, `numpy`, `rich`, and an ONNX-based OCR package (RapidOCR). Confirm the OCR models ship inside the wheel so it works fully offline, and record the install size in the README.

```
blurkey/
  pyproject.toml            # console script: blurkey
  .pre-commit-hooks.yaml
  src/blurkey/
    cli.py  ocr.py  detect.py  locate.py  redact.py  gif.py  report.py
  tests/
    make_fixtures.py  test_detect.py  test_locate.py  test_redact.py  test_gif.py
  .github/workflows/ci.yml
  README.md  LICENSE (MIT)
```

## 7. Testing

- **Fixtures:** synthetic screenshots (terminal, editor and browser styles, light and dark) using only documented fake keys such as AWS's `AKIAIOSFODNN7EXAMPLE`.
- **Unit tests:** every regex with positive and negative examples.
- **Irreversibility test:** re-run OCR on the output and assert the secret text is gone; assert the covered region is a uniform colour.
- **Metrics to publish:** recall on the synthetic set and false positives on clean screenshots.

## 8. Timeline

| Day | Work |
|---|---|
| 1 | `detect.py` with tests, OCR adapter, `locate.py` |
| 2 | `redact.py`, PNG/JPG CLI, report, fixtures and recall test |
| 3 | GIF pipeline, smoothing, performance tuning |
| 4 | Packaging, `uvx` test on a clean machine, CI, pre-commit hook, README, tag `0.1.0` |
| 5+ | Launch (see below) |

## 9. Launch Plan

**Before launch**
- README top: a before/after GIF, where the demo was itself processed by blurkey.
- Clear install line, a limitations section, and the published accuracy numbers.
- Check that the name is free on PyPI (`pypi.org/project/blurkey`) and GitHub.

**Launch week** (spread posts over several days, not all at once)
- Show HN: *free, offline CLI that redacts API keys from screenshots and GIFs*
- r/Python, r/commandline, r/webdev
- X / LinkedIn post with the before/after GIF
- Answer every issue and comment quickly in week one

## 10. Success Metrics

Stars (target: aim for 1k in the first 7 days, which no plan can guarantee), PyPI downloads, issues opened, and pull requests from outside contributors.

## 11. Risks

| Risk | Mitigation |
|---|---|
| OCR misses or garbles a key (`O`/`0`, `l`/`1`) | Lenient prefix matching in v0.2, `--preview`, honest README |
| Slow on long GIFs | Frame diffing, `--frame-step` |
| Large install size | State it upfront, benchmark lighter engines later |
| Users trust it too much | Clear "review the output" warning; not a compliance tool |
| Name says "blur" but uses solid bars | Explain in README: a real blur can be undone |

## 12. Roadmap

- **v0.2:** watch mode (`--watch ~/Screenshots`), lenient OCR matching, custom rule file.
- **v0.3:** video support (mp4/mov/webm) via ffmpeg, consistent labels per value.
- **Later:** GitHub Action, browser-screenshot integration, more detector packs.

## 13. Definition of Done (v0.1)

- [ ] `uvx blurkey demo.gif` works on a clean machine
- [ ] Redacted output passes the irreversibility test
- [ ] Recall and false-positive numbers published
- [ ] CI green, pre-commit hook works
- [ ] README with before/after GIF and limitations
- [ ] Tagged and published to PyPI
