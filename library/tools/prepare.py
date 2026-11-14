"""Turns an export of the catalogue sheet into library/data/library.json.

Usage: python3 library/tools/prepare.py catalogue.json links.json library/data/library.json

catalogue.json is an export of the catalogue sheet (one list of rows per tab). It holds working
notes, so it is deliberately NOT kept in this repository. links.json is the output of a link check.
Only entries whose link loaded, and whose sheet status is not "Needs checking" or "To source",
are published.
"""
import json,re,sys,collections
c=json.load(open(sys.argv[1])); L=json.load(open(sys.argv[2]))
import os
DATA_DIR=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'data')
SUM=json.load(open(os.path.join(DATA_DIR,'summaries.json')))
DEAD={'https://www.edresearch.edu.au/resources/explicit-instruction-english','https://www.edresearch.edu.au/guides-resources/videos/teaching-how-students-learn-teach-explicitly'}
def rows(s):
    h=c[s][0]; return [dict(zip(h,r+[None]*(len(h)-len(r)))) for r in c[s][1:]]
def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def ok(u,status=None):
    if not u or u in DEAD or u not in L or L[u]['status']!='ok': return False
    return status not in ('Needs checking','To source')
# ---- areas
areas=[]; byname={}
for r in rows('Framework'):
    if not r['Area'] or not re.match(r'\d+\. ',r['Area'] or ''): continue
    n,name=r['Area'].split('. ',1); short=name
    a={'n':int(n),'name':name,'slug':slug(name.split(':')[0] if ':' in name else name),'domain':r['Domain'].split('. ',1)[1],
       'about':r['What people need to know'],'practices':[p.strip() for p in (r['Example practices (full list on the Practices tab)'] or '').split(';') if p.strip()]}
    areas.append(a); byname[name.lower()]=int(n)
def nums(s):
    return [int(x) for x in re.findall(r'\d+',str(s or ''))][:4]
def area_from_name(s):
    m=re.match(r'(\d+)\.',str(s or '')); return [int(m.group(1))] if m else []
ART={'All teaching practice areas':[2,4,23],'Change management':[22],'Daily review':[3],'Early reading':[7],'Evidence, myths and debates':[18],'Explicit instruction':[2],'Hinge questions':[4],'How learning happens':[1],'Implementation':[17],'Instructional coaching':[16],'Knowledge and writing':[10,6],'Leadership and culture':[19,20],'Maths':[12],'Parent communication':[20],'Participation and opportunities to respond':[23],'Phonics F-2':[7],'Questioning':[4],'Reading':[8],'Reading and writing 3-6':[8,10],'Retrieval, spacing and review':[3],'Spelling 3-6':[9],'Spelling, morphology and handwriting':[9],'System policy':[],'Text studies':[8],'Writing':[10]}
TECH={}
for r in rows('Practices'):
    n=int(r['Area'].split('.')[0]); TECH[r['Practice'].lower()]=n
    for a in re.split(r'[;,]',r['Also called'] or ''):
        if a.strip(): TECH.setdefault(a.strip().lower(),n)
EXTRA={'routines':5,'checking for understanding':4,'i do / we do / you do':2,'full phonics lesson':7,'feedback':24,'vocabulary':8,'participation':23,'success rate':24,'tiered support':14,'active participation':23,'full lesson':2,'coaching':16,'think aloud':2,'learning objectives':2,'error correction':4,'blending':7,'attention signals':5,'writing':10,'scripted explanation':2,'retrieval':3,'monitoring':4,'teacher presence':5,'economy of language':5,'mastery':24,'how learning happens':1,'implementation':17,'leadership':19,'knowledge-rich teaching':6,'success criteria':2,'prior knowledge':1,'scaffold practice':2,'revisit and review':3,'vary practice':24,'organise knowledge':1,'classroom routines':5,'response systems':23,'coaching tool':16,'engagement':23,'spelling rules':9,'word chaining':7,'whole-class teaching':2,'thinking ratio':23,'scaffolding':2,'fading':2,'knowledge organisation':6,'application':24,'entry':5,'exit':5,'behaviour':20,'relationships':20,'circulation':4,'scanning':5,'praise':5,'positive framing':5,'start of year':5,'pl cycles':16,'teacher talk':2,'intervention':14,'one-to-one teaching':14,'drop-ins':16,'coherence':6,'phonics routines':7,'lesson starts':5,'high expectations':20,'culture':20,'entry routines':5,'micro-scaffolding':2,'modelling':2,'explicit teaching overview':2}
SUBJ={'Maths':[12],'Writing':[10],'Phonics':[7],'Reading':[8],'Vocabulary':[8],'Spelling':[9],'Oral language':[11]}
E=[]; held=collections.Counter(); seen=set()
def add(t,title,url,by='',meta=None,areas_=None,tags=None,status=None,sheet='',**extra):
    if not ok(url,status): held[sheet]+=1; return
    k=(t,url,title.lower()[:40])
    if k in seen: return
    seen.add(k)
    a=[]
    for x in areas_ or []:
        if x not in a and 1<=x<=24: a.append(x)
    E.append({'type':t,'title':title.strip(),'url':url,'by':(by or '').strip(),'meta':[m for m in (meta or []) if m],'areas':a[:3],'tags':[x for x in (tags or []) if x],**{k:v for k,v in extra.items() if v}})
def years(y):
    y=str(y or '')
    return '' if (not y or 'heck' in y or y in ('All','All staff','Leaders')) else y
KW=[(r'phonic|decod|blending',7),(r'fluen|comprehension|vocabular|shared reading|echo reading|paired reading|repeated reading',8),(r'spell|suffix|handwrit|transcription|letter formation',9),(r'writ',10),(r'\btalk\b|oral language|dialogue|oracy',11),(r'math|number facts|fraction|multiplic|division|manipulative|bar model',12),(r'retriev|daily review|revisit and review',3),(r'check(ing)? (for |pupils. )?understanding|diagnostic question|mini.?white|cold call|formative|monitor progress|check, adapt',4),(r'turn and talk|participation|ratio|choral|response system',23),(r'feedback|mastery',24),(r'routine|classroom management|behaviour|attention|entering|exiting',5),(r'coach',16),(r'implement',17),(r'mtss|intervention|tiered|send\b|special educational|teaching assistant',14),(r'explicit|worked example|model(l)?ing|modelled|think aloud|scaffold|learning objectives',2),(r'how students learn|learning process|cognitive load|prior knowledge',1),(r'leader|leading',19)]
def band(y):
    y=str(y or '')
    if re.search(r'F-2|K-2|K-3|Foundation|Year 1\b|Year 2|Early|Reception|Years 1-4',y): return ['F-2']
    if re.search(r'Year 3|Year 4|Year 5|Year 6|3-6|Upper primary',y): return ['3-6']
    if re.search(r'Primary and secondary|F-10|F-12|K-12|K-8',y): return ['F-2','3-6','Secondary']
    if re.search(r'Primary|K-5|K-6|Years 1-6',y): return ['F-2','3-6']
    if re.search(r'Secondary|7-12|Middle',y): return ['Secondary']
    return []
def subj(s):
    s=str(s or '')
    if s=='Maths': return 'Maths'
    if s in ('Phonics','Reading','Writing','Vocabulary','Spelling','Literacy','English','Oral language'): return 'Literacy and English'
    if s in ('Mixed','Literacy and numeracy'): return 'Across subjects'
    return 'Other subjects'
for r in rows('Videos'):
    a=[]; text=(r['Title']+' '+SUM.get(r['Link'],'')).lower()
    for pat,n in KW:
        if re.search(pat,text) and n not in a: a.append(n)
    a+=list(SUBJ.get(r['Subject'],[]))
    for t in re.split(r';',r['Techniques'] or ''):
        n=TECH.get(t.strip().lower()) or EXTRA.get(t.strip().lower())
        if n: a.append(n)
    u=r['Link']; title=r['Title']; src=r['Source'] or ''
    acc=r['Access'] or ''
    add('watch',title,u,src.replace(' (YouTube)',''),[r['Length'] and str(r['Length']),years(r['Years']),r['Region']],a,['Free' if acc.startswith('Free') else 'Check cost'],r['Status'],'Videos',summary=SUM.get(u),bands=band(r['Years']),subject=subj(r['Subject']),region=r['Region'])
for r in rows('Episodes'):
    add('listen',r['Episode'],r['Link'],r['Show'],[('with '+r['Guest']) if r['Guest'] else '',r['Subject']],nums(r['Area']),['Free'],r['Status'],'Episodes')
for r in rows('Vic practice map'):
    add('listen',r['Episode'],r['Link'],r['Show'],[('with '+r['Guest']) if r['Guest'] else ''],[],['Free'],r['Status'],'Vic practice map')
shows=[]
for r in rows('Podcasts'):
    if ok(r['Link'],r['Status']) and 'third-party' not in (r['Notes'] or '') and 'Link is' not in (r['Notes'] or ''):
        shows.append({'title':r['Show'],'by':r['Hosts'],'url':r['Link'],'meta':[r['Subject'],r['Region']]})
    else: held['Podcasts']+=1
for r in rows('Articles'):
    title=re.sub(r'\s*\((?:[A-Z][A-Za-z ,&]+,? )?\d{4}\)$','',r['Title'])
    add('read',r['Title'],r['Link'],r['Source'],[r['Type'],r['Region']],ART.get(r['Area'],[]),[],r['Status'],'Articles')
for r in rows('Foundations'):
    layer=(r['Layer'] or '')[:1]
    add('research' if layer=='C' else 'read',r['Title'],r['Link'],r['Authors'],[str(r['Year']) if r['Year'] else '', 'Foundational research' if layer=='C' else (r['Layer'] or '')[3:]],area_from_name(r['Area']),['Foundational'] if layer=='C' else [],r['Status'],'Foundations')
for r in rows('Research'):
    add('research',r['Title'],r['Link'],r['Authors'] if r['Authors']!='Not confirmed' else '',[str(r['Year']) if r['Year'] else '',r['Type']],area_from_name(r['Area']),[],r['Status'],'Research')
for r in rows('Voices'):
    add('voice',r['Name'],r['Link'],'',[r['Format'],r['Region']],nums(r['Areas']) if 'All' not in str(r['Areas']) else [],[],r['Status'],'Voices')
CUR={'Phonics':[7],'Maths':[12],'grammar':[10],'Reading':[8]}
for r in rows('Curriculum'):
    a=[]
    for k,v in CUR.items():
        if k in (r['Subjects'] or '') and ',' not in (r['Subjects'] or '').replace('Phonics, spelling','x'): a+=v
    add('curriculum',r['Name'],r['Link'],'',[r['Subjects'],years(r['Years']),r['Alignment']],a,[r['Cost']],r['Status'],'Curriculum')
# dedupe listen entries by url (Episodes tab first, then Vic map extras)
out=[];urls=set()
for e in E:
    if e['type']=='listen':
        if e['url'] in urls: continue
        urls.add(e['url'])
    out.append(e)
E=out
# VTLM view
V=collections.OrderedDict()
for r in rows('Vic practice map'):
    if not ok(r['Link'],r['Status']): continue
    V.setdefault(r['Victorian frame'],collections.OrderedDict()).setdefault(r['Element or priority'],[]).append({'title':r['Episode'],'by':r['Show'],'guest':r['Guest'] or '','focus':r['Practice focus'],'url':r['Link']})
# episodes from Vic map inherit areas where element maps cleanly
VA={'Phonics and early reading':[7],'Reading in Years 3 to 6':[8],'Spelling and morphology':[9],'Writing':[10],'Oral language':[11],'Mathematics':[12],'Assessment and data':[13],'MTSS and inclusion':[14],'Coaching and professional learning':[16],'Leadership and culture':[19],'Implementation':[17],'Retention and recall':[3],'Knowledge and memory':[1],'Attention, focus and regulation':[5],'Planning':[6],'Enabling learning':[5],'Explicit teaching: overview':[2],'Explicit teaching: focus the learning':[2],'Explicit teaching: explicit explanation and modelling':[2],'Explicit teaching: scaffold practice':[23],'Explicit teaching: monitor progress':[4],'Supported application':[24],'Mastery and application':[24]}
u2a={}
for r in rows('Vic practice map'): u2a.setdefault(r['Link'],[]).extend(VA.get(r['Element or priority'],[]))
for e in E:
    if e['type']=='listen' and not e['areas']: e['areas']=list(dict.fromkeys(u2a.get(e['url'],[])))[:3]
focus={}
for r in rows('Vic practice map'): focus.setdefault(r['Link'],r['Practice focus'])
for r in rows('Episodes'):
    if r['Practice']: focus[r['Link']]=r['Practice']
for e in E:
    if e['type']=='listen' and focus.get(e['url']): e['focus']=focus[e['url']]
JM={'title':'Jones & McLean','by':'Bron Ryrie Jones and Emina McLean','url':'https://jonesandmclean.podbean.com/','meta':['General teaching','Australia']}
shows=[JM]+shows
have={x['title'] for x in shows}
EXTRA_SHOWS=[{'title':'Sold a Story','by':'Emily Hanford, APM Reports','url':'https://features.apmreports.org/sold-a-story/','meta':['Reading and phonics','USA'],'note':'Seasons 1 and 2'},
 {'title':'Progressively Incorrect','by':'Zach Groshell','url':'https://educationrickshaw.com/podcast/','meta':['General teaching','USA']},
 {'title':'Science of Reading: The Podcast','by':'Amplify','url':'https://amplify.com/science-of-reading-the-podcast/','meta':['Reading and phonics','USA']}]
for x in EXTRA_SHOWS:
    if x['title'] in have: shows=[x if y['title']==x['title'] else y for y in shows]
    else: shows.append(x)
# Left out: The Art of Teaching, Schoolin' Around and Teacher Takeaway (removed November 2026: not aligned with the
# science of learning and science of reading focus of the library).
shows=[x for x in shows if x['title'] not in ('The Art of Teaching',"Schoolin' Around",'Teacher Takeaway')]
ART=json.load(open(os.path.join(DATA_DIR,'shows.json')))
ALIAS={'Mind the Gap: Making Education Work Across the Globe':'Mind the Gap'}
for x in shows:
    a=ART.get(ALIAS.get(x['title'],x['title']))
    if a: x.update(a)
    if x.get('by_override'): x['by']=x.pop('by_override')
    if x['title']=='Triple R Teaching': x['title']='Reach All Readers (formerly Triple R Teaching)'
json.dump({'areas':areas,'entries':E,'shows':shows,'vtlm':V},open(sys.argv[3],'w'),ensure_ascii=False,indent=1)
cnt=collections.Counter(e['type'] for e in E); print('published',dict(cnt),'total',len(E),'shows',len(shows)); print('held back',dict(held))
ac=collections.Counter(a for e in E for a in e['areas']); print('per area',sorted(ac.items())); print('no area',collections.Counter(e['type'] for e in E if not e['areas']))
