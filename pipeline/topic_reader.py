"""Assemble practice-topic pages from current drawings, publisher indexes and governing sections."""
from collections import defaultdict
from html import escape
from pathlib import Path
import re

from current_catalog import BASE, PUBLIC, read
from topics_def import T,CHAPS
from visual_types import graphic,make_visuals,within_articles

ROUTES={
'bikeways':[('Select the facility','/bulletins/bikeway-design-comparison/'),('Check California geometry','/bulletins/caltrans-hdm-ch1000/'),('Design separated bikeways','/bulletins/caltrans-dib-89-02/'),('Find bicycle signs and markings','/ca-mutcd/9e/')],
'crosswalks':[('Review LADOT crossing criteria','/ladot/marked-crosswalks/'),('Place the markings','/ca-mutcd/3c/'),('Check red curb and visibility','/ladot/curb-paint/')],
'accessibility':[('Check Caltrans accessibility guidance','/bulletins/caltrans-dib-82-06/'),('Lay out a curb ramp','/details/caltrans/caltrans-std-plans-2026-a88a/'),('Check accessible signals','/ca-mutcd/4k/')],
'temporary-traffic-control':[('Plan tapers and work areas','/ca-mutcd/6b/'),('Select a typical application','/ca-mutcd/6p/'),('Check Santa Monica submittals','/santa-monica/standard-plans/#ttcp')],
'signals':[('Evaluate signal warrants','/ca-mutcd/4c/'),('Read pedestrian indications','/ca-mutcd/4i/'),('Find the LADOT construction drawing','/ladot/red-book/')],
'striping-intersections':[('Select a line pattern','/markings/line-types/'),('Compare lane widths','/bulletins/lane-widths/'),('Open crosswalk drawing A24F','/details/caltrans/caltrans-std-plans-2026-a24f/')],
'speed-and-calming':[('Review California speed guidance','/ca-mutcd/2b/'),('Compare traffic calming layouts','/burbank/standard-plans/'),('Check hump markings','/ca-mutcd/3b/')],
'curb-parking-loading':[('Look up curb colors and hours','/ladot/curb-paint/'),('Lay out accessible parking','/bulletins/ca-accessible-parking-2026/'),('Check crosswalk clearances','/ladot/curb-paint/#where-red-curb-goes')],
'rail-crossings':[('Check crossing design principles','/ca-mutcd/8a/'),('Select grade crossing signs','/ca-mutcd/8b/'),('Read crossing signals','/ca-mutcd/8d/')],
'street-name-and-guide-signs':[('Lay out conventional guide signs','/ca-mutcd/2d/'),('Find an FHWA sign layout','/signs/'),('Check LADOT local signing','/ladot/mpp-531/')],
'school-zones':[('Check school area signs','/ca-mutcd/7b/'),('Review school markings','/ca-mutcd/7c/'),('Check crossing controls','/ladot/marked-crosswalks/')],
'transit':[('Find the stop design guide by operator','/transit/'),('Read preferential lane markings','/ca-mutcd/3e/'),('Compare lane widths','/bulletins/lane-widths/'),('Review LADOT bus bulb details','/details/ladot/mpp-531-s-523-0/')]
}
# The first paragraph describes the decision a reviewer makes before opening the indexes.
DECISIONS={
 'crosswalks':'Identify the crossing control and the agency that owns the street. For an uncontrolled LA approach, check the marked-crosswalk criteria, then open the drawing for the selected treatment.',
 'bikeways':'Select the facility type for the corridor, then check operating space and the transitions at driveways, intersections and transit stops.',
 'accessibility':'Trace the pedestrian route from the sidewalk through the ramp, crossing and far-side landing. Check the applicable ramp drawing and signal provisions together.',
 'temporary-traffic-control':'Start with the work area, speed and lanes affected. Select the typical application, then check taper dimensions and the pedestrian route through the closure.',
 'signals':'Start with the engineering study for a new signal or the affected movements for a modification. Use the applicable signal provisions before selecting the construction sheets.',
 'striping-intersections':'Identify the lane function and available width. Select the line pattern, then check the transition and any words, arrows or crosswalk markings.',
 'speed-and-calming':'Distinguish a posted-speed change from a physical traffic-calming treatment. For a proposed device, review the local layout together with its advance signs and markings.',
 'curb-parking-loading':'Identify the street owner and the intended curb use. For an LA curb plan, look up the color and operating hours first, then check crossing clearance and accessible parking.',
 'rail-crossings':'Identify the rail operator, crossing type and traffic controls. Check signing, pavement markings and signal coordination at the same crossing.',
 'street-name-and-guide-signs':'Identify where the driver must make a decision. Then check the legend, placement and mounting details for the agency that will maintain the sign.',
 'school-zones':'Locate the school crossing and arrival route first. Check the applicable school-area signs and pavement markings before selecting a crossing treatment.',
 'transit':'Identify the transit operator and street owner. Use the operator’s stop layout for the boarding area, then check the street agency’s lane markings and intersection details.'
}
PATTERNS={
 'bikeways':r'\bbike|\bbicycl|bikeway|sharrow|shared.lane|shared.use path|two.stage turn|cycle track|cycling',
 'signals':r'\bsignal|detector|mast.arm|beacon|warrant|loop detector|countdown|pull box|controller',
 'transit':r'\bbus(?:es)?\b|\btransit\b|\bbrt\b|boarding|preferential lane|light.rail',
 'crosswalks':r'crosswalk|pedestrian crossing|yield line|stop line|limit line|pedestrian hybrid beacon|rapid.flashing',
 'speed-and-calming':r'speed limit|speed hump|speed table|speed cushion|traffic calming|traffic circle|roundabout|chicane|traffic diverter|raised crosswalk|vertical deflection',
 'street-name-and-guide-signs':r'street.name|guide sign|wayfinding|directional sign|destination sign|route marker',
 'curb-parking-loading':r'parking|curb paint|curb mark|loading zone|curbside|parking meter|parklet|passenger loading|tow.away',
 'accessibility':r'accessib|curb ramp|detectable warning|pedestrian access route|wheelchair|landing slope|truncated dome',
 'striping-intersections':r'striping|lane line|edge line|center.?line|channeliz|pavement marking|pavement marker|lane drop|turn bay|turn lane|limit line|lane.width',
 'school-zones':r'school|crossing guard',
 'rail-crossings':r'grade crossing|railroad|railway|light.rail|\blrt\b|crossbuck',
 'temporary-traffic-control':r'temporary traffic control|work.zone|work area|work space|lane closure|road closure|detour|flagger|typical application|temporary pedestrian|barricade|traffic control plan'
}
EXTRA={'signals':['4C-1','4C-2','4C-3','4C-4','4C-5','4C-6','4C-7','4C-8','4C-9','4C-10'],
'school-zones':['7B-1','7B-2'],'rail-crossings':['8B-1','8B-2'],'street-name-and-guide-signs':['2D-10','2D-11']}


def links(rows):
    return '<ul class="topic-records">'+''.join('<li><a href="'+u+'">'+escape(label)+'</a></li>' for label,u in rows)+'</ul>'


def render(root,details):
    groups,index=make_visuals(details)
    sections=read('data/ca-mutcd/sections.json')
    boe=read(PUBLIC/'boe-sections.json')
    signs=read(PUBLIC/'signs-index.json')
    for slug,title,intro,*_ in T:
        file=root/'topics'/(slug+'.md');old=file.read_text()
        head=old.split('\n---\n',1)[0]+'\n---\n\n';match=re.compile(PATTERNS[slug],re.I)
        def matches(row):
            if match.search(row['title']):return True
            if row['type'] in ('Figure','Table'):return row['num'].split('-')[0] in CHAPS.get(slug,[])
            return False
        for row in details:
            prior=row.setdefault('topics',[])
            if matches(row):
                if slug not in prior:prior.append(slug)
            elif slug=='transit' and slug in prior and not match.search((row.get('kw') or '')+' '+(row.get('sum') or '')):prior.remove(slug)
            elif slug=='bikeways' and re.search(r'motorcycle',row['title'],re.I) and slug in prior:prior.remove(slug)
        eligible=[r for r in details if slug in r['topics']]
        drawings=[r for r in eligible if r['type'] in ('Standard drawing','Agency sheet')]
        body=[head,DECISIONS[slug],'','<nav class="topic-tasks" aria-label="Common design tasks">'+''.join('<a href="'+BASE+u+'">'+escape(label)+'</a>' for label,u in ROUTES[slug])+'</nav>','',
              '[Governing sections](#governing-sections-and-agency-guidance) · [Drawings by agency](#drawings-by-agency)','']
        body+=['','## Facility types and applications','']
        def editorial(key):
            marker='<!-- topic-'+key+' -->'
            end='<!-- /topic-'+key+' -->'
            if marker in old and end in old:
                return old[old.index(marker):old.index(end)+len(end)]
            return ''
        statewide=editorial('statewide')
        guides=editorial('guides')
        if statewide:body.extend([statewide,''])
        for label,_,r,caption in groups.get(slug,[]):body+=['### '+label,'',graphic(label,r,caption),'']
        for number in EXTRA.get(slug,[]):
            agency='Federal MUTCD' if slug=='signals' else 'CA MUTCD 2026'
            r=index.get((agency,'Figure '+number))
            if r: body += ['### '+r['title'],'',graphic(r['title'],r,r['description'].split('. ',1)[-1]),'']
        regs=[(r['num']+' · '+r['title'],r['url']) for r in sections if r['chapter'] in CHAPS.get(slug,[]) or match.search(r['title'])]
        body+=['## Governing sections and agency guidance','']
        for heading,rows in [('California MUTCD sections',regs),
                           ('Design bulletins and policy memos',[(r['num']+' · '+r['title'],r['url']) for r in eligible if r['type']=='Bulletin']),
                           ('LA BOE Street Design Manual',[(s['title'],s['url']) for s in boe if match.search(s['title'])])]:
            if rows:body.append(f'<details class="topic-list"><summary>{heading} · {len(rows)}</summary>'+links(rows)+'</details>')
        for agency in ('CA MUTCD 2026','Federal MUTCD'):
            rows=[(r['type']+' '+r['num']+' · '+r['title'],r['url']) for r in eligible if r['src']==agency and r['type'] in ('Table','Figure')]
            if rows:body.append(f'<details class="topic-list"><summary>{agency} figures and tables · {len(rows)}</summary>'+links(rows)+'</details>')
        if guides:body.extend(['',guides,''])
        body+=['','## Drawings by agency','',f'[Browse {len(eligible)} indexed details for this topic]({BASE}/details/?topic={slug})','']
        by=defaultdict(list)
        for row in drawings:by[row['src']].append((row['num']+' · '+row['title'],row['url']))
        for agency,rows in sorted(by.items()):
            body.append(f'<details class="topic-list"><summary>{escape(agency)} · {len(rows)}</summary>'+links(rows)+'</details>')
        if not by:body.append('See the linked manual sections above for applicable layouts.')
        active=[(r['code']+' · '+r['descriptor'],r['url']) for r in signs.values() if match.search(r.get('descriptor',''))]
        if active:body+=['',f'<details class="topic-list"><summary>Sign library matches · {len(active)}</summary>'+links(active)+'</details>']
        body+=['','[Search all sources]('+BASE+'/search/?q='+slug.split('-')[0]+') · [All design topics]('+BASE+'/topics/)','']
        # Maintain incoming links to prior topic headings.
        for fragment in ('Key Standard Drawings & Signs','Bulletins and policy memos','The rules','Agency standard plans and drawings (LADOT, Caltrans 2026, Burbank, Pasadena)','Figures','Signs','Related topics and tools','Federal guidance (FHWA, U.S. Access Board)','National design guides (NACTO, CPBS)'):
            alias=re.sub('[^a-z0-9 -]','',fragment.lower()).replace(' ','-')
            if alias and alias not in {re.sub('[^a-z0-9 -]','',line[3:].lower()).replace(' ','-') for line in body if line.startswith('## ')}:body.append('<span id="'+alias+'"></span>')
        file.write_text('\n'.join(body))
    # Compute public coverage from the current records so the same numbers appear in every build.
    home=root/'index.mdx';text=home.read_text()
    text=re.sub(r'[0-9,]+(</b> details &amp; figures| details &amp; figures)',lambda m:f'{len(details):,}'+m[1],text)
    home.write_text(text)
    inserts=within_articles(root,groups,index)
    print(f'Placed {inserts} in-text source illustrations across reference articles.')
