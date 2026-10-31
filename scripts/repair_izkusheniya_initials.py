#!/usr/bin/env python3
"""Correct the verified single wrong initial in the published PDF and EPUB."""
from pathlib import Path
from tempfile import NamedTemporaryFile
import os, zipfile
import fitz

folder = Path("books/izkusheniya-v-zdracha")
pdf = folder/"izkusheniya-v-zdracha.pdf"
epub = folder/"izkusheniya-v-zdracha.epub"
old = "К крал Фелипе Четвърти"
new = "С крал Фелипе Четвърти"

def fix_pdf():
    d = fitz.open(pdf)
    matches = []
    for n,p in enumerate(d):
        words=p.get_text("words", sort=True)
        for i, w in enumerate(words[:-2]):
            if w[4]=="К" and words[i+1][4]=="крал" and words[i+2][4]=="Фелипе" and w[5:7]==words[i+1][5:7]:
                matches.append((n,w))
    print("PDF pages:", len(d), "initial matches:", [(n+1,w[4]) for n,w in matches])
    if len(matches)!=1:
        raise RuntimeError("Expected exactly one PDF initial; no PDF change made")
    n,w=matches[0]
    p=d[n]
    glyph=None
    spaninfo=None
    for block in p.get_text("rawdict")["blocks"]:
        if block["type"]!=0: continue
        for line in block["lines"]:
            for span in line["spans"]:
                for ch in span["chars"]:
                    box=fitz.Rect(ch["bbox"])
                    if ch["c"]=="К" and box.intersects(fitz.Rect(w[:4])) and abs(box.x0-w[0])<3:
                        glyph=ch
                        spaninfo=span
                        break
                if glyph: break
            if glyph: break
        if glyph: break
    if not glyph: raise RuntimeError("Cannot isolate original glyph")
    box=fitz.Rect(glyph["bbox"])
    box=fitz.Rect(box.x0+.08,box.y0+.08,box.x1-.08,box.y1-.08)
    font=next((s for s in [
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"] if os.path.isfile(s)),None)
    if not font: raise RuntimeError("No Cyrillic-capable serif font")
    p.add_redact_annot(box,fill=(1,1,1),cross_out=False)
    p.apply_redactions(images=0,graphics=0,text=0)
    p.insert_text(fitz.Point(glyph["origin"]),"С",fontname="repairedinitial",
                  fontfile=font,fontsize=spaninfo["size"],
                  color=fitz.sRGB_to_pdf(spaninfo["color"]),overlay=True)
    temp=pdf.with_suffix(".pdf.tmp")
    d.save(str(temp),garbage=4,deflate=True)
    d.close()
    with fitz.open(str(temp)) as chk:
        assert len(chk)>200 and chk[n].get_text()
    os.replace(temp,pdf)
    print("PDF fixed page:",n+1)

def fix_epub():
    temp=epub.with_suffix(".epub.tmp")
    found=0
    with zipfile.ZipFile(epub) as zin, zipfile.ZipFile(temp,"w") as zout:
        for item in zin.infolist():
            body=zin.read(item.filename)
            if item.filename.lower().endswith((".xhtml",".html",".htm")):
                source=body.decode("utf-8")
                occurrences=source.count(old)
                if occurrences:
                    body=source.replace(old,new).encode("utf-8")
                    found+=occurrences
                    print("EPUB replaced in:",item.filename)
            zout.writestr(item,body)
    if found!=1:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"EPUB initial not found uniquely: {found}")
    with zipfile.ZipFile(temp) as chk:
        assert chk.testzip() is None
    os.replace(temp,epub)

if __name__=="__main__":
    if not pdf.exists() or not epub.exists(): raise RuntimeError("Missing publication files")
    # Validate EPUB match first so the two formats are not partially modified.
    with zipfile.ZipFile(epub) as z:
        matches=sum(z.read(n).decode("utf-8").count(old) for n in z.namelist() if n.lower().endswith((".xhtml",".html",".htm")))
    if matches!=1: raise RuntimeError(f"Expected one EPUB match, got {matches}")
    fix_pdf()
    fix_epub()
    print("COMPLETE: Both publication files corrected, existing download URLs preserved")
