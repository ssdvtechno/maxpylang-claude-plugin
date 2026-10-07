# Vendored MaxPyLang

`maxpylang-0.1.1+git0a171e1-py3-none-any.whl` is MaxPyLang built from
https://github.com/Barnard-PL-Labs/MaxPyLang at commit 0a171e1 (2026-09-25), MIT license
(see the wheel's `dist-info/licenses/LICENSE.txt`). It is here so the skill works without network access:

```bash
pip install --no-index --no-deps maxpylang-0.1.1+git0a171e1-py3-none-any.whl
```

`--no-deps` is fine: `mpl.py` stands in for `tabulate` (only used to print error tables) and `numpy`
(only used by `import_objs()`, which needs Max) when they are missing. Without pip at all:
`python3 -m zipfile -e <wheel> _maxpylang` and add `_maxpylang` to `PYTHONPATH`.
