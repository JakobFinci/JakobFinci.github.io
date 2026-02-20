#!/usr/bin/env python3
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
html_files = [p for p in root.rglob('*.html') if '.git' not in p.parts]

errors = []

for file in html_files:
    text = file.read_text(encoding='utf-8')
    clean = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.S)

    if clean.count('<body') > 1:
        errors.append(f"{file}: multiple <body> tags")
    if clean.count('</html>') > 1:
        errors.append(f"{file}: multiple </html> tags")

    for href in re.findall(r'href="([^"]+)"', clean):
        if href.startswith(('http://', 'https://', 'mailto:', '#')) or '{{' in href or '{%' in href:
            continue
        target = href.split('#')[0].split('?')[0]
        if not target:
            continue
        if target.startswith('/'):
            abs_target = root / target.lstrip('/')
        else:
            abs_target = (file.parent / target).resolve()
        if abs_target.is_dir():
            abs_target = abs_target / 'index.html'
        if not abs_target.exists():
            errors.append(f"{file}: broken link {href}")

if errors:
    print('\n'.join(errors))
    sys.exit(1)

print(f"Validated {len(html_files)} HTML files: structure + internal links OK")
