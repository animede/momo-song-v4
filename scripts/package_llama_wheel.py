#!/usr/bin/env python3
"""Download one upstream llama-cpp-python wheel and wrap it as a release asset."""

from __future__ import annotations

import argparse
import html.parser
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


class Links(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            value = dict(attrs).get("href")
            if value:
                self.hrefs.append(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--accelerator", required=True)
    parser.add_argument("--system", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = f"https://abetlen.github.io/llama-cpp-python/whl/{args.accelerator}/llama-cpp-python/"
    page = urllib.request.urlopen(index).read().decode()
    links = Links()
    links.feed(page)
    platform_tag = "manylinux" if args.system == "linux" else "win_amd64"
    candidates = sorted({
        urllib.parse.urljoin(index, href) for href in links.hrefs
        if (f"-{args.version}-" in href and platform_tag in href and "x86_64" in href
            and "musllinux" not in href and href.endswith(".whl"))
    })
    if len(candidates) != 1:
        raise SystemExit(f"Expected one matching wheel, found {len(candidates)} at {index}")
    wheel_url = candidates[0]
    wheel_name = urllib.parse.urlparse(wheel_url).path.rsplit("/", 1)[-1]
    wheel = args.output.parent / wheel_name
    urllib.request.urlretrieve(wheel_url, wheel)
    license_url = "https://raw.githubusercontent.com/abetlen/llama-cpp-python/main/LICENSE.md"
    license_file = args.output.parent / "LICENSE.llama-cpp-python"
    urllib.request.urlretrieve(license_url, license_file)
    source = args.output.parent / "SOURCE.txt"
    source.write_text(f"Wheel: {wheel_url}\nLicense: {license_url}\n", encoding="utf-8")
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in (wheel, license_file, source):
            bundle.write(path, path.name)


if __name__ == "__main__":
    main()
