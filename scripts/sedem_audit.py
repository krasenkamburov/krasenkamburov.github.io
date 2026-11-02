import json, zipfile, re
from pathlib import Path
import fitz
from lxml import etree
root=Path('books/sedem-piesi')
book=fitz.open(root/'sedem-piesi.pdf')
report={'pdf_pages':len(book),'pdf_size':(root/'sedem-piesi.pdf').stat().st_size,'pdf_page_headers':[],'pdf_toc':book.get_toc(),'pdf_metadata':book.metadata}
for idx,p in enumerate(book):
    lines=[s.strip() for s in p.get_text(sort=True).splitlines() if s.strip()]
    headings=[{'line':i,'text':s[:160]} for i,s in enumerate(lines[:18]) if re.search(r'(ДЕЙСТВ|КАРТИН|СЦЕН|ПРОЛОГ|ЕПИЛОГ|^БЕБА$|ЖАДУВАН|ВСЕКИ ПЕТ|ГЛИНА|КАЛЕНДИ|КАТО КУЧЕ|СПОНТАННО)',s,re.I)]
    if idx<12 or headings:report['pdf_page_headers'].append({'page':idx+1,'first':lines[:7],'headings':headings})
with zipfile.ZipFile(root/'sedem-piesi.epub') as z:
    names=z.namelist();report['epub_files']=names[:150];report['epub_html']=[]
    for n in names:
        if n.lower().endswith(('.html','.xhtml','.htm')):
            raw=z.read(n)
            try:doc=etree.fromstring(raw,etree.XMLParser(recover=True))
            except Exception:continue
            heads=[]
            for node in doc.iter():
                tag=etree.QName(node).localname.lower() if isinstance(node.tag,str) else ''
                if tag in ('h1','h2','h3','h4','h5','nav'):
                    txt=' '.join(''.join(node.itertext()).split())
                    if txt and len(txt)<300:heads.append({'tag':tag,'text':txt[:180],'id':node.get('id')})
            txt=' '.join(''.join(doc.itertext()).split())[:200]
            report['epub_html'].append({'file':n,'bytes':len(raw),'headings':heads[:35],'head_count':len(heads),'intro':txt})
    for n in names:
        if n.endswith(('.opf','.ncx')):report['epub_'+n.split('/')[-1]]=z.read(n).decode('utf-8','replace')[:12000]

scene_re=re.compile(r'^(?:[Пп]ърва|[Вв]тора|[Тт]рета|[Чч]етвърта|[Пп]ета|[Шш]еста|[Сс]едма)\s+картина$|^(?:[Пп]ърво|[Вв]торо|[Тт]рето|[Чч]етвърто)\s+действ(?:ие|о)$|^ПРОЛОГ$|^ЕПИЛОГ$',re.I)
report['scene_candidates']=[]
for i,p in enumerate(book):
    for line in p.get_text(sort=True).splitlines():
        t=' '.join(line.split())
        if len(t)<70 and scene_re.match(t):report['scene_candidates'].append({'page':i+1,'text':t})
report['epub_scene_candidates']=[]
with zipfile.ZipFile(root/'sedem-piesi.epub') as z:
    doc=etree.fromstring(z.read('EPUB/text/ch002.xhtml'),etree.XMLParser(recover=True))
    for el in doc.iter():
        tag=etree.QName(el).localname.lower() if isinstance(el.tag,str) else ''
        if tag not in ('p','div','h2','h3'):continue
        if tag=='div' and list(el):continue
        txt=' '.join(''.join(el.itertext()).split())
        if len(txt)<75 and scene_re.match(txt):
            report['epub_scene_candidates'].append({'tag':tag,'text':txt,'id':el.get('id'),'class':el.get('class')})

Path('scripts/sedem_audit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('PDF PAGES',len(book),'EPUB HTML',len(report['epub_html']))
