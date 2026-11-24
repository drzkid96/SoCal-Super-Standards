"""Give each indexed item a qualitative reading note and a precise source destination."""
from collections import defaultdict
from functools import lru_cache
from html import escape, unescape
from pathlib import Path
import re

from current_catalog import BASE, PUBLIC, read, save
from manual_art import SHEET_COUNTS, ART, source

# What a designer is looking for in each drawing family. Match the most specific use first.
READING = [
 (r'height.*lateral location|sign installations','Compare the mounting height and lateral offset against the roadside setting. The diagrams show which reference points the dimensions are measured from.'),
 (r'interchange numbering|exit numbering','Trace the numbered exits along the mainline. Where routes overlap or split, compare the numbering sequence for each branch.'),
 (r'interchange|exit direction|exit only|entrance ramp|exit ramp|frontage road','Follow a driver from the upstream decision point through the ramp. The ordering of the diagrammed signs identifies when the driver receives lane and destination information.'),
 (r'interim approval|process for|experimentations','Follow the decision points and identify the agency responsible at each step. The diagram distinguishes applying for approval from using a device after approval.'),
 (r'keep right|keep left|merge and added lane','Trace the paths on either side of the device. Compare a lane that continues downstream with one that requires a merge.'),
 (r'pull.out|bus lane|bus.bike|boarding','Locate the boarding edge and trace the bus path as it approaches and leaves the stop.'),
 (r'chicane|diverter|road diet|bulbout','Follow the movements that the layout preserves, redirects or restricts. Look at how the curb position or lane allocation changes the path through the treatment.'),
 (r'parklet|outdoor dining|street tree|stormwater','Locate the feature within the street cross section and trace pedestrian access around it. The frontage and curb edges show where it fits relative to other uses.'),
 (r'illumina|lighting|photometric','Identify the area to be lit and its relationship to the pole or fixture. The drawing or table distinguishes placement from performance.'),
 (r'plan sheet|line weight|linetype|drafting|sheet format','Compare the graphic conventions with the marks on the plan. Line weight, linework and sheet organization communicate different parts of the design.'),
 (r'left.turn|right.turn|turn lane|turn pocket','Follow the turning vehicle from its approach lane to its receiving lane. The detail identifies where the turn separates from, or crosses, other movements.'),
 (r'sign placement|guide signing|signing for|guide sign|pictograph|sign panels|distance sign|sign spreading|sign use','Read the sign sequence from the driver’s approach toward the decision point. Identify the location and movement associated with each message.'),
 (r'warrant.*volume|volume.*warrant|peak hour.*warrant','The chart or table relates measured demand to the warrant named in its heading. Check the time period and any adjustment factor before comparing the major- and minor-street counts.'),
 (r'pedestrian hybrid beacon.*speed|installation of pedestrian hybrid','The plotted relationship is specific to the roadway speed range in the figure title. Locate the crossing demand and traffic volume on the matching chart.'),
 (r'push.?button|accessible pedestrian signal','Look at where a person waiting to cross can find and reach the control and identify the crossing it serves.'),
 (r'sequence|interval|phasing','Read the indications in time order and follow the movements that receive each display.'),
 (r'bike box|bicycle box|two.stage.*turn','Follow the bicycle approach into the waiting area and then trace the movement that leaves it. The position of the box explains how it relates to other traffic at the intersection.'),
 (r'separated bike|separated bicycle|separated bikeway|protected bike|class iv','Look for the space separating riders from moving vehicles and follow how that separation changes at crossings or driveways.'),
 (r'shared.use path|class i\b|bike path','Follow the path independently of the motor-vehicle lanes, paying particular attention to connections and crossings.'),
 (r'buffer.*bike|buffer.*bicycle|bike lane buffer','Read the buffer separately from the bicycle travel area. The drawing distinguishes stripes and hatching from any physical separator.'),
 (r'wayfinding|destination|guide signs|directional sign','Read the messages in the order a traveler would encounter them. Compare destination names, arrows and route information with the decision point on the approach.'),
 (r'shared lane|sharrow|bike route|class iii','The route uses roadway space shared with motor vehicles. Look at how the device guides riders or alerts drivers along that shared alignment.'),
 (r'bike lane|bicycle lane|bikeway|bicycl','Follow the rider through the depicted facility and identify where the design changes their position relative to other street users.'),
 (r'speed cushion','Look for the gaps between raised sections and how they line up with vehicle wheel paths. This distinguishes a cushion from a continuous hump.'),
 (r'speed table|raised crosswalk','The profile shows the transition from the roadway onto the raised area. Where the treatment carries a crossing, trace the pedestrian route across the top.'),
 (r'speed hump','Read the plan together with the profile to see the footprint and the change in elevation in the direction of travel.'),
 (r'curb extension|bulb.out|bus bulb','Follow the curb where it extends into the street and returns to the original curb line. Compare the space for people at the curb with the path of a passing or turning vehicle.'),
 (r'curb ramp|detectable warning|landing slope','Follow the accessible route from the sidewalk toward the crossing. The arrangement of the landing, slope transitions and street edge distinguishes the configurations.'),
 (r'island|pedestrian refuge|median','Read the outline of the island or median against the adjacent travel paths. Look at how each approach aligns with the opening or nose.'),
 (r'roundabout|traffic circle','Trace the approach, circulation around the center, and exit. Approach geometry and the way the center is treated help distinguish the layout shown.'),
 (r'bus stop|boarding|bus.bike|transit stop','Trace the passenger path between the sidewalk and the vehicle alongside any bicycle or motor-vehicle movements.'),
 (r'crosswalk|pedestrian crossing|marked crossing','Follow the pedestrian crossing line across each approach and compare it with the path of approaching vehicles.'),
 (r'flagger|pilot car','Follow the sequence of control points along the work area and identify which direction of travel each point serves.'),
 (r'closure|detour|diversion|temporary traffic control|work zone|work space|typical application','Read the arrangement from the first advance warning through the work area to the return to normal travel. The position of the activity and the route that stays open distinguish this application.'),
 (r'grade crossing|railroad|light rail|rail transit','Follow the roadway or pedestrian approach toward the tracks. The relationship between the crossing and the warning or control devices is the central feature.'),
 (r'parking stall|accessible parking|parking space','Read the stall, adjoining aisle and access path as a single layout. Their relationship determines how a person can move between a parked vehicle and the sidewalk.'),
 (r'parking|standing|loading zone|stopping','Identify the part of the curb or roadway addressed and the movement or activity being regulated there.'),
 (r'loop|detection|detector','Trace the detection area in relation to the movement it is meant to register. The original drawing identifies the position and installation details.'),
 (r'conduit|pull box|cabinet|foundation|anchor bolt|mast.arm|wiring|terminal|cable|bracket|mounting','Read the connection between the named component and its support or adjacent equipment. The section, connection details and notes identify the parts used at that location.'),
 (r'retroreflect|visibility|illumination','Compare the applicable device and viewing conditions before reading the corresponding performance value.'),
 (r'letter|numeral|alphabet|abbreviat|legend','Compare the message or character shown with its intended use. Lettering and wording choices affect how much information a traveler can read on approach.'),
 (r'sign.*size|plaque.*size|size.*sign','Find the sign designation first, then read across the roadway or application column that applies.'),
 (r'advance placement|spacing|sight distance|taper length','Match the approach conditions in the heading to the appropriate row or diagram before reading the distance.'),
 (r'preferential|managed lane|hov|express lane|toll','Identify which users may enter each lane and where the signing or markings communicate a change in access.'),
 (r'centerline|edge line|lane line|striping|pavement marker|channeliz|longitudinal','Read the line in the direction of travel and compare its position, continuity and color with the adjacent lanes.'),
 (r'arrow|word marking|pavement marking|symbol','Read the marking from the approaching traveler’s point of view. Its orientation and placement explain which movement or space it identifies.'),
 (r'warning sign|regulatory sign|object marker|plaque|signs','Compare the device legends and symbols with the situation named in the title. The accompanying section explains where each device applies.'),
 (r'signal|beacon','Identify the movement addressed by each indication and the point on the approach where it is seen.'),
 (r'driveway|turning|intersection|cross section|cross.section','Trace the travel paths through the layout and compare the allocation of space at each connection.'),
 (r'pedestrian|sidewalk|walkway|accessib','Follow the pedestrian route through the design and identify its connections to adjoining facilities.'),
 (r'school','Read the treatment in relation to the school approach, crossing, or area it identifies.'),
 (r'speed','Compare the traffic condition described in the heading with the design or operational measure shown.'),
]


@lru_cache(maxsize=None)
def usage(title, kind):
    for rx,text in READING:
        if re.search(rx,title,re.I):return text
    return {'Table':'Compare the row and column headings before using a value. Their intersection identifies which case the entry describes.',
            'Figure':'Read the labels alongside the adjacent manual text to distinguish the example from the conditions governing its use.',
            'Figure page':'The page preserves the surrounding source context, including its labels and any notes.',
            'Bulletin':'Use the linked bulletin to check which projects and decisions fall within its scope.'}.get(kind,
            'Refer to the labeled components and the notes alongside the detail when matching it to a project condition.')


def tidy(s):
    return ' '.join(unescape(re.sub('<[^>]+>',' ',s)).split()).strip()


def sentences(s):
    return [a.strip() for a in re.split(r'(?<=[.!?])\s+(?=[A-Z("])',tidy(s)) if a.strip()]


def describe(row, page_lookup):
    kind,title,num=row['type'],row['title'],row['num']
    detail=tidy(row.get('sum') or '')
    if kind=='Figure page' and re.fullmatch(r'Page \d+|',title,re.I):
        pg=page_lookup.get(row['url'],{})
        txt=tidy(pg.get('text',''))
        terms=[v for v in pg.get('keywords',[]) if v.lower() not in ('ladot','guide','page','design')]
        # Prefer a human-readable line from the source over raw OCR text.
        chapter=pg.get('chapter','').split('-',1)[-1].replace('-',' ')
        cues=', '.join(terms[:4])
        if txt and not pg.get('ocr') and len(txt)<165:
            title=re.sub(r'\s+[|]\s+\d+\b','',txt).strip(' .:')
        elif cues:title=cues[0].upper()+cues[1:]
        else:title=chapter or row['src']
        row['title']=title
    if kind in ('Figure','Table') and re.match(r'^4C-\d+$',num):
        if kind=='Figure' and num in ('4C-1','4C-2','4C-3','4C-4','4C-5','4C-6','4C-7','4C-8','4C-9','4C-10'):
            focus = ('major-street volume against the higher-volume minor-street approach' if num in ('4C-1','4C-2','4C-3','4C-4') else
                     'pedestrian crossing volume against vehicles on the major street' if num in ('4C-5','4C-6','4C-7','4C-8') else
                     'traffic demand near the grade crossing under the approach-lane configuration in the heading')
            return f'{row["src"]} Figure {num} is the chart for {title}. It compares {focus}. Read the time period and adjustment factor in the heading before choosing the curve for the site.'
    if kind in ('Figure','Table'):
        if kind=='Table': intro=f'{row["src"]} Table {num} sets out the entries for “{title}”.'
        else:intro=f'{row["src"]} Figure {num} illustrates “{title}”.'
    elif kind=='Line type':
        intro=f'{num} depicts the {title[:1].lower()+title[1:]} pattern.'
    elif kind=='Marking':
        intro=f'This marking detail shows “{title}” from {row["src"]} Figure {num}.'
    elif detail and not re.search(r'—\s*'+re.escape(title)+r'\.?$',detail,re.I):
        parts=sentences(detail)
        intro=' '.join(parts[:3]).rstrip(' .')+'.'
    else:
        intro=f'{row["src"]} illustrates “{title}” on page {num.lstrip("p")}.' if kind=='Figure page' else f'{row["src"]} {num} covers “{title}”.'
    return intro.rstrip(' .')+'. '+usage(title,kind)


def cdn(edition,number,page):
    url,n=source(edition,number,page)
    return url+'#page='+str(n)


def illustrations(root, details, lookup):
    for alias,hits in list(lookup.items()):
        # OCR had indexed in-paragraph figure mentions as illustrations in the wrong chapters.
        lookup[alias]=[pair for pair in hits if not re.search(r'/(?:ca-mutcd|mutcd)/[^/]+/#fig-',pair[1])]
        if not lookup[alias]:del lookup[alias]
    indexed={(r['src'],r['type'],r['num']):r for r in details if r['type'] in ('Table','Figure')}
    details[:]=[r for r in details if r['type'] not in ('Table','Figure')]
    for edition,items in ART.items():
        agency='Federal MUTCD' if edition=='mutcd' else 'CA MUTCD 2026'
        chapters=defaultdict(dict)
        for key,(title,page) in items.items():
            kind,num=key.split()
            chapter=num.split('-')[0]
            slug=num.lower().replace('(','').replace(')','')
            id_=('table-' if kind=='Table' else 'fig-')+slug
            img=f'{BASE}/figs/{edition}/p{page:04d}.webp'
            row=dict(indexed.get((agency,kind,num),{}))
            row.update(src=agency,sg='MUTCD',type=kind,num=num,title=title,url=f'{BASE}/{edition}/{chapter.lower()}/#{id_}',img=img,full=img,part=chapter[0],original=cdn(edition,num,page))
            row.setdefault('topics',[])
            details.append(row);chapters[chapter][key]=(id_,row)
            for alias in (num,key):
                pairs=lookup.setdefault(alias.upper(),[])
                pairs[:]=[r for r in pairs if not (r[1].startswith(BASE+'/'+edition+'/') and r[0].lower().startswith((agency+' '+kind).lower()))]
                pairs.append([agency+' '+key+' · '+title,row['url']])
        for chapter,entries in chapters.items():
            path=root/edition/(chapter.lower()+'.md'); body=path.read_text()
            seen=set(); old=set()
            def entry(key):
                id_,r=entries[key]; seen.add(key)
                caption=f'{escape(key)} · {escape(r["title"])}'
                total=SHEET_COUNTS[edition].get(key,1)
                first=items[key][1]
                sheets=[]
                for offset in range(total):
                    page=first+offset
                    anchor=id_ if offset==0 else f'{id_}-sheet-{offset+1}'
                    label=caption if total==1 else f'{caption} · Sheet {offset+1} of {total}'
                    image=f'{BASE}/figs/{edition}/p{page:04d}.webp'
                    pdf=cdn(edition,r['num'],page)
                    sheets.append(f'<figure class="mfig"><span id="{anchor}"></span><a href="{image}"><img loading="lazy" src="{image}" alt="{label}"></a><figcaption>{label} · <a href="{pdf}">Publisher PDF</a></figcaption></figure>')
                if total>1:return '<div class="mfig-inline multi manual-sheets">'+''.join(sheets)+'</div>'
                return sheets[0]
            def replace(m):
                raw=m[0]; cap=re.search(r'<figcaption>(Figure|Table)\s+(\d[A-Z]-\d+(?:\s*\(CA\))?)',raw)
                if not cap:return raw
                key=cap[1]+' '+cap[2].replace(' ','')
                idmatch=re.search(r'<span id="([^"]+)"',raw)
                if idmatch:old.add(idmatch[1])
                if key not in entries:return ''
                id_,r=entries[key]
                if key not in seen:return entry(key)
                if key in SHEET_COUNTS[edition]:return ''
                # Preserve distinct continuation sheets already associated with the actual item.
                src=re.search(r'<a href="([^"]+/p(\d+)\.webp)"',raw)
                first=int(r['full'].split('/p')[-1][:-5])
                if src and int(src[2])>first and 'sheet' in raw.lower() and int(src[2]) <= first+8:
                    return re.sub(r'<span id="[^"]+"></span>','',raw)
                return ''
            body=re.sub(r'<figure class="mfig">.*?</figure>',replace,body,flags=re.S)
            missing=[key for key in entries if key not in seen]
            if missing:body+='\n\n## Additional figures and tables\n\n'+'\n\n'.join('<div class="mfig-inline single">'+entry(k)+'</div>' for k in missing)+'\n'
            # Preserve older shared fragments as aliases if the chapter previously used them.
            current=set(re.findall(r'\bid="([^"]+)"',body))
            for old_id in sorted(old-current):
                tid=old_id.replace('fig-','table-',1)
                if tid in current:body=body.replace('<span id="'+tid+'">','<span id="'+old_id+'"></span><span id="'+tid+'">',1)
                else:body+='\n<span id="'+old_id+'"></span>\n'
            path.write_text(body)


def enrich(root,details,lookup):
    # Administrative exhibits, front matter and blank sheets are accessible in their source
    # documents but do not belong among design details.
    def design_item(r):
        if r['type']!='Figure page':return True
        title=r['title']
        return not re.search(r'blank page|section divider|draft watermark|communication from public|^(?:EXHIBIT \d+|\d+ \d+|P/ZC [\d-]+)$|: Vote:|Activity Log|Approval Page|CPC-2013-|Millman Perlman',title,re.I)
    details[:]=[r for r in details if design_item(r)]
    for r in details:
        r['title']=re.sub(r'^(?:Mobility2035_Print \(final\)|mobilityplnmemo)\s*:\s*','',r['title'],flags=re.I)
        r['title']=re.sub(r'[\x00-\x1f\ufeff]','',r['title']).strip()
    illustrations(root,details,lookup)
    pages={}
    for f in Path('data/docs').glob('*__*.json'):
        doc=read(f)
        if isinstance(doc,dict):
            pages.update({p['url']:p for p in doc.get('pages',[]) if 'url' in p})
    # The marking gallery exposes all 203 members even where the older catalog collapsed related items.
    present={r['url'] for r in details}
    for m in read('data/markings/items.json'):
        u=BASE+'/markings/#'+m['id']
        if u not in present:
            r=dict(src='CA MUTCD 2026',sg='MUTCD',type='Marking',num=m['figure'],title=m['name'],url=u,img=BASE+m['img'],full=BASE+m['img'],topics=['striping-intersections'])
            details.append(r);present.add(u)
    # Include city sheets which used to exist only as unindexed gallery images.
    images={(r.get('full') or r.get('img','')).replace('/thumbs/figs/','/figs/') for r in details}
    for file in root.glob('*/standard-plans.md'):
        city=file.parent.name
        def municipal(m):
            raw=m[0]
            image=re.search(r'<a href="([^"]+)"><img',raw)
            if not image or '/figs/'+city+'/' not in image[1] or image[1] in images:return raw
            src=image[1]; anchor='sheet-'+Path(src).stem
            a=re.search(r'<figure[^>]* id="([^"]+)"',raw)
            if a:anchor=a[1]
            else:raw=raw.replace('<figure ',f'<figure id="{anchor}" ',1)
            cap=re.search(r'<figcaption>(.*?)</figcaption>',raw,re.S)
            label=tidy(cap[1]) if cap else Path(src).stem.replace('-',' ')
            name=city.replace('-',' ').title()
            tag,title=(label.split(' — ',1) if ' — ' in label else (name,label))
            record=dict(src=name+' agency sheets',sg=name,type='Agency sheet',num=tag,title=title,
                        url=f'{BASE}/{city}/standard-plans/#{anchor}',img=src,full=src,topics=[])
            details.append(record);images.add(src)
            return raw
        file.write_text(re.sub(r'<figure\b[^>]*>.*?</figure>',municipal,file.read_text(),flags=re.S))
    by_page=defaultdict(dict)
    for r in details:
        r['description']=describe(r,pages)
        route,_,fragment=r['url'].removeprefix(BASE).strip('/').partition('#')
        by_page[route.rstrip('/')][fragment]=r
    for route,items in by_page.items():
        file=root/(route+'.md')
        if not file.exists():file=root/route/'index.md'
        if not file.exists():continue
        body=file.read_text()
        def note(r):
            return '<p class="detail-description">'+escape(r['description'])+'</p>'
        if '' in items:
            r=items['']
            if 'class="dwg-summary"' in body:
                body=re.sub(r'<div class="dwg-summary">.*?</div>',lambda _:note(r),body,count=1,flags=re.S)
            else:
                i=body.find('\n---\n')+5;body=body[:i]+'\n'+note(r)+'\n'+body[i:]
        # Attach prose to its own sheet, table, marking card or source-page anchor.
        def figure(m):
            raw=m[0]; a=re.search(r'\bid="([^"]+)"',raw)
            if not a:return raw
            keys=re.findall(r'\bid="([^"]+)"',raw)
            r=next((items[k] for k in keys if k in items),None)
            if not r:return raw
            return raw.replace('</figcaption>',note(r)+'</figcaption>',1)
        body=re.sub(r'<figure\b[^>]*>.*?</figure>',figure,body,flags=re.S)
        for fragment,r in items.items():
            if r['type'] not in ('Marking','Line type'):continue
            pos=body.find('id="'+fragment+'"')
            if pos<0:continue
            tag='<div class="mbody">' if r['type']=='Marking' else '<div class="ltc-pic">'
            start=body.find(tag,pos)
            if start<0:continue
            end=body.find('</b>',start)+4 if r['type']=='Marking' else start
            body=body[:end]+note(r)+body[end:]
        body=re.sub(r'(<span id="(p\d+)" class="anchor"></span>\s*\n\s*###? [^\n]+)',
                    lambda m:m[0]+'\n\n'+note(items[m[2]]) if m[2] in items else m[0],body)
        file.write_text(body)
    # Cross-linked local drawing cards share the same reading note as their detail page.
    markings=root/'markings/index.md'
    by_url={r['url']:r for r in details}
    def local_card(m):
        row=by_url.get(m[2])
        return m[0].replace('<div class="msrc">',note(row)+'<div class="msrc">') if row else m[0]
    text=re.sub(r'(<div class="mcard"[^>]*><a class="mimg" href="([^"]+)">.*?<div class="msrc">)',local_card,markings.read_text())
    markings.write_text(text)
    save(PUBLIC/'details.json',details)
