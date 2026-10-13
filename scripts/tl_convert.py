#!/usr/bin/env python3
"""Convert Jornal da República PDFs (see tl_fetch.py) to LawCodex Markdown.

The Jornal is printed in two columns: each page is extracted column by column with poppler's
`pdftotext -x/-y/-W/-H` cropping, so the reading order is preserved. For PDFs that contain a
whole Série I issue, the act is located by its upper-case heading ("LEI N.º 1/2026",
"DECRETO-LEI N.º 13/2026") and cut at the next act heading.

Usage: tl_convert.py [RAW_DIR] [OUT_DIR]
"""
import json
import os
import re
import subprocess
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "_raw", "tl")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..")
BASE = "https://www.mj.gov.tl/jornal/"
RETRIEVED = date.today().isoformat()
os.makedirs(os.path.join(RAW, "txt"), exist_ok=True)

ACT_HEAD = re.compile(r"^(LEI|DECRETO-LEI|DECRETO\s+DO\s+(GOVERNO|PRESIDENTE)[A-Z ]*|DECRETO|RESOLUÇÃO\s+DO\s+"
                      r"(GOVERNO|PARLAMENTO\s+NACIONAL)|RESOLUÇÃO|DIPLOMA\s+MINISTERIAL|DESPACHO|ACÓRDÃO|AVISO|"
                      r"DELIBERAÇÃO|DECLARAÇÃO|REGULAMENTO|ORDEM\s+DE\s+SERVIÇO|INSTRUÇÃO|LEI\s+DE\s+REVISÃO)"
                      r"\s+N\.?\s*[º°oO.]*\s*\d+\s*/\s*\d{2,4}", re.U)
NOISE = [re.compile(p) for p in (
    r"^Jornal da República$", r"^Série I+,?\s*N\.?\s*[º°o.]*\s*\S+.*$", r"^Página \d+\s*$",
    r"^(Segunda|Terça|Quarta|Quinta|Sexta)-[Ff]eira,\s+\d+ de \S+ de \d{4}\s*$",
    r"^(Sábado|Domingo),\s+\d+ de \S+ de \d{4}\s*$", r"^\$ ?\d+\.\d+$",
    r"^PUBLICAÇÃO OFICIAL DA REPÚBLICA DEMOCRÁTICA DE TIMOR\s*-\s*LESTE$")]
STRUCT = [(re.compile(r"^(LIVRO)\s+[IVXLC]+.*$", re.I), 0), (re.compile(r"^(PARTE)\s+[IVXLC]+.*$"), 0),
          (re.compile(r"^(TÍTULO)\s+[IVXLC]+.*$"), 1), (re.compile(r"^(CAPÍTULO)\s+[IVXLC]+.*$"), 2),
          (re.compile(r"^(SECÇÃO|SEÇÃO)\s+[IVXLC]+.*$"), 3), (re.compile(r"^(SUBSECÇÃO|SUBSEÇÃO)\s+[IVXLC]+.*$"), 4)]
ART = re.compile(r"^Artigo\s+(\d+[.º°o]*(\s*-?\s*[A-Z])?)\.?[º°]?\s*$")


def page_size(pdf):
    info = subprocess.run(["pdfinfo", pdf], capture_output=True).stdout.decode("utf-8", "replace")
    n = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    w, h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups())
    return n, w, h


def column_text(pdf):
    cache = os.path.join(RAW, "txt", os.path.basename(pdf) + ".txt")
    if os.path.exists(cache):
        return open(cache, encoding="utf-8").read()
    n, w, h = page_size(pdf)
    parts = []
    for p in range(1, n + 1):
        for x0 in (0, w / 2):
            r = subprocess.run(["pdftotext", "-enc", "UTF-8", "-f", str(p), "-l", str(p), "-x", str(int(x0)),
                                "-y", "0", "-W", str(int(w / 2) + 1), "-H", str(int(h) + 1), pdf, "-"],
                               capture_output=True)
            parts.append(r.stdout.decode("utf-8", "replace"))
    t = "\n".join(parts)
    open(cache, "w", encoding="utf-8").write(t)
    return t


def plain_text(pdf):
    return subprocess.run(["pdftotext", "-enc", "UTF-8", pdf, "-"], capture_output=True).stdout.decode("utf-8", "replace")


def clean_lines(t):
    out = []
    for x in t.replace("\f", "\n").split("\n"):
        x = x.strip()
        if not x or any(p.match(x) for p in NOISE):
            continue
        out.append(x)
    return out


def find_act(lines, kind, number):
    n, y = number.split("/")
    word = "LEI" if kind == "lei" else "DECRETO-LEI"
    core = rf"{word}\s+N\.?\s*[º°oO.]*\s*0*{n}\s*/\s*({y}|{y[2:]})\b"
    upper = re.compile("^" + core)
    alone = re.compile("^" + core + r"\s*(de\s+\d+\s+de\s+\w+(\s+de\s+\d{4})?)?\s*$", re.I)
    def toc(i):  # entries of the issue's table of contents (SUMÁRIO) have dotted leaders
        return any("...." in x for x in lines[i:i + 4])
    starts = [i for i, x in enumerate(lines) if upper.match(x) and not toc(i)]
    if not starts:
        cands = [i for i, x in enumerate(lines) if alone.match(x)]
        nontoc = [i for i in cands if not toc(i)]
        starts = nontoc or (cands[1:] if len(cands) > 1 else cands)
    if not starts:
        return None
    s = starts[0]
    head_alone = re.compile(ACT_HEAD.pattern + r"\s*(de\s+\d+\s+de\s+\w+(\s+de\s+\d{4})?)?\s*$", re.I)
    e = next((i for i in range(s + 2, len(lines))
              if head_alone.match(lines[i]) and not re.match("^" + core, lines[i], re.I)),
             len(lines))
    return lines[s:e]


NEWPARA = re.compile(r"^(\d+\.\s|[a-z]\)\s|[ivx]+\)\s|\([a-z]\)\s|«|“)")


def join(lines):
    paras, cur = [], ""
    for ln in lines:
        if not cur:
            cur = ln
        elif NEWPARA.match(ln) or (cur.endswith((".", ":", ";")) and ln[:1].isupper()) \
                or (ln.isupper() and len(ln) < 90) or (cur.isupper() and len(cur) < 90):
            paras.append(cur)
            cur = ln
        else:
            cur += " " + ln
    if cur:
        paras.append(cur)
    return [re.sub(r"^(\d+[.)]\s|[#>*+|]|-\s)", r"\\\1", p) for p in paras]


def to_md(lines):
    blocks, buf = [], []

    def flush():
        if buf:
            blocks.append(("text", join(buf)))
            buf.clear()
    i = 0
    while i < len(lines):
        ln = lines[i]
        st = next((lv for rx, lv in STRUCT if rx.match(ln)), None)
        if st is not None and len(ln) < 40:
            flush()
            title = lines[i + 1] if i + 1 < len(lines) and lines[i + 1].isupper() else ""
            blocks.append(("struct", st, ln + (f" — {title}" if title else "")))
            i += 2 if title else 1
            continue
        m = ART.match(ln)
        if m:
            flush()
            epig = lines[i + 1] if i + 1 < len(lines) and not NEWPARA.match(lines[i + 1]) \
                and len(lines[i + 1]) < 120 and not lines[i + 1].endswith((".", ";")) else ""
            blocks.append(("art", None, ln + (f" — {epig}" if epig else "")))
            i += 2 if epig else 1
            continue
        buf.append(ln)
        i += 1
    flush()
    levels = sorted({b[1] for b in blocks if b[0] == "struct"})
    lv = {x: k + 2 for k, x in enumerate(levels)}
    art_lv = min(6, 2 + len(levels))
    out = []
    for b in blocks:
        if b[0] == "text":
            out += b[1]
        elif b[0] == "struct":
            out.append("#" * lv[b[1]] + " " + b[2])
        else:
            out.append("#" * art_lv + " " + b[2])
    return "\n\n".join(out)


def slug(s, n=60):
    import unicodedata
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].rstrip("-")


def yq(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main():
    items = json.load(open(os.path.join(RAW, "index.json"), encoding="utf-8"))
    stats = {}
    seen = set()
    for it in items:
        pdf = os.path.join(RAW, "pdf", re.sub(r"[^A-Za-z0-9._-]+", "_", it["pdf"].strip("/")))
        if not os.path.exists(pdf):
            stats["missing-pdf"] = stats.get("missing-pdf", 0) + 1
            continue
        kind = it["kind"]
        if kind in ("lei", "decreto-lei"):
            key = (kind, it["number"])
            if key in seen:
                continue
            seen.add(key)
            lines = clean_lines(column_text(pdf))
            act = find_act(lines, kind, it["number"])
            if act is None or len(to_md(act)) < 300:
                # headings centred across both columns are cut by the column crop:
                # fall back to poppler's own reading order for this act
                alt = find_act(clean_lines(plain_text(pdf)), kind, it["number"])
                if alt is not None and len(to_md(alt)) >= 300:
                    act = alt
            if act is None:
                # single-act PDFs (2002-2008) may lack a matching heading: use the whole document
                if "/serie_1/" not in it["pdf"].lower() and "serie" not in os.path.basename(pdf).lower():
                    act = lines
                else:
                    stats["not-found"] = stats.get("not-found", 0) + 1
                    print("  not found:", kind, it["number"], it["pdf"], flush=True)
                    continue
            n, y = it["number"].split("/")
            d = "leis" if kind == "lei" else "decretos-leis"
            rel = f"{d}/{y}/{kind}-{int(n):03d}-{y}.md"
            title = f"{'Lei' if kind == 'lei' else 'Decreto-Lei'} n.º {it['number']} — {it['title']}"
            typ = "law" if kind == "lei" else "decree_law"
            ident = f"{'Lei' if kind == 'lei' else 'Decreto-Lei'} n.º {it['number']}"
        else:
            # constitution / codes: some are single-column documents; keep the extraction that
            # yields more article headings
            cands = [clean_lines(column_text(pdf)), clean_lines(plain_text(pdf))]
            act = max(cands, key=lambda ls: sum(1 for x in ls if ART.match(x)))
            d = "constituicao" if kind == "constituicao" else "codigos"
            rel = f"{d}/{kind}.md"
            title, typ, ident = it["title"], ("constitution" if d == "constituicao" else "code"), it["title"]
        body = to_md(act)
        if len(body) < 300:
            stats["empty"] = stats.get("empty", 0) + 1
            print("  empty:", rel, flush=True)
            continue
        fm = ["---", f"title: {yq(title)}", f"identifier: {yq(ident)}", f"type: {typ}", "jurisdiction: tl",
              "language: pt"]
        pm = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", it.get("published") or "")
        if pm:
            fm.append(f"date: {pm.group(3)}-{int(pm.group(2)):02d}-{int(pm.group(1)):02d}")
        fm += [f"status: {'in_force' if kind == 'constituicao' else 'unknown'}", f"source: {yq(BASE + it['pdf'])}", f"retrieved: {RETRIEVED}", "---", "",
               f"# {title}", "", body, ""]
        p = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(fm))
        stats[d] = stats.get(d, 0) + 1
    print(stats)


if __name__ == "__main__":
    main()
