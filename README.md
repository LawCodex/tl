# Timor-Leste — LawCodex

Timor-Leste legislation as plain Markdown, in Portuguese (the language of the Jornal da
República; Tetum versions exist only for a few acts). Part of
[LawCodex](https://github.com/LawCodex).

## What is covered

| Category | Directory | Files |
|---|---|---|
| Constitution of the Democratic Republic of Timor-Leste (2002) | `constituicao/` | 1 |
| Codes published on the Jornal site (Civil Code, Penal Code, Code of Criminal Procedure, Code of Civil Procedure) | `codigos/` | 4 |
| Laws of the National Parliament (Leis do Parlamento Nacional) | `leis/<year>/lei-NNN-YYYY.md` | 262 |
| Decree-laws of the Government (Decretos-Leis do Governo) | `decretos-leis/<year>/decreto-lei-NNN-YYYY.md` | 843 |
| **Total** | | **1110** |

These are the acts **as published** (original texts), one file per act as listed in the Jornal's
indexes — Timor-Leste has no official consolidated database, so amendments are separate acts and
repealed acts are not marked. Every file therefore has `status: unknown`.

### Gaps

The indexes list 277 distinct laws and 912 distinct decree-laws. Not converted:

- 45 acts whose heading could not be located in the linked issue PDF (heading printed in an
  unexpected form, or the index links the wrong issue);
- 36 acts whose PDF has no text layer (image scans, mainly 2004–2009) or yielded no text;
- 3 PDFs that return HTTP 404 (Série I 2012 n.º 41, 2014 n.º 25 and n.º 44).

`scripts/tl_convert.py` prints the exact list.


### Not covered

- Other Série I acts (Presidential decrees, Government decrees, parliamentary and Government
  resolutions, ministerial diplomas, court and agency acts) and Série II.
- UNTAET regulations (2000–2002), some of which remain in force (http://mj.gov.tl/jornal/lawsTL).
- Tetum translations.

## How the text is extracted

Since about 2008 the index links to the PDF of the whole Série I issue in which an act was
published; older acts have their own PDF. The Jornal is printed in two columns, so each page is
extracted column by column (`pdftotext` with cropping); the act is then located by its heading
(`LEI N.º 1/2026`, `DECRETO-LEI N.º 13/2026`) and cut at the next act heading. Running headers
(Jornal name, issue number, date, page number) are removed; Títulos/Capítulos/Secções and Artigos
(with their epigraphs) become headings. Words hyphenated at line ends may appear joined
(e.g. "decretolei") because the PDF text layer does not keep the hyphen. Check doubtful passages
against the PDF in `source`.

## Source

Jornal da República, Ministério da Justiça — https://www.mj.gov.tl/jornal/ (indexes `?q=node/12`
and `?q=node/13`; Constitution `public/docs/ConstituicaoRDTL_Portugues.pdf`; codes under
`files/`). Retrieved 2026-10-13. robots.txt specifies `Crawl-delay: 10`, which was respected
(one request every 10 s, descriptive User-Agent). The Jornal da República is the official
gazette; its texts are official acts of the State, reproduced for public information.

## Regenerate

```sh
pip install -r scripts/requirements.txt   # plus poppler (pdftotext, pdfinfo)
python scripts/tl_fetch.py ../_raw/tl
python scripts/tl_convert.py ../_raw/tl .
```
