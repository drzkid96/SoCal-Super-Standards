"""Place an actual publisher's graphic beside a discussed facility type or chart."""
from html import escape, unescape
from pathlib import Path
import re

# Display title, identifying terms, indexed source and designation, and what to look for.
GROUPS={
'bikeways':[
 ('Class I · Shared-use path',r'class i\b|shared.use paths?|bike paths?','Culver City CSDS 2025','CSDS p.46','The path has its own alignment away from motor traffic. Follow how the paths for walking and cycling connect at crossings.'),
 ('Class II · Bicycle lane',r'class ii\b|conventional (?:bike|bicycle) lanes?','Culver City CSDS 2025','CSDS p.45','A longitudinal stripe assigns roadway space to bicycles. Look for which side carries parking and which side carries moving traffic.'),
 ('Class III · Bicycle route',r'class iii\b|signed bike routes?','Culver City CSDS 2025','CSDS p.44','People riding and driving use the same travel space. Signs or shared-lane markings identify the route.'),
 ('Class IV · Separated bikeway',r'class iv\b|protected (?:bike|bicycle) lanes?|separated bikeways?','Culver City CSDS 2025','CSDS p.43','A physical element separates bicycle travel from the adjacent vehicle lane. Trace that separation up to intersections and driveways.'),
 ('Buffered bicycle lane',r'buffer(?:ed|.separated) (?:bike|bicycle) lanes?','Long Beach Std. Plans','LB 303','The painted buffer adds clearance alongside the bicycle lane. The stripes identify space between moving or parked vehicles and riders.'),
 ('Bicycle box',r'bike box(?:es)?|bicycle box(?:es)?','CA MUTCD 2026','Figure 9E-12','The waiting area sits ahead of stopped motor traffic. Follow the rider from the approach lane into the box.'),
 ('Two-stage turn box',r'two.stage (?:bicycle )?turn (?:queue )?box','CA MUTCD 2026','Figure 9E-10','The rider crosses one leg, turns in the waiting area, then crosses the second leg. The location of the box determines the waiting orientation.')],
'speed-and-calming':[
 ('Chicane',r'chicanes?','Complete Streets DG','p156','Successive lateral shifts bend the vehicle path. Trace the curb or parking edge to see the sequence of deflections.'),
 ('Traffic diverter',r'(?:traffic |diagonal )?diverters?','Complete Streets DG','p198','The treatment interrupts some vehicle movements at the intersection. Follow the open movements separately from the routes blocked by the diverter.'),
 ('Speed hump',r'speed humps?','Burbank Std. Plans','BT-414','The rounded vertical profile extends across the vehicle path. Read the profile alongside the plan view.'),
 ('Speed cushion',r'speed cushions?','Burbank Std. Plans','BT-417','Gaps separate the raised sections. Their location relative to wheel paths distinguishes this treatment from a continuous hump.'),
 ('Speed table',r'speed tables?','Burbank Std. Plans','BT-418','Approach and departure ramps connect the pavement to a flat top. The profile shows the length of the raised portion.'),
 ('Raised crosswalk',r'raised crosswalks?','MPP 531','S-483.1','The crossing sits on a raised platform. The drawing relates the pedestrian route to the vehicle approach ramps.'),
 ('Curb extension',r'curb extensions?|bulb.outs?','MPP 531','S-527.0','The curb projects into the roadway at the crossing. Follow the new curb line to see how it changes pedestrian and turning paths.'),
 ('Neighborhood traffic circle',r'(?:neighbou?rhood )?traffic circles?','Supp. Street Design Guide','Detail 700','Vehicles circulate around a center island. The plan shows how the island deflects the approach path.'),
 ('Mini-roundabout',r'mini.roundabouts?','Supp. Street Design Guide','Detail 710','Read the center and approach islands together. The drawing shows how entering traffic reaches the circulating roadway.')],
'crosswalks':[
 ('Pedestrian refuge island',r'pedestrian refuge|crossing islands?','MPP 531','S-525.0','The island divides a crossing into separate roadway segments. Follow the waiting area and its alignment with the crosswalks on either side.'),
 ('Crosswalk marking patterns',r'crosswalk markings?|crosswalk striping|marked crosswalk','CA MUTCD 2026','Figure 3C-1','Compare the direction of the transverse lines and longitudinal bars relative to approaching traffic.'),
 ('Diagonal pedestrian crossing',r'diagonal cross(?:ing|walk)|exclusive pedestrian phase','CA MUTCD 2026','Figure 3C-2','Diagonal markings connect opposite corners during an exclusive pedestrian phase. The figure shows how that path meets the conventional crossings.'),
 ('Uncontrolled multilane crossing',r'uncontrolled (?:multilane )?(?:pedestrian )?cross(?:ing|walk)','CA MUTCD 2026','Figure 3C-101(CA)','Look across the approach lanes to see the placement of the crosswalk, signs, and advance markings.'),
 ('Pedestrian hybrid beacon',r'pedestrian hybrid beacons?|\bPHBs?\b','CA MUTCD 2026','Figure 4J-3','Follow the sequence of beacon displays through a pedestrian crossing request.')],
'curb-parking-loading':[
 ('On-street parking',r'on.street parking','Culver City CSDS 2025','CSDS p.62','The curbside parking space is shown in relation to the moving lane and sidewalk.'),
 ('Freight loading',r'freight (?:loading|management)|freight zones?','Culver City CSDS 2025','CSDS p.56','Trace the loading operation from the curbside vehicle to the adjacent frontage.'),
 ('Parklet',r'parklets?','Culver City CSDS 2025','CSDS p.64','The installation repurposes curbside roadway space for people. Look at its edges, access point, and relationship to the sidewalk.')],
'transit':[
 ('Attached bus bulb',r'attached (?:\(type i\) )?bus bulbs?','Supp. Street Design Guide','p54','The boarding area meets the sidewalk. Follow the bicycle alignment and the passenger path where the two approaches meet.'),
 ('Floating boarding island',r'floating (?:bus stop|bus bulb|boarding island)','Supp. Street Design Guide','p55','The boarding area sits away from the main sidewalk. The original layout shows the bicycle path and pedestrian crossing serving the island.'),
 ('Transit lane',r'transit lanes?|bus.only lanes?','Culver City CSDS 2025','CSDS p.75','The street section identifies the space reserved for transit relative to adjacent travel lanes.'),
 ('Transit stop',r'transit stops?|bus stops?','Culver City CSDS 2025','CSDS p.76','Follow the passenger route to the boarding location at the curb.'),
 ('Bus bulb',r'bus bulbs?','MPP 531','S-523.0','The sidewalk extends to the boarding position. The bus can serve the stop beside the extended curb.')],
'temporary-traffic-control':[
 ('Bicycle lane closure without a detour',r'bicycle lane closure without a detour','CA MUTCD 2026','Figure 6P-47','Trace the bicycle movement through the work area and read the warning sequence on the approach.'),
 ('Bicycle lane closure with a detour',r'bicycle lane closure with an on.road detour','CA MUTCD 2026','Figure 6P-48','Follow the signed diversion from the bicycle lane and find the return to the original route.'),
 ('Shared-use path diversion',r'shared.use path (?:closure|diversion)','CA MUTCD 2026','Figure 6P-49','The path is redirected around the activity area. Follow the temporary alignment between the two open path segments.')],
'accessibility':[
 ('Curb ramp',r'curb ramps?','Caltrans Std. Plans 2026','A88A','Trace the route between the sidewalk landing, the ramp run and the crossing.'),
 ('Island passageway',r'island passageway|island cut.through','Caltrans Std. Plans 2026','A88B','Trace the crossing through the island and identify where the pedestrian route meets each roadway edge.')],
'striping-intersections':[
 ('Barrier-separated preferential lane',r'barrier.separated preferential','CA MUTCD 2026','Figure 3E-1','A barrier separates traffic streams. The markings delineate the roadway next to that barrier.'),
 ('Buffer-separated preferential lane',r'buffer.separated preferential','CA MUTCD 2026','Figure 3E-2','A marked buffer separates the lanes. Compare its boundaries with the allowable access points.'),
 ('Contiguous preferential lane',r'contiguous preferential','CA MUTCD 2026','Figure 3E-3','The preferential lane adjoins the general-purpose lane. The lane-line treatment identifies the boundary.')],
}
FIGREF=re.compile(r'\b(Figure|Table)\s+(\d[A-Z]-\d+(?:\s*\(CA\))?)(?![\w(])',re.I)

def make_visuals(details):
    index={(r['src'],(r['type']+' ' if r['type'] in ('Figure','Table') else '')+r['num']):r for r in details}
    groups={}
    for group,items in GROUPS.items():
        groups[group]=[]
        for title,terms,agency,code,caption in items:
            r=index.get((agency,code))
            if not r:raise ValueError('Missing representative sheet: '+agency+' '+code)
            groups[group].append((title,re.compile(r'\b(?:'+terms+r')',re.I),r,caption))
    return groups,index


def graphic(title,r,caption,compact=False):
    image=(r.get('full') or r['img']).replace('/thumbs/figs/','/figs/')
    classes = 'type-example reading-example' if compact else 'type-example'
    thumbnail = image.replace('/figs/', '/thumbs/figs/', 1)
    preview = thumbnail if compact and Path('public'+thumbnail.removeprefix('/SoCal-Super-Standards')).is_file() else image
    return (f'<figure class="{classes}"><figcaption><strong>{escape(title)}</strong> {escape(caption)}</figcaption>'
            f'<a href="{image}"><img src="{preview}" loading="lazy" alt="{escape(title,quote=True)} — {escape(r["src"],quote=True)} {escape(r["num"],quote=True)}"></a>'
            f'<a class="source-sheet" href="{r["url"]}">{escape(r["src"])} · {escape(r["num"])} — open source</a></figure>')


def within_articles(root,groups,index):
    inserted=0
    for path in root.rglob('*.md'):
        section=path.relative_to(root).parts[0]
        if section in {'topics','details','signs','markings','keywords','search'}:continue
        body=path.read_text();head,sep,article=body.partition('\n---\n')
        if not sep:continue
        pieces=re.split(r'(?=^##(?:#)? )',article,flags=re.M); change=False
        seen_on_page=set()
        for i,block in enumerate(pieces):
            # Analyze authored text, excluding existing images, OCR, navigation and linked indexes.
            prose=re.sub(r'<(?:figure|nav|script|details)\b.*?</(?:figure|nav|script|details)>',' ',block,flags=re.S)
            prose=unescape(re.sub('<[^>]+>',' ',prose))
            examples=[]
            for family in groups.values():
                matches=[v for v in family if v[1].search(prose)]
                heading=prose.split('\n',1)[0]
                if len(matches)>1 or any(v[1].search(heading) for v in matches): examples.extend(matches)
            edition='Federal MUTCD' if section=='mutcd' else 'CA MUTCD 2026' if section=='ca-mutcd' else None
            for kind,num in FIGREF.findall(prose):
                number=re.sub(r'\s+','',num.upper())
                key=kind.title()+' '+number
                # Outside a manual, only resolve comparisons whose cited edition is explicit.
                source=edition
                if not edition:
                    m=re.search(r'(Federal MUTCD|FHWA|CA MUTCD(?: 2026)?)\s*[,·:–-]?\s*'+re.escape(kind)+r'\s+'+re.escape(num),prose,re.I)
                    source=('Federal MUTCD' if m and m[1].lower().startswith(('federal','fhwa')) else 'CA MUTCD 2026' if m else None)
                r=index.get((source,key))
                if r and (r.get('full') or r['img']) not in block:
                    examples.append((key+' · '+r['title'],None,r,r['description'].split('. ',1)[-1]))
            seen=set()
            cards=[]
            lines=block.splitlines(keepends=True)
            paragraphs=[(j,unescape(re.sub('<[^>]+>',' ',line))) for j,line in enumerate(lines)
                        if re.fullmatch(r'<p(?: [^>]*)?>.*</p>\s*',line)]
            for title,term,r,caption in examples:
                image=r.get('full') or r['img']
                if image in seen or image in seen_on_page or ('src="'+image+'"') in block:continue
                # Exact references in manual paragraphs get edition-specific citation cards.
                if edition and term is None and any(title.split(' · ')[0] in text for _,text in paragraphs):
                    continue
                seen.add(image);seen_on_page.add(image)
                card=graphic(title,r,caption,compact=True)
                near=next((j for j,text in paragraphs if term and term.search(text)),None)
                if near is None:
                    cards.append(card)
                else:
                    lines[near]=lines[near].rstrip()+'\n'+card+'\n'
                    change=True;inserted+=1
            pieces[i]=''.join(lines)
            if cards:
                pieces[i]=pieces[i].rstrip()+'\n\n'+'\n'.join(cards)+'\n\n';change=True;inserted+=len(cards)
        if change:path.write_text(head+sep+''.join(pieces))
    return inserted
