#!/usr/bin/env python3
"""Fetch Timor-Leste legislation from the Jornal da República (Ministry of Justice),
https://www.mj.gov.tl/jornal/ .

Index pages: "Leis do Parlamento Nacional" (node/12) and "Decretos-Leis do Governo" (node/13),
plus the Constitution and the codes linked from the home page. Each index row gives the act
number, its description, publication date and a link to the PDF (either the act alone or the
whole Série I issue in which it was published). robots.txt asks for Crawl-delay: 10, which we
respect. Raw files are cached under _raw/tl/.
Usage: tl_fetch.py [RAW_DIR]
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse

import requests

UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
BASE = "https://www.mj.gov.tl/jornal/"
DELAY = 10.0  # robots.txt Crawl-delay
INDEXES = {"lei": "?q=node/12", "decreto-lei": "?q=node/13"}
EXTRA = [
    ("constituicao", "Constituição da República Democrática de Timor-Leste", "public/docs/ConstituicaoRDTL_Portugues.pdf"),
    ("codigo-civil", "Código Civil", "files/Codigo_Civil.pdf"),
    ("codigo-penal", "Código Penal", "files/Codigo_Penal.pdf"),
    ("codigo-processo-penal", "Código de Processo Penal", "files/Codigo_Processo_Penal.pdf"),
    ("codigo-processo-civil", "Código de Processo Civil", "files/Codigo_de_Processo_Civil.pdf"),
]
RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "_raw", "tl")
os.makedirs(os.path.join(RAW, "pdf"), exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = UA


def get(url):
    for i in range(4):
        try:
            r = S.get(url, timeout=600)
            time.sleep(DELAY)
            if r.status_code in (403, 404) or (r.status_code >= 500 and i >= 1):
                return r
            r.raise_for_status()
            return r
        except Exception as e:  # noqa
            w = 15 * 2 ** i
            print(f"  ! {url}: {e!r}; retry in {w}s", flush=True)
            time.sleep(w)
    return None


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def pdf_path(rel):
    return os.path.join(RAW, "pdf", re.sub(r"[^A-Za-z0-9._-]+", "_", rel.strip("/")))


def main():
    jf = os.path.join(RAW, "index.json")
    if os.path.exists(jf):
        items = json.load(open(jf))
    else:
        items = []
        for kind, q in INDEXES.items():
            s = get(BASE + q).text
            for row in re.findall(r"<tr>(.*?)</tr>", s, re.S):
                cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
                links = [html.unescape(h) for h in re.findall(r'href="([^"]+\.pdf)"', row, re.I)]
                if len(cells) < 4 or not links:
                    continue
                m = re.search(r"(\d+)\s*/\s*(\d{4})", cells[0])
                if not m:
                    continue
                pt = next((l for l in links if "traducao" not in l), links[0])
                items.append({"kind": kind, "number": f"{int(m.group(1))}/{m.group(2)}", "title": cells[1],
                              "published": cells[2], "pdf": pt})
        for slug, title, rel in EXTRA:
            items.append({"kind": slug, "number": "", "title": title, "published": "", "pdf": rel})
        json.dump(items, open(jf, "w"), ensure_ascii=False, indent=1)
    print(len(items), "items;", len({i["pdf"] for i in items}), "PDFs", flush=True)
    done = set()
    for n, it in enumerate(items):
        rel = it["pdf"]
        if rel in done:
            continue
        done.add(rel)
        f = pdf_path(rel)
        if os.path.exists(f) or os.path.exists(f + ".missing"):
            continue
        m = re.match(r"^https?:/*(public|files)/", rel)  # malformed links such as "http://public/docs/..."
        if m:
            rel_path = rel[m.start(1):]
            url = urllib.parse.urljoin(BASE, urllib.parse.quote(rel_path, safe="/%"))
        elif re.match(r"^https?://", rel):
            url = urllib.parse.quote(rel, safe=":/%?&=")
        else:
            url = urllib.parse.urljoin(BASE, urllib.parse.quote(rel, safe="/%"))
        r = get(url)
        if r is not None and r.status_code == 200 and r.content.startswith(b"%PDF"):
            open(f, "wb").write(r.content)
        else:
            print("  FAIL", rel, getattr(r, "status_code", None), flush=True)
            open(f + ".missing", "w").write(str(getattr(r, "status_code", None)))
        if len(done) % 25 == 0:
            print(f"  {len(done)} PDFs ({n}/{len(items)})", flush=True)


if __name__ == "__main__":
    main()
