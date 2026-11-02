#!/usr/bin/env python3
"""Sedem piesi: accessible v2 book production without changing original dramatic text."""
import io, re, sys, json, zipfile, hashlib, html
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from lxml import etree
import fitz

ROOT=Path('books/sedem-piesi')
SRC_PDF=ROOT/'sedem-piesi.pdf'
SRC_EPUB=ROOT/'sedem-piesi.epub'
FRONT=ROOT/'sedem-piesi-cover.jpg'
BACK=ROOT/'sedem-piesi-back-cover.jpg'
PDF_ISBN='978-619-94327-2-3'; EPUB_ISBN='978-619-94327-3-0'
PLAYS=[
 {'name':'Беба','year':'1999','page':5,'scenes':[]},
 {'name':'Жадувани от птиците','year':'1999','page':38,'scenes':[
  ('Пролог',40),('Първо действие',42),('Първа картина',42),('Втора картина',57),
  ('Трета картина',68),('Четвърта картина',79),('Пета картина',96),
  ('Второ действие · Шеста картина',108)]},
 {'name':'Всеки пет лета','year':'2000','page':164,'scenes':[('Първа картина',165),('Втора картина',201)]},
 {'name':'Глина','year':'2010','page':241,'scenes':[('Първо действие',242),('Второ действие',291)]},
 {'name':'Календи нула','year':'2013','page':322,'scenes':[]},
 {'name':'Като куче','year':'2013','page':366,'scenes':[]},
 {'name':'Спонтанно','year':'2013','page':406,'scenes':[]},
]
for i,p in enumerate(PLAYS,1):
 p['id']='play-'+str(i)
 p['scenes']=[{'title':title,'page':page,'id':f'play-{i}-part-{j}'} for j,(title,page) in enumerate(p['scenes'],1)]

# Stage divisions identified in the actual 2026 source PDF and EPUB.
def normalize(text):return ' '.join(text.split()).strip(' .\u00a0')
def is_target(text, scene):
 t=normalize(text).lower()
 name=scene['title'].lower()
 if t==name: return True
 if name=='първо действие':return (t=='п ъ р в о д е й с т в о' or t=='първо действо')
 if name=='второ действие · шеста картина':return (('шеста картина' in t and len(t)<95) or t=='второ действо')
 return False

def stage_spot_check(src):
 for i,p in enumerate(PLAYS):
  page=src[p['page']-1]
  s=normalize(page.get_text(sort=True))
  if p['name'].casefold() not in s.casefold():
   raise ValueError(f"Source PDF drama title missing on page {p['page']}: {p['name']}")

# Build a consistent, readable gold-on-cream, non-underlined TOC for fixed-layout PDF.
def font_path():
 for s in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
           '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf']:
  if Path(s).exists():return s
 raise RuntimeError('No Unicode font on Actions runner')

PALE=(0.974,0.964,0.935); NAVY=(0.11,0.15,0.19)
GOLD=(0.55,0.40,0.21); MUTED=(0.39,0.40,0.42)

def content_page(doc, sourcepage, groups, marker, n_toc_pages):
 w,h=sourcepage.rect.width,sourcepage.rect.height
 pg=doc.new_page(width=w,height=h)
 pg.draw_rect(pg.rect,color=None,fill=PALE)
 font='serifbg';pg.insert_font(fontname=font,fontfile=font_path())
 sc=min(w/545,h/760)
 margin=max(36,w*.105)
 pg.insert_text((margin,66*sc),'КРАСЕН КАМБУРОВ',fontsize=10*sc,fontname=font,color=GOLD)
 pg.insert_text((margin,112*sc),'СЪДЪРЖАНИЕ',fontsize=29*sc,fontname=font,color=NAVY)
 pg.draw_line((margin,134*sc),(w-margin,134*sc),color=GOLD,width=1.5)
 pg.insert_text((margin,154*sc),f'Седем пиеси  ·  {marker}',fontsize=11.5*sc,fontname=font,color=MUTED)
 y=192*sc
 expected=[]
 for play in groups:
  y+=10*sc
  label=play['name']
  pg.insert_text((margin,y),f"{int(play['id'].split('-')[1]):02d}   {label}",fontsize=14*sc,fontname=font,color=NAVY)
  num=play['page']+n_toc_pages-1
  pg.insert_text((w-margin-35*sc,y),str(num),fontsize=11*sc,fontname=font,color=GOLD)
  rect=fitz.Rect(margin-3,y-17*sc,w-margin,y+8*sc)
  expected.append((rect,num-1,label))
  y+=23*sc
  for x in play['scenes']:
   txt='•  '+x['title']
   pg.insert_text((margin+31*sc,y),txt,fontsize=10.7*sc,fontname=font,color=MUTED)
   num=x['page']+n_toc_pages-1
   pg.insert_text((w-margin-35*sc,y),str(num),fontsize=10.5*sc,fontname=font,color=GOLD)
   rect=fitz.Rect(margin+27*sc,y-13*sc,w-margin,y+6*sc)
   expected.append((rect,num-1,txt))
   y+=20*sc
  y+=10*sc
 footer=h-36*sc
 if y>footer-5*sc:raise ValueError(f"TOC content does not fit: {y} > {footer}")
 pg.draw_line((margin,footer-20*sc),(w-margin,footer-20*sc),color=GOLD,width=.6)
 pg.insert_text((margin,footer),f'PDF ISBN {PDF_ISBN}',fontsize=8*sc,fontname=font,color=MUTED)
 return pg,expected

def make_pdf():
 source=fitz.open(SRC_PDF)
 stage_spot_check(source)
 old_pages=len(source)
 if old_pages<400:raise ValueError('Unexpected source PDF length')
 old_body_hash=hashlib.sha256('\n'.join(source[i].get_text() for i in range(4,old_pages)).encode()).hexdigest()
 dst=fitz.open();rect=source[1].rect
 cover=dst.new_page(width=rect.width,height=rect.height)
 cover.insert_image(cover.rect,filename=str(FRONT),keep_proportion=False)
 dst.insert_pdf(source,from_page=1,to_page=2)
 K=2
 linkplans=[]
 for groups,marker in ((PLAYS[:4],'I–IV'),(PLAYS[4:],'V–VII')):
  page,links=content_page(dst,source[1],groups,marker,K)
  linkplans.append((page.number,links))
 dst.insert_pdf(source,from_page=4,to_page=old_pages-1,links=False,annots=True)
 back=dst.new_page(width=rect.width,height=rect.height)
 back.insert_image(back.rect,filename=str(BACK),keep_proportion=False)
 for idx,links in linkplans:
  page=dst[idx]
  for rect,target,label in links:
   if target<0 or target>=len(dst):raise ValueError(f"Invalid PDF link {label}: {target}")
   page.insert_link({'kind':fitz.LINK_GOTO,'from':rect,'page':target})
 toc=[[1,'СЕДЕМ ПИЕСИ',1],[1,'Съдържание',4]]
 for p in PLAYS:
  toc.append([1,p['name'],p['page']+K-1])
  toc.extend([[2,s['title'],s['page']+K-1] for s in p['scenes']])
 toc.append([1,'Задна корица',len(dst)])
 dst.set_toc(toc)
 dst.set_metadata({'title':'Седем пиеси — Красен Камбуров','author':'Красен Камбуров',
    'subject':'Драматургия, второ издание, София 2026','keywords':PDF_ISBN})
 newhash=hashlib.sha256('\n'.join(dst[i].get_text() for i in range(5,len(dst)-1)).encode()).hexdigest()
 if old_body_hash!=newhash:raise ValueError('Original drama text was changed in PDF')
 outfile=ROOT/'sedem-piesi-v2.pdf'
 dst.save(outfile,garbage=4,deflate=True)
 check=fitz.open(outfile)
 assert len(check)==old_pages+2
 actual_links=sum(len(check[i].get_links()) for i in (3,4))
 assert actual_links>=len(PLAYS)+sum(len(p['scenes']) for p in PLAYS)
 report={'source_pages':old_pages,'new_pages':len(check),'body_text_sha256':newhash,'bookmarks':len(check.get_toc()),'toc_links':actual_links,'size_bytes':outfile.stat().st_size}
 print('PDF_CHECK',json.dumps(report,ensure_ascii=False))
 check.close();dst.close();source.close()
 return report

XHTML='http://www.w3.org/1999/xhtml'
EPUBNS='http://www.idpf.org/2007/ops'
OPF='http://www.idpf.org/2007/opf'

def e(name):return etree.Element('{'+XHTML+'}'+name)
def add(parent,name,txt=None,**kwargs):
 el=etree.SubElement(parent,'{'+XHTML+'}'+name,**kwargs)
 if txt is not None:el.text=txt
 return el

def make_nav():
 htmlroot=etree.Element('{'+XHTML+'}html',nsmap={None:XHTML,'epub':EPUBNS})
 htmlroot.set('{http://www.w3.org/XML/1998/namespace}lang','bg')
 h=add(htmlroot,'head');add(h,'title','Седем пиеси — съдържание')
 style=add(h,'style');style.text='''body{background:#151c20;color:#f1e5ce;font-family:Georgia,serif;line-height:1.65;padding:1em}h1{color:#eac982;font-size:1.8em}h2{color:#eac982;font-size:1.25em;border-bottom:1px solid #776341;padding:.4em 0}ol{padding-left:1.45em}li{margin:.6em 0}ol ol{margin:.3em 0 1.2em}a,a:visited{color:#e5c782;text-decoration:none;border:0}a:focus,a:hover{color:#fff0b4;text-decoration:none}small{color:#c6c2b9}'''
 body=add(htmlroot,'body');nav=add(body,'nav',id='toc')
 nav.set('{'+EPUBNS+'}type','toc');add(nav,'h1','Съдържание')
 ol=add(nav,'ol')
 for p in PLAYS:
  li=add(ol,'li');a=add(li,'a',p['name']);a.set('href','text/ch002.xhtml#'+p['id'])
  subs=[x for x in p['scenes'] if x.get('anchored')]
  if subs:
   ul=add(li,'ol')
   for sub in subs:
    sli=add(ul,'li');a=add(sli,'a',sub['title']);a.set('href','text/ch002.xhtml#'+sub['id'])
 nav2=add(body,'nav',id='landmarks');nav2.set('{'+EPUBNS+'}type','landmarks')
 ol2=add(nav2,'ol');li=add(ol2,'li');a=add(li,'a','Корица');a.set('href','text/cover.xhtml');a.set('{'+EPUBNS+'}type','cover')
 return etree.tostring(htmlroot,encoding='utf-8',xml_declaration=True)

def make_ncx():
 ns='http://www.daisy.org/z3986/2005/ncx/'
 q=lambda n:'{'+ns+'}'+n
 root=etree.Element(q('ncx'),nsmap={None:ns},version='2005-1')
 head=etree.SubElement(root,q('head'));etree.SubElement(head,q('meta'),name='dtb:uid',content=EPUB_ISBN)
 title=etree.SubElement(root,q('docTitle'));etree.SubElement(title,q('text')).text='Седем пиеси'
 navmap=etree.SubElement(root,q('navMap'));order=0
 def item(parent,label,target):
  nonlocal order
  order+=1
  node=etree.SubElement(parent,q('navPoint'),id='point'+str(order),playOrder=str(order))
  nl=etree.SubElement(node,q('navLabel'));etree.SubElement(nl,q('text')).text=label
  etree.SubElement(node,q('content'),src=target)
  return node
 for p in PLAYS:
  parent=item(navmap,p['name'],'text/ch002.xhtml#'+p['id'])
  for s in p['scenes']:
   if s.get('anchored'):item(parent,s['title'],'text/ch002.xhtml#'+s['id'])
 return etree.tostring(root,encoding='utf-8',xml_declaration=True)

def make_back_xhtml():
 root=etree.Element('{'+XHTML+'}html',nsmap={None:XHTML})
 root.set('{http://www.w3.org/XML/1998/namespace}lang','bg')
 head=add(root,'head');add(head,'title','Задна корица — Седем пиеси')
 style=add(head,'style');style.text='body{margin:0;padding:0;text-align:center;background:#101820;color:#f2e7d4}img{max-width:100%;height:auto;display:block;margin:auto}p{font:1em Georgia,serif;margin:1em}'
 b=add(root,'body');im=add(b,'img');im.set('src','../media/sedem-piesi-back-cover.jpg');im.set('alt','Задна корица на Седем пиеси: седем драматургични творби, от Беба до Спонтанно, ISBN за PDF и EPUB')
 return etree.tostring(root,xml_declaration=True,encoding='utf-8')

def make_epub():
 out=ROOT/'sedem-piesi-v2.epub'
 with zipfile.ZipFile(SRC_EPUB,'r') as zi:
  raw={n:zi.read(n) for n in zi.namelist()}
  orig_text=etree.fromstring(raw['EPUB/text/ch002.xhtml'],etree.XMLParser(recover=True))
  text_before=list(orig_text.itertext())
  chapter=orig_text
  current=None;ids={}
  for el in chapter.iter():
   if not isinstance(el.tag,str):continue
   tag=etree.QName(el).localname.lower()
   text=normalize(''.join(el.itertext()))
   if tag=='h1':
    target=next((p for p in PLAYS if normalize(p['name'])==text),None)
    if target:
     current=target;el.set('id',target['id']);ids[target['id']]=True
   elif tag in ('p','h2','h3') and current and len(text)<96:
    for scene in current['scenes']:
     if scene['id'] not in ids and is_target(text,scene):
      el.set('id',scene['id']);scene['anchored']=True;ids[scene['id']]=True;break
  assert all(ids.get(p['id']) for p in PLAYS)
  text_after=list(chapter.itertext())
  if text_before!=text_after:raise ValueError('EPUB body text changed during navigation setup')
  # No anchor links to missing scene headings; page-based web/PDF TOC can still cover them.
  raw['EPUB/text/ch002.xhtml']=etree.tostring(chapter,encoding='utf-8',xml_declaration=True)
  raw['EPUB/nav.xhtml']=make_nav()
  raw['EPUB/toc.ncx']=make_ncx()
  raw['EPUB/media/sedem-piesi-ebook-cover-front-only.jpg']=FRONT.read_bytes()
  raw['EPUB/media/sedem-piesi-back-cover.jpg']=BACK.read_bytes()
  raw['EPUB/text/back-cover.xhtml']=make_back_xhtml()
  doc=etree.fromstring(raw['EPUB/content.opf'],etree.XMLParser(recover=True))
  manifest=doc.find('{'+OPF+'}manifest');spine=doc.find('{'+OPF+'}spine')
  assert manifest is not None and spine is not None
  etree.SubElement(manifest,'{'+OPF+'}item',id='back-cover-image',href='media/sedem-piesi-back-cover.jpg',**{'media-type':'image/jpeg'})
  etree.SubElement(manifest,'{'+OPF+'}item',id='back-cover-xhtml',href='text/back-cover.xhtml',**{'media-type':'application/xhtml+xml'})
  etree.SubElement(spine,'{'+OPF+'}itemref',idref='back-cover-xhtml')
  raw['EPUB/content.opf']=etree.tostring(doc,encoding='utf-8',xml_declaration=True)
  with zipfile.ZipFile(out,'w') as zo:
   zo.writestr('mimetype',raw['mimetype'],compress_type=zipfile.ZIP_STORED)
   for n in zi.namelist():
    if n=='mimetype':continue
    zo.writestr(n,raw[n],compress_type=zipfile.ZIP_DEFLATED)
   for n in ['EPUB/media/sedem-piesi-back-cover.jpg','EPUB/text/back-cover.xhtml']:
    zo.writestr(n,raw[n],compress_type=zipfile.ZIP_DEFLATED)
 with zipfile.ZipFile(out,'r') as za:
  assert za.testzip() is None
  assert za.namelist()[0]=='mimetype'
  x=etree.fromstring(za.read('EPUB/text/ch002.xhtml'))
  assert list(x.itertext())==text_before
  actual_ids={el.get('id') for el in x.iter() if isinstance(el.tag,str) and el.get('id')}
  nav=etree.fromstring(za.read('EPUB/nav.xhtml'))
  targets=[a.get('href').split('#')[-1] for a in nav.xpath('//*[local-name()="a"]') if '#' in a.get('href','')]
  if not all(id in actual_ids for id in targets):raise ValueError('Broken internal links in EPUB navigation')
  assert len([p for p in PLAYS if p['id'] in actual_ids])==7
 report={'epub_size_bytes':out.stat().st_size,'plays':len(PLAYS),'anchored_scenes':sum(x.get('anchored',False) for p in PLAYS for x in p['scenes']),
  'nonanchored_scenes':[x['title']+' ('+p['name']+')' for p in PLAYS for x in p['scenes'] if not x.get('anchored')],
  'epub_internal_links':len(targets),'original_text_preserved':True}
 print('EPUB_CHECK',json.dumps(report,ensure_ascii=False));return report

# Web accessible accordion (similar to Saborna kniga).
def make_web_toc(n_toc_pages=2):
 css='''<style>.toc-wrap{max-width:960px;margin:auto;padding:38px 20px 80px}.toc-wrap h1{font-size:clamp(2.15rem,5vw,3.5rem);margin-bottom:1rem}.toc-wrap .intro{max-width:70ch;color:#c7c1b2;line-height:1.7}.toc-tools{display:flex;gap:.75rem;flex-wrap:wrap;margin:1.5rem 0 2rem}.toc-book{border:1px solid #3e423a;border-radius:3px;margin:1rem 0;background:#151b17}.toc-book summary{list-style:none;cursor:pointer;color:#e8ce90;padding:1.1rem 1.2rem;font-size:1.2rem;font-family:Georgia,serif}.toc-book summary::-webkit-details-marker{display:none}.toc-book summary::after{content:'+';float:right;font-family:sans-serif}.toc-book[open] summary::after{content:'−'}.toc-book ol{margin:0;padding:0 1.35rem 1.2rem 2.7rem}.toc-book li{padding:.42rem 0;color:#bdb8a8;border-bottom:1px solid #29312b}.toc-book a,.toc-book a:visited{color:#e4d1a4;text-decoration:none;border:0}.toc-book a:hover,.toc-book a:focus{color:#fff0ba;text-decoration:none}.toc-book small{float:right;color:#b2afa7;font-size:.8em}.toc-wrap .toc-tools a{color:#ebd5a1;text-decoration:none;border:1px solid #6d634c;padding:.7rem 1rem}.toc-wrap .toc-tools a:hover{background:#2b3028;color:#fff}.toc-book a:focus-visible{outline:2px solid #e6c786;outline-offset:3px}</style>'''
 page=['<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
  '<title>Съдържание — Седем пиеси, Красен Камбуров</title>',
  '<meta name="description" content="Пълно кликаемо съдържание на Седем пиеси: седем пиеси и техните действия и картини.">',
  '<link rel="stylesheet" href="../../assets/site.css">',css,'</head><body data-page="book"><a class="skip" href="#main">Към съдържанието</a>',
  '<header class="site-header"><div class="wrap nav"><a class="brand" href="../../">Красен Камбуров<span>Литературен свят · книги и автор</span></a><nav class="navlinks" aria-label="Основна навигация"><a href="../../#works">Книги</a><a href="../sedem-piesi/">Книгата</a></nav></div></header>',
  '<main id="main" class="toc-wrap"><p class="eyebrow">Седем драматургични произведения</p><h1>Пълно съдържание</h1>',
  '<p class="intro">Разгънете пиесата, за да отворите съответното действие или картина в PDF изданието. В EPUB съдържанието е достъпно и от менюто на електронния четец.</p>',
  '<div class="toc-tools"><a href="sedem-piesi.pdf">PDF издание</a><a href="sedem-piesi.epub">EPUB издание</a><a href="./">Към книгата</a></div>']
 for i,p in enumerate(PLAYS,1):
  n=p['page']+n_toc_pages-1
  page.append('<details class="toc-book"'+(' open' if i==1 else '')+'><summary>'+f'{i:02d} · '+html.escape(p['name'])+'</summary><ol>')
  page.append(f'<li><a href="sedem-piesi.pdf#page={n}" title="Отвори на страница {n}">Начало на пиесата</a><small>стр. {n}</small></li>')
  for x in p['scenes']:
   idx=x['page']+n_toc_pages-1
   page.append(f'<li><a href="sedem-piesi.pdf#page={idx}" title="Отвори на страница {idx}">{html.escape(x["title"])}</a><small>стр. {idx}</small></li>')
  page.append('</ol></details>')
 page.extend([f'<p class="intro">PDF ISBN {PDF_ISBN} · EPUB ISBN {EPUB_ISBN}</p>','</main><footer class="footer"><div class="wrap">© Красен Камбуров · 2026</div></footer></body></html>'])
 target=ROOT/'sadarzhanie.html';target.write_text('\n'.join(page),encoding='utf8')
 return {'size_bytes':target.stat().st_size,'group_count':len(PLAYS),'links':sum(len(p['scenes'])+1 for p in PLAYS)}

if __name__=='__main__':
 required=[SRC_PDF,SRC_EPUB,FRONT,BACK]
 if not all(x.exists() for x in required):raise SystemExit('Missing sources: '+repr([str(x) for x in required if not x.exists()]))
 report={'pdf':make_pdf(),'epub':make_epub(),'web_toc':make_web_toc()}
 Path('scripts/sedem_v2_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 print('SEDEN_V2_SUCCESS',json.dumps(report,ensure_ascii=False))
