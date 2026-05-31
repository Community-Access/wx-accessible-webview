# Contributing

**Contributions are welcome — anyone can contribute, and we want them.** This is
a Community Access open-source project, created by Taylor Arndt.

## Ways to help
- **Report bugs** — open an issue with what you expected, what happened, your OS,
  wxPython version, and screen reader (if relevant).
- **Test with screen readers** — NVDA, JAWS, Narrator (Windows), VoiceOver
  (macOS), Orca (Linux). Real-world a11y reports are the most valuable thing here.
- **Send pull requests** — features, fixes, docs, examples.

## Ground rules
- **Accessibility first.** The whole point is that screen readers read the content
  correctly. Changes shouldn't regress NVDA/JAWS/VoiceOver behavior; note how you
  tested.
- Keep it **dependency-light** — wxPython only in the core. Rendering choices
  (e.g. Markdown) belong to the caller, not this package.
- Match the existing style; format with `ruff format` (line length 100).

## Dev setup
```bash
pip install -e .            # installs wxPython
python examples/demo.py     # try it (ideally with a screen reader on)
```

## Pull requests
- Describe the change and how you verified it (which screen reader / OS).
- One focused change per PR is easiest to review.

Thanks for helping make accessible web content in wxPython the default, not the
exception.
