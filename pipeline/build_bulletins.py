"""Bulletins and policy memos: Caltrans Design Information Bulletins (lane width) and LADOT signing and striping
policy guidance currently in effect. Content is a plain-language digest with section references and a link to the
official copy; values were read from the official documents (checked 2026-11-18).

Writes src/content/docs/bulletins/*.md, adds "Bulletin" entries to public/data/details.json and lookup.json.
"""
import html, json, os, re

BASE = "/SoCal-Super-Standards"
CHECKED = "November 18, 2026"
esc = lambda t: html.escape(str(t), quote=False)
OUT = "src/content/docs/bulletins"
os.makedirs(OUT, exist_ok=True)

def table(head, rows, cls="btab"):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'

# ------------------------------------------------------------------ Caltrans DIBs
DIB_PAGE = "https://dot.ca.gov/programs/design/design-information-bulletins-dibs"
CT = [
 dict(slug="caltrans-dib-94", num="DIB 94", title="Complete Streets: Contextual Design Guidance", date="January 16, 2024",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/dib-94-010224-a11y.pdf",
      status="In effect. Effective immediately on issue. Projects already in development follow HDM Index 82.5.",
      supersedes="Where a project segment uses DIB 94, its standards replace the HDM and DIB 89 standards in that segment (and, through the HDM, DIB 79 design standards). Where DIB 94 is silent, the HDM and DIB 89 still apply.",
      lane="10.5 to 12 ft for through and turn lanes, by place type and speed (Table 5.3); 11 ft minimum for transit-only lanes and for right-hand and left-turn lanes on large-vehicle routes.",
      topics=["striping-intersections", "bikeways", "transit", "speed-and-calming"],
      kw="lane width, travel lane width, 10.5 foot lanes, narrow lanes, road diet, place type, complete streets, shoulder width, bike lane width, separated bikeway width, two-way left-turn lane, TWLTL, transit-only lane width, Caltrans DIB 94",
      body=lambda: f"""
## Where it applies

DIB 94 is an opt-in set of standards for Complete Streets work on the State Highway System. A project segment can use it only when all three apply (Section 2.3):

1. The segment is in an Urban Area, Suburban Area or Rural Main Street place type.
2. The posted speed is 45 mph or less.
3. The project provides or improves a bicycle, pedestrian or transit facility, as recorded in the Complete Streets Decision Document.

Transitional areas, undeveloped areas and special use or protected lands are excluded. Locally or privately funded projects on State right of way may use the standards when they meet the first two criteria and the sponsor documents why (Section 2.4). Not meeting an underlined standard needs a Design Standard Decision Document.

## Lane width (Section 5.3)

The 10.5 ft floor comes from the Vehicle Code: CVC 35100(a) allows an 8.5 ft (102 in) vehicle, and CVC 35109 lets mirrors and devices stick out up to 10 in on each side. That makes a 122 in (about 10.2 ft) vehicle, so State lanes are not narrower than 10.5 ft.

- Through, left-turn and right-turn lanes should generally be 10.5 to 12 ft. This does not apply to crossroads at interchanges inside State right of way.
- A lane under 10.5 ft is a documented exception. Engineering judgment may allow it for a right-turn lane, or a tangent through lane with a shoulder, where the posted speed is 40 mph or less and truck volume is under 250 AADTT per lane.
- Routes that carry trailers, motorhomes, buses or other vehicles at the legal maximum width should not get lanes under 10.5 ft.
- With two or more lanes per direction, size them together. The inside lane can be about 10.5 ft and the outside lane, where trucks run, 11 to 12 ft. Heavy truck use favors the top of the range. With a median, the inside lane can be narrower.
- On roads with transit-only lanes or many large design vehicles (STAA, California Legal, 45 ft bus, motorhome), right-hand, transit-only and left-turn lanes should be at least 11 ft (HDM Index 404.4).
- Rural Main Street segments at the edge of town suit the upper range, narrowing as walking, biking and transit demand grows. A four-to-three road diet with narrower lanes can free space for sidewalks and bikeways.
- Related: pavement widening, HDM Index 206.2(3); cross section reduction, HDM Index 301.2(3).

**Table 5.3, suggested minimum lane widths** (guidance; ft)

{table(["Place type", "Lane", "20 mph", "25 mph", "30 mph", "35 mph", "40 mph", "45 mph"], [
 ["Urban: City Center", "Through", "10.5", "10.5", "10.5", "10.5", "10.5-11", "10.5-11"],
 ["Urban: City Center", "Left or right turn", "10.5", "10.5", "10.5", "10.5", "10.5-11", "10.5-11"],
 ["Urban: City Center", "TWLTL", "10.5", "10.5", "10.5", "10.5", "10.5-11", "10.5-11"],
 ["Urban: Urban Community", "Through", "10.5", "10.5", "10.5", "10.5", "10.5-11", "10.5-11"],
 ["Urban: Urban Community", "Left or right turn", "10.5", "10.5", "10.5", "10.5", "10.5-11", "10.5-11"],
 ["Urban: Urban Community", "TWLTL", "10.5", "10.5", "10.5", "10.5", "10.5-11", "10.5-11"],
 ["Suburban Area", "Through", "10.5", "10.5", "10.5", "10.5-11", "11-12", "11-12"],
 ["Suburban Area", "Left or right turn", "10.5", "10.5", "10.5", "10.5-11", "11-12", "11-12"],
 ["Suburban Area", "TWLTL", "10.5", "10.5", "10.5", "10.5-11", "10.5-11", "11-12"],
 ["Rural Main Street", "Through", "10.5", "10.5", "10.5-11", "10.5-11", "11-12", "11-12"],
 ["Rural Main Street", "Left or right turn", "10.5", "10.5", "10.5-11", "10.5-11", "11-12", "11-12"],
 ["Rural Main Street", "TWLTL", "10.5", "10.5", "10.5", "10.5-11", "10.5", "10.5"],
])}

The table is adapted from NCHRP Report 880 Exhibit 4.8, adjusted for the Vehicle Code and HDM. In Suburban and Rural Main Street areas, check with the District Truck Access Manager on truck turning needs before narrowing.

## Shoulder width (Section 5.4)

- Minimum continuous usable paved right shoulder: 4 ft.
- Where a sidewalk, Class I path or Class IV bikeway is provided: 0 to 4 ft, but 4 ft at an interchange crossroad or next to a barrier or railing.
- Expect more than 4 ft where there is a Class II bike lane or on-street parking (both counted as shoulder), gutter spread for drainage (HDM Chapter 830), an evacuation route (DIB 93) or transit use.

## Bikeway widths (Section 5.1)

{table(["Facility", "Placement", "Minimum", "Preferred", "Practical max"], [
 ["Class II bike lane", "At curb, pavement edge, parking, or between through and turn lanes", "5 ft", "6-7 ft", "8 ft"],
 ["Class II bike lane", "Next to a buffer", "4 ft", "5-7 ft", "8 ft"],
 ["Class IV, one-way", "Between curbs (raised island)", "6 ft", "7-9 ft", "10 ft"],
 ["Class IV, one-way", "Curb to buffer, or curb to parking buffer", "5-8 ft", "6-8 ft", "9 ft"],
 ["Class IV, one-way", "Pavement edge to buffer, or between through and right-turn lanes", "4-7 ft", "5-7 ft", "8 ft"],
 ["Class IV, two-way", "Between curbs", "10-14 ft", "12-14 ft", "16 ft"],
 ["Class IV, two-way", "Curb to buffer", "9-12 ft", "10-12 ft", "14 ft"],
 ["Class IV, two-way", "Curb to parking buffer", "9-14 ft", "10-14 ft", "16 ft"],
 ["Class IV, two-way", "Pavement edge to buffer", "8-11 ft", "9-11 ft", "14 ft"],
 ["Class I path, one-way", "", "6-7 ft", "7 ft", "8 ft"],
 ["Class I path, two-way", "", "10-12 ft", "10-12 ft", "12-15 ft"],
])}

- Bike lane widths exclude the gutter. Above 40 mph posted, bike lanes should be at least 6 ft.
- Buffers: 2 ft minimum, 2 to 4 ft preferred; 2 to 4 ft door-zone buffer next to parking.
- Class II is recommended at 25 mph or less, buffered Class II at 35 mph or less. At 40 to 45 mph, use separation, or a Class II lane with at least a 4 ft buffer where separation is not feasible.

## Contents

Introduction; use of the guidance; design contexts and place types; vehicle speeds; roadway cross section (bicycle facilities, pedestrian facilities, lane width, shoulder width); crosswalks and enhanced crosswalks; bus transit; green streets; graphic examples by place type.
"""),
 dict(slug="caltrans-dib-89-02", num="DIB 89-02", title="Class IV Bikeway Guidance (Separated Bikeways/Cycle Tracks)", date="February 7, 2022",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/dib-89-02-final-a11y.pdf",
      status="In effect. Effective immediately on issue. Projects already in development follow HDM Index 82.5.",
      supersedes="Supersedes DIB 89-01 (May 3, 2018). Inside a project segment that uses DIB 94, DIB 94 governs; DIB 89-02 applies where DIB 94 is silent.",
      lane="Does not set travel lane widths. Notes that lanes or the bikeway may need narrowing at loading zones, transit stops and passenger drop-off.",
      topics=["bikeways"],
      kw="separated bikeway width, cycle track width, Class IV, buffer width, flexible posts, raised island, parking buffer, two-way cycle track, lane narrowing, Caltrans DIB 89",
      body=lambda: f"""
## Where it applies

Design criteria and guidance for Class IV (separated) bikeways in California. It covers State highway projects and, through the HDM and the Local Assistance Procedures Manual, local agency facilities. The FHWA Separated Bike Lane Planning and Design Guide is the companion reference.

## Bikeway width (Section 3.4)

- One-way: 7 ft preferred, 5 ft minimum next to a roadway.
- Two-way: same as a Class I bike path (HDM Index 1003.1). At street level next to a gutter pan, the lane by the gutter needs at least 3 ft of paved width.
- Temporary narrowing at accessible parking or a raised bus stop island: 4 ft one-way, 8 ft two-way.

## Separation (Section 3.3)

{table(["Separation type", "Width"], [
 ["Grade separated, at sidewalk level", "1.5 ft minimum including curb; 3 ft minimum with parking"],
 ["Raised bikeway in the roadbed", "3 ft preferred, 2 ft minimum without parking; 3 ft with parking; 5 ft at accessible parking"],
 ["Flexible posts", "Marked buffer 3 ft preferred, 2 ft minimum; on a sidewalk, posts at least 1.5 ft from curb face"],
 ["Inflexible barrier", "35 mph or less: 3 ft preferred, 2 ft minimum; higher speeds call for concrete barrier"],
 ["On-street parking", "3 ft minimum buffer; 5 ft at accessible parking"],
 ["Raised island", "3 ft preferred, 2 ft minimum without parking; 1 ft with flexible posts; 3 ft with parking; 5 ft at accessible parking"],
])}

- Keep 5 ft clear for pedestrians where an inflexible barrier meets parking, and next to accessible parking. Leave a 5 ft opening where continuous barriers, islands or curbs are used at parking.
- Objects 30 in or taller: 6 in from curb face preferred (12 in without curb). Vertical clearance 8 ft minimum.

## Travel lanes

DIB 89-02 gives no travel lane widths. At loading zones, transit stops and drop-off zones it says the vehicle lane or the bikeway may need to be narrowed (FHWA guide Figures 20 and 21).
"""),
 dict(slug="caltrans-dib-79-04", num="DIB 79-04", title="Design Guidance and Standards for Major Pavement Rehabilitation Projects (2R and 3R)", date="October 2, 2019",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/signed-dib-79-04-posting-030123-a11y.pdf",
      status="In effect (listed on the Caltrans DIB page; posted copy dated March 1, 2023).",
      supersedes="Supersedes DIB 79-03. Inside a segment that uses DIB 94, DIB 94 standards replace the DIB 79 design standards.",
      lane="12 ft on two- and three-lane conventional highway 3R projects; urban turn lanes may be narrower, right-turn lanes to 10 ft when severely constrained.",
      topics=["striping-intersections"],
      kw="3R lane width, 2R, pavement rehabilitation, resurfacing, restoration, rehabilitation, shoulder width table, ADT, turn lane width, 10 foot right turn lane, Caltrans DIB 79",
      body=lambda: f"""
## Where it applies

Design procedures and standards for roadway rehabilitation projects whose main work is pavement (2R and 3R). It supplements the HDM, which applies where the DIB is silent. Freeways, expressways and multilane conventional highways must meet current HDM standards for new construction (Section 3.3.1). Minor rehabilitation (CAPM) is covered by DIB 81.

## Lane width (Section 3.3.3.6.1.1)

- All lanes on two- and three-lane conventional highway 3R projects are 12 ft, with these exceptions:
  - Urban turn lanes may be narrower because speeds are lower. Narrow the right-turn lane first, since the left-turn lane is next to oncoming traffic.
  - In severely constrained locations a right-turn lane may go down to 10 ft.
  - Each location with a narrowed turn lane needs a truck usage study and a turning analysis.
- Any deviation is recorded in a Design Standard Decision Document. References: HDM Indexes 301.1, 405.2, 405.3 and 504.3(1)(b).
- On curves under 300 ft radius with a central angle over 60 degrees, consider extra lane width for offtracking (Section 3.3.3.4).

## Shoulder width (Table 2, two-lane conventional highways)

{table(["Existing ADT", "3R bridge shoulder", "3R shoulder", "Min. existing bridge shoulder", "Min. existing shoulder"], [
 ["0-250", "4 ft", "0 ft*", "0 ft", "0 ft"],
 ["251-1,000", "4 ft", "2 ft*", "2 ft", "0 ft"],
 ["1,001-3,000", "8 ft", "4 ft*", "4 ft", "2 ft"],
 ["3,001-6,000", "8 ft", "8 ft", "6 ft", "4 ft"],
 ["6,001-18,000", "8 ft", "8 ft", "8 ft", "4 ft"],
 ["Over 18,000", "8 ft", "8 ft", "8 ft", "8 ft"],
])}

\\* Under some conditions the right shoulder must be at least 4 ft, or 5 ft with a gutter.

- Shoulders narrower than the minimum existing width are widened to the 3R width. Wider ones may stay unless the pavement is widened or realigned.
- The minimum usable shoulder for bicycles and pedestrians is 4 ft.
- Added passing, climbing or right-turn lanes need at least 4 ft of shoulder next to them (5 ft with a gutter).
- Bridge clear width must at least match the approach roadbed. Replacing bridge rail means widening shoulders to the 3R bridge width.
"""),
 dict(slug="caltrans-dib-81-03", num="DIB 81-03", title="Minor Pavement Rehabilitation Capital Preventive Maintenance (CAPM) Guidelines", date="November 8, 2024",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/dib-81-03-a11y.pdf",
      status="In effect.",
      supersedes="Supersedes DIB 81-02.",
      lane="No numeric widths. Restriping that creates nonstandard lanes, including narrowing lanes for a bike facility, needs a Design Standard Decision Document.",
      topics=["striping-intersections", "bikeways"],
      kw="CAPM, restriping, resurfacing, lane narrowing for bike lanes, nonstandard features, design standard decision document, Caltrans DIB 81",
      body=lambda: """
## Where it applies

Capital preventive maintenance (minor pavement rehabilitation) on the State Highway System. Design standards are handled the same way as 3R projects (DIB 79) under Section 2.3.

## What it says about lane width

- It sets no lane or shoulder widths of its own.
- Restriping is allowed during CAPM. If the new configuration introduces nonstandard geometric features, a Design Standard Decision Document is required (Section 2.3).
- Its examples of design exceptions include reduced lane widths to fit a bike facility, and reduced shoulder width from a standard dike, guardrail or bridge approach rail.
- Shoulder backing must be specified to avoid pavement edge drop-offs (Section 4.2).

This matters for repaving-plus-restriping projects: a lane diet done with CAPM still goes through the DSDD process unless the segment uses DIB 94.
"""),
 dict(slug="caltrans-dib-93", num="DIB 93", title="Evacuation Route Design Guidance", date="December 23, 2020",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/signed-dib-93-evacuation-route-a11y.pdf",
      status="In effect.",
      supersedes="New bulletin; supplements the HDM.",
      lane="12 ft standard on evacuation routes (HDM 301.1); 11 ft acceptable in rural town centers with low speeds and low truck volumes.",
      topics=["striping-intersections"],
      kw="evacuation route, wildfire, 12 foot lanes, 11 foot lanes, rural town center, shoulder as evacuation lane, turn pocket, Caltrans DIB 93",
      body=lambda: """
## Where it applies

Mainly rural communities with limited access where a State highway is an evacuation route, with wildfire as the main case. It supplements the HDM and does not replace engineering judgment.

## Lane and shoulder width

- Travel lanes: 12 ft standard (HDM Index 301.1), and standard widths should be used on designated evacuation routes (Section 3.2).
- 11 ft lanes are acceptable in rural town centers with low speeds and low truck volumes.
- Where standard widths cannot fit, options include clearing parking lanes for traffic, adding a buffered Class II bike lane, or widening shoulders.
- Shoulders of 10 ft or more can serve as an extra evacuation or access lane. Otherwise make them wide enough for disabled vehicles to pull out, or build wide pullouts at key points (Section 3.3).
- Horizontal clearance at least 4 ft, tied to the HDM shoulder standard (Section 3.5).
- At intersections, size for the main evacuation direction and avoid narrowing lanes for turn pockets or bike lanes (Section 3.6).
- Bridges and tunnels should match or exceed the approach roadway width (Section 3.11).

DIB 94 lists evacuation routes as a case where shoulders wider than 4 ft are expected.
"""),
 dict(slug="caltrans-dib-92", num="DIB 92", title="Single Point Interchange Guidelines", date="November 9, 2018",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/f0005291-dib92-a11y.pdf",
      status="In effect. Projects already in development follow HDM Index 82.5.",
      supersedes="New bulletin; supplements the HDM, which applies except where DIB 92 says otherwise.",
      lane="14 ft left-turn lanes through the intersection, plus offtracking width where needed.",
      topics=["striping-intersections"],
      kw="single point interchange, SPI, SPUI, left turn lane width, 14 foot lane, offtracking, Caltrans DIB 92",
      body=lambda: """
## Lane width (Section 3.4)

- Left-turn lanes through the intersection: 14 ft. More may be needed for truck offtracking (HDM Table 504.3).
- Other lanes and shoulders follow the HDM. Bikeways follow HDM Index 301.2 and DIB 89; sidewalks follow HDM Index 105.2 (Section 3.8).
- An optional design keeps the bicycle crossing to about 85 ft, from the stop bar to the middle of the far lane, so a bicyclist can clear in one phase (Section 2.2).
"""),
 dict(slug="caltrans-dib-90", num="DIB 90", title="Diverging Diamond Interchange", date="December 14, 2017",
      url="https://dot.ca.gov/-/media/dot-media/programs/design/documents/dib90-a11y.pdf",
      status="In effect.",
      supersedes="New bulletin. Within the DDI limits it governs where it conflicts with the HDM or the FHWA DDI guide.",
      lane="Wider lanes in every lane through the crossovers for truck offtracking (no single value; HDM 301.1 and Table 504.3).",
      topics=["striping-intersections"],
      kw="diverging diamond interchange, DDI, crossover, lane width offtracking, shoulder width, center walkway, Caltrans DIB 90",
      body=lambda: f"""
## Lane and shoulder width

- Lane width (Section 2.7): all lanes, not just the right-most, need extra width for truck offtracking. No single value; see HDM Index 301.1 and Table 504.3.

{table(["Location", "Width"], [
 ["Left shoulder at crossover approach", "0 ft, to discourage wrong-way entry"],
 ["Left shoulder between crossovers", "2 ft minimum, 4 ft preferred (wider for sight distance)"],
 ["Right shoulder at approaches and between crossovers", "4 ft minimum with curb or guardrail; 3 ft otherwise; 6 ft preferred next to barrier between crossovers"],
 ["Shoulders at departures, ramps and turn lanes", "HDM Index 302.1"],
 ["Center walkway for pedestrians and bicyclists", "10 ft minimum, 14 ft preferred"],
])}
"""),
]

# ------------------------------------------------------------------ LADOT
LA = [
 dict(slug="ladot-lane-reconfiguration-2023", num="CSC Lane Reconfiguration", title="Lane Reconfiguration Guidelines", date="April 2023",
      url="https://ladot.lacity.gov/sites/default/files/2024-09/lane-reconfiguration-guidelines-update-april-2023.pdf",
      status="In effect. Listed in the LADOT Technical Reference Library.", supersedes="Update of the January 2020 Lane Reconfiguration Guidelines.",
      area="Road diets and lane repurposing", topics=["striping-intersections", "bikeways", "transit"],
      kw="road diet, lane reconfiguration, lane repurposing, 4 to 3 conversion, two-way left-turn lane, ADT threshold, vehicles per hour per lane, delay per mile, High Injury Network, Mobility Plan 2035, LADOT Complete Streets Committee",
      body=lambda: """
## When a reconfiguration is a candidate

A project should meet at least one of these:

- More than one travel lane in each direction and no center two-way left-turn lane.
- On the High Injury Network, with an expected safety benefit.
- On a Mobility Plan 2035 bicycle, transit or pedestrian network, where the change allows the facility that network calls for.
- The community, council office or Department wants more travel by other modes, better safety for vulnerable users, or lower speeds.

## Volumes and delay

- FHWA suggests 20,000 ADT or less for four-to-three conversions. Extrapolating, lane reductions may work up to 37,500 ADT on roads with three lanes each way. ADT is not a hard cutoff; peak hour analysis (HCM 2022) is the preferred test.
- Pre-project delay study trigger: 1,000 vehicles per hour per lane on a Boulevard, or 900 on an Avenue, in a peak hour. Below that is "Low Volume", above it "High Volume", and the outreach rules differ.
- Added delay of 2 to 5 minutes per mile: proceed with caution. Over 5 minutes per mile: only with a substantiated overriding need (safety, connectivity, sustainability or equity) or an adopted plan, and discussed at the Complete Streets Committee.
- Delay analysis is not required by CEQA or the Mobility Plan 2035 settlement and is optional below the thresholds. Delay alone is not a CEQA impact.

## Required steps

- Pre-project counts for every reconfiguration, including exempt ones, and for affected signals; recount if counts are over two years old. Use current timing charts for any simulation.
- File a Notice of Exemption when no impacts need mitigation. Bike lanes on the Mobility Plan Bicycle Lane, Bicycle Enhanced or Neighborhood Enhanced networks are statutorily exempt, but still file the notice.
- Council office support before starting. CPUC approval for changes at active rail crossings. LAFD involvement for concrete barriers or medians. Early transit operator coordination (bus stops) and ATSAC coordination (timing).
- Plan post-project evaluation and fixes (coordination, transit priority, turn pocket lengthening). Use quick-build materials first where possible.

The guidelines do not set lane widths; use MPP 531 for those (see the lane width comparison).
"""),
 dict(slug="ladot-bikeway-marking-2022", num="CSC Bikeway Marking", title="Bikeway Marking", date="December 2022",
      url="https://ladot.lacity.gov/sites/default/files/2026-04/bikeway-pavement-marking.pdf",
      status="In effect. Current copy posted April 2026.", supersedes="Not stated.",
      area="Bike lane and bikeway pavement markings", topics=["bikeways"],
      kw="bike symbol, bicycle symbol marking, helmeted bicyclist, BIKE LANE legend, BIKE PATH legend, sharrow, 90 mil, preformed thermoplastic, stencil, LADOT Complete Streets Committee",
      body=lambda: f"""
## Rule

The bike symbol is LADOT's preferred marking for new bikeways and for refreshing faded markings on existing ones. It is the only marking the CA MUTCD permits on every bikeway class.

{table(["Bikeway", "Markings the CA MUTCD permits", "LADOT preference"], [
 ["Class I path", "Bike symbol or BIKE PATH", "Bike symbol"],
 ["Class II lane", "Bike symbol, helmeted bicyclist or BIKE LANE", "Bike symbol"],
 ["Class III route", "Bike symbol in the shared lane marking", "Bike symbol"],
 ["Class IV separated", "Bike symbol or helmeted bicyclist", "Bike symbol"],
])}

- Materials: 90 mil stencils and preformed bike symbols are preferred. Use a 125 mil stencil only if it is the only one available at installation.
- On geometric design plans the bike symbol shall be specified explicitly. On work orders, request it as the preferred type.
- The helmeted bicyclist and the word legends remain legal under the CA MUTCD but are being phased out in LADOT practice.
- Sizes and spacing are not set here; use CA MUTCD Part 9 and MPP 531.
"""),
 dict(slug="ladot-lpi-2021", num="CSC Leading Pedestrian Interval", title="Leading Pedestrian Interval", date="Revised June 2021",
      url="https://ladot.lacity.gov/sites/default/files/2022-08/csc-policy-guidance-lpi-revised-june-2021.pdf",
      status="In effect. Listed in the LADOT Technical Reference Library.", supersedes="Not stated (revised edition).",
      area="Signal timing that affects crosswalks and turn restrictions", topics=["signals", "crosswalks"],
      kw="leading pedestrian interval, LPI, walk head start, turning vehicles, protected permissive left turn, PPLT, no turn on red, accessible pedestrian signal, LADOT Complete Streets Committee",
      body=lambda: """
## Where to consider an LPI

At signalized crosswalks where the WALK is actuated, or, for non-actuated WALK phases, where any of these apply:

- At least 200 turning vehicles per hour across the crosswalk in the peak hour.
- Within 500 ft of a school, park, hospital or senior center.
- On a High Quality Transit Corridor (bus every 15 minutes or better in the peak). LPI can slow parallel transit.
- Unusual geometry that creates unexpected conflicts or visibility problems.

If one crosswalk gets an LPI, give the parallel crosswalk one too; perpendicular legs are judged separately. With protected-permissive left turns, the controller drops the LPI in cycles where the arrow runs.

## Design

- WALK starts 3 to 7 seconds before the concurrent vehicle green, long enough to cross one lane or get in front of turning vehicles.
- Use accessible pedestrian signals at LPI locations.
- If conflicts remain: part-time or full-time turn prohibitions (always, or on red only), protected-only or protected-permissive turns, or curb extensions. At busy crossings, extend green past the pedestrian clearance so turning drivers find gaps.

Site note: the guidance does not specify signs; NO TURN ON RED is the CA MUTCD R10-11 series.
"""),
 dict(slug="ladot-exclusive-ped-phase-2017", num="CSC Exclusive Pedestrian Phase", title="Exclusive Pedestrian Phase", date="January 2017",
      url="https://ladot.lacity.gov/sites/default/files/2022-08/exclusive-pedestrian-phase-policy-design-guide-final-2017.pdf",
      status="In effect. Listed in the LADOT Technical Reference Library.", supersedes="Not stated.",
      area="Scramble phases, diagonal crossings and NO TURN ON RED", topics=["signals", "crosswalks"],
      kw="exclusive pedestrian phase, pedestrian scramble, Barnes dance, diagonal crosswalk, no turn on red, all-way walk, LADOT Complete Streets Committee",
      body=lambda: """
## When to consider it (all three)

1. Peak hour pedestrians are at least 30% of vehicle volume, or 300 pedestrians per hour use one crosswalk.
2. At least 200 vehicles per hour turn across each of more than one crosswalk in the peak hour.
3. At least three pedestrian and turning-vehicle crashes in the last three years of data.

## Design

- NO TURN ON RED is required on all approaches.
- Diagonal crossings are optional; leaving them out may make sense where the diagonal would be over 100 ft.
- If conflicts are limited to one or two legs (for example a one-way street), consider protected turns or an LPI instead.
- Expect longer cycles here and at coordinated neighbors; re-evaluate protected-permissive left-turn phases that were added for pedestrian conflicts.
- Extra signing may be needed to explain crossing rules; the guidance does not specify signs or markings.
- Avoid near rail crossings or railroad preemption, and near freeway ramps where queues could back onto the mainline.
- Get documented council office support before approval, and notify LAFD, Metro and others after.
"""),
 dict(slug="ladot-ss-plan-checklist-2022", num="S&S Plan Review Checklist", title="Restoration Signing and Striping Plans Design Review Checklist", date="Version 1, August 2022",
      url="https://ladot.lacity.gov/sites/default/files/2026-04/mca-checklist-restoration-signing-and-striping-plans.pdf",
      status="In effect. Current copy posted April 2026.", supersedes="Not stated.",
      area="Signing and striping plan content at 30, 60, 85 and 100 percent", topics=["striping-intersections"],
      kw="signing and striping plan checklist, plan review, 30 60 85 100 percent, title sheet, sign diagram, legend, as-built verification, field photos, comment resolution matrix, 1 inch = 40 feet",
      body=lambda: f"""
## What reviewers check

{table(["Group", "Items"], [
 ["Drafting (1-14)", "LADOT drafting standards and Geometric Plan Sample format; project title above the title block; street name and limits, sheet number, LADOT signature box; LADOT project and drawing numbers; north arrow; scale 1 in = 40 ft; consultant signature block with Civil and Traffic stamps, signed by the Engineer of Record; civil improvements and streetscape dimensions; land use; property lines, limits and right of way; signalized intersections; existing, proposed and removed striping, markings, signs and posts; parking elements (prohibitions, PMZ, colored curb, stall marking)"],
 ["As-built base (15-17)", "Current LADOT and civil base files with field-verified conditions; field-verify anything that affects design; field photos and notes checked"],
 ["Design (18-24)", "CA MUTCD, MPP 531, the Supplemental Street Design Guide and LADOT policies; title sheet with notes, legend, abbreviations, details, typical section, key map and vicinity map; sign diagrams and legend showing existing, removed and proposed signs; coordination with signal plans and other disciplines; agency and council coordination; comment resolution matrix after 30%"],
 ["Supporting documents (25-27)", "Traffic design documentation (for example the Final EIR); preliminary street improvement plans; dated field photos with a key map (Google Street View is not accepted)"],
])}
"""),
 dict(slug="ladot-accessible-parking-2017", num="Accessible Parking Zones", title="Accessible Parking Zones: Basic Placement Facts", date="June 20, 2017",
      url="https://ladot.lacity.gov/sites/default/files/documents/accessible-parking-zones-basic-placement-facts-06-20-2017_1_0.pdf",
      status="In effect (still posted by LADOT).", supersedes="Not stated.",
      area="Blue curb and on-street accessible parking placement", topics=["curb-parking-loading", "accessibility"],
      kw="accessible parking zone, APZ, blue curb, disabled parking, on-street accessible parking, placement, curb ramp, van lift",
      body=lambda: """
## Placement principles

- No one should have to walk or wheel behind a vehicle other than their own.
- Accessible parking zones are not personal spaces and must meet State and federal accessibility guidance.
- A good location has a sidewalk at least 8 ft wide running to the curb (no grass parkway), ramp access to the sidewalk, nothing beside the space that blocks doors or a lift, room for a rear-loading device to reach the corner, and no storm drain inlet in the path.
- Driveways or bus zones between the corner and the first space, grass parkways, poles, inlets and steep roadway slope all limit where a zone can go.

For blue curb paint and signing rules, see the LADOT curb paint page.
"""),
]

# related, already on the site or reference-only
LA_REF = [
 ("MPP 531 Application and Design for Striping, Channelization and Special Signing", "02/2023", f"{BASE}/ladot/mpp-531/", "Lane width table, striping fundamentals, Table 1"),
 ("Marked Crosswalk Guidelines", "rev. October 2020", f"{BASE}/ladot/marked-crosswalks/", "Crosswalk marking criteria"),
 ("Supplemental Street Design Guide", "July 2020", f"{BASE}/ladot/supplemental-street-design-guide/", "Bus bulbs, curb extensions, separated bikeways"),
 ("2028 Games Corridors Design Guide", "2025-2026", f"{BASE}/ladot/games-corridors/", "Games route S&S details"),
 ("Traffic Signal Design Notes", "March 2023", "https://ladot.lacity.gov/sites/default/files/2026-04/traffic-signal-design-notes-03-2023.pdf", "Signal plan sign notes (SN series)"),
 ("Worksite Traffic Control Plans Design Review Checklist", "ver. 1, Aug 2022", "https://ladot.lacity.gov/sites/default/files/2026-04/mca-checklist-worksite-traffic-control-plans-wtcp.pdf", "Temporary striping and WTCP title sheet contents"),
 ("Drafting Standards for Striping and Signal Plans (Final Drafting Manual)", "February 2005", "https://ladot.lacity.gov/sites/default/files/documents/final-drafting-manual.pdf", "Line types, weights, text, title blocks"),
]

# ------------------------------------------------------------------ lane width comparison
LW_ROWS = [
 ["Through lane, low speed", "10.5 ft (20-35 mph, urban)", "10 ft desirable, 9 ft min (35 mph and below)", "11 ft standard; 10 ft desirable min; 9 ft absolute min; 12 ft max (not speed-based)"],
 ["Through lane, 40 mph and up", "10.5-11 ft urban; 11-12 ft suburban", "10-11 ft desirable, 10 ft min", "Same as above"],
 ["Lane next to a bike lane", "No separate value", "11 ft desirable, 10.5 ft min", ""],
 ["Truck or bus route lane", "11 ft min for right-hand and transit-only lanes on large-vehicle routes", "11 ft desirable, 10 ft min", ""],
 ["Left-turn lane", "10.5 ft (urban, 20-35 mph); 11 ft min on large-vehicle routes", "10 ft desirable, 9 ft min", ""],
 ["Two-way left-turn lane", "10.5 ft (urban)", "10 ft desirable, 9 ft min", ""],
 ["Curb lane, no parking", "", "11-13 ft desirable, 10 ft min", ""],
 ["Curb lane with parking", "", "18-20 ft desirable, 18 ft min (17 ft on 25 mph local streets)", "Parking lane 10 ft desirable, 8 ft absolute min"],
 ["Bus lane", "11 ft min (transit-only)", "12 ft desirable, 10 ft min", ""],
 ["Bike lane at curb", "5 ft min, 6-7 ft preferred (no gutter counted)", "6-7 ft with gutter (5 ft min); 5-6 ft without (4 ft min)", ""],
 ["Floor below which it is an exception", "Under 10.5 ft needs documented noncompliance", "Below the minimums above", "9 ft"],
]

# ------------------------------------------------------------------ write pages
def page(it, agency):
    fm = f'''---
title: "{it["num"]}: {it["title"]}"
description: "{agency} {it["num"]} ({it["date"]}). {(it.get("lane") or it.get("area", "")).replace(chr(34), "'")}"
---
'''
    head = f'''<div class="bul-meta">
<div><b>Issued</b> {esc(it["date"])}</div>
<div><b>Status</b> {esc(it["status"])}</div>
<div><b>Supersedes</b> {esc(it["supersedes"])}</div>
<div><b>Official copy</b> <a href="{it["url"]}">{esc(agency)} PDF</a></div>
</div>

'''
    tail = f'''

<p class="bul-foot">Plain-language digest with section references, checked against the official copy on {CHECKED}. Cite the official document, and check the issuing agency's list before relying on it, since bulletins are revised and retired without notice. Back to <a href="{BASE}/bulletins/">all bulletins and policy memos</a> or the <a href="{BASE}/bulletins/lane-widths/">lane width comparison</a>.</p>
'''
    open(f"{OUT}/{it['slug']}.md", "w").write(fm + head + it["body"]().strip() + tail)

for it in CT:
    page(it, "Caltrans")
for it in LA:
    page(it, "LADOT")

ct_rows = [[f'<a href="{BASE}/bulletins/{i["slug"]}/"><b>{esc(i["num"])}</b></a>', esc(i["title"]), esc(i["date"]), esc(i["lane"])] for i in CT]
la_rows = [[f'<a href="{BASE}/bulletins/{i["slug"]}/"><b>{esc(i["title"])}</b></a>', esc(i["date"]), esc(i["area"])] for i in LA]
ref_rows = [[f'<a href="{u}">{esc(t)}</a>', esc(d), esc(n)] for t, d, u, n in LA_REF]
idx = f'''---
title: Bulletins and Policy Memos
description: Caltrans Design Information Bulletins that set lane widths, and LADOT signing and striping policy guidance, currently in effect, with plain-language digests.
---

Design bulletins and policy memos change design values faster than the manuals do. This page lists the ones in effect as of {CHECKED}. Each digest gives the scope, the key values and the section numbers, with a link to the official copy.

<p><a class="cta" href="{BASE}/bulletins/lane-widths/">Lane width comparison: DIB 94, MPP 531 and the City street standards side by side</a></p>

## Caltrans Design Information Bulletins on lane width

Bulletins on the [Caltrans DIB list]({DIB_PAGE}) that set or change lane widths. Caltrans says DIBs may supersede the Highway Design Manual. None of these is marked retired.

{table(["Bulletin", "Title", "Issued", "Lane width"], ct_rows)}

Related Caltrans design memos: [Bikeway Facility Selection Guidance](https://dot.ca.gov/-/media/dot-media/programs/design/documents/dod-bikeway-selection-memo_06302020_signed-a11y.pdf) (June 30, 2020) and [Complete Streets Decision Document implementation](https://dot.ca.gov/-/media/dot-media/programs/design/documents/csdd-memo20210210finalktyt-mdk--a11y.pdf) (February 11, 2021). The HDM lane width standard itself is Index 301.1.

## LADOT signing and striping policy guidance

Complete Streets Committee Policy and Design Guidance and the plan review checklist, from the [LADOT Technical Reference Library](https://ladot.lacity.gov/businesses/technical-reference-library).

{table(["Guidance", "Issued", "Covers"], la_rows)}

### Other LADOT signing and striping references

{table(["Document", "Edition", "Use"], ref_rows)}
'''
open(f"{OUT}/index.md", "w").write(idx)

lw = f'''---
title: Lane Width Comparison
description: Lane widths side by side from Caltrans DIB 94, LADOT MPP 531 and the City of Los Angeles street standards, with the rules that apply on State highways and City streets.
---

Which values apply depends on who owns the street. On a State highway, the HDM (Index 301.1, 12 ft) applies unless a segment uses <a href="{BASE}/bulletins/caltrans-dib-94/">DIB 94</a>, or a project falls under <a href="{BASE}/bulletins/caltrans-dib-79-04/">DIB 79</a>, <a href="{BASE}/bulletins/caltrans-dib-93/">DIB 93</a> or an interchange bulletin. On City of Los Angeles streets, LADOT stripes to <a href="{BASE}/ladot/mpp-531/">MPP 531</a>, and the Bureau of Engineering street standards set the design criteria for new streets.

{table(["Lane", "Caltrans DIB 94 (State highways, opt-in)", "LADOT MPP 531, 02/2023 (striping)", "City of LA BOE E 612.21 (street design)"], [[c or 'Not set' for c in r] for r in LW_ROWS])}

## State highway cases outside DIB 94

{table(["Case", "Lane width", "Source"], [
 ["Standard (new construction and most projects)", "12 ft", "HDM Index 301.1"],
 ["2R and 3R pavement rehabilitation, two- and three-lane conventional highways", "12 ft; urban turn lanes narrower, right-turn lanes to 10 ft when severely constrained (truck study required)", f'<a href="{BASE}/bulletins/caltrans-dib-79-04/">DIB 79-04</a>'],
 ["CAPM restriping", "No values; nonstandard lanes (including narrowing for a bike facility) need a DSDD", f'<a href="{BASE}/bulletins/caltrans-dib-81-03/">DIB 81-03</a>'],
 ["Evacuation routes", "12 ft; 11 ft in rural town centers with low speeds and truck volumes", f'<a href="{BASE}/bulletins/caltrans-dib-93/">DIB 93</a>'],
 ["Single point interchange", "14 ft left-turn lanes through the intersection", f'<a href="{BASE}/bulletins/caltrans-dib-92/">DIB 92</a>'],
 ["Diverging diamond interchange", "Extra width in all lanes for offtracking", f'<a href="{BASE}/bulletins/caltrans-dib-90/">DIB 90</a>'],
])}

## Notes for City projects that touch a State highway

- MPP 531 allows 9 ft interior lanes at 35 mph and below, and 9 ft turn lanes. DIB 94 treats anything under 10.5 ft on a State highway as a documented exception, so a City design that continues onto a State route usually needs wider lanes on the State segment or a DSDD.
- DIB 94 counts a Class II bike lane and on-street parking as shoulder, and expects at least 4 ft of usable right shoulder unless a sidewalk, Class I or Class IV facility is provided.
- Both agencies favor the wider lane on the outside where trucks and buses run. BOE E 612.22 says the same for streets with medians or slow traffic, and the opposite (widest lane near the centerline) on undivided, faster streets.

Sources: Caltrans DIB 94 Section 5.3 and Table 5.3; LADOT MPP 531 (02/2023) Lane Widths; City of Los Angeles Complete Street Design Manual E 612.21 ([online](https://completestreetdesignmanual.engineering.lacity.gov/e-600-cross-section-elements/e-610-streets/e-612-width-standards-and-component-arrangements)). Values checked {CHECKED}.
'''
open(f"{OUT}/lane-widths.md", "w").write(lw)

# ------------------------------------------------------------------ index entries
det = json.load(open("public/data/details.json"))
det = [i for i in det if i.get("type") != "Bulletin"]
lookup = json.load(open("public/data/lookup.json"))
norm = lambda s: re.sub(r"\s+", "", s.upper())
for it, ag in [(i, "Caltrans") for i in CT] + [(i, "LADOT") for i in LA]:
    url = f"{BASE}/bulletins/{it['slug']}/"
    det.append({"src": f"{ag} bulletins", "sg": ag, "type": "Bulletin", "num": it["num"], "title": it["title"], "img": "",
                "url": url, "topics": it["topics"], "kw": it["kw"], "date": it["date"],
                "sum": (it.get("lane") or it.get("area", ""))})
    for k in {norm(it["num"]), norm(it["num"].replace("DIB ", "DIB-")), norm("Caltrans " + it["num"])}:
        ent = [f"{ag} {it['num']}: {it['title']}", url]
        if ent not in lookup.get(k, []):
            lookup.setdefault(k, []).append(ent)
det.append({"src": "Bulletins", "sg": "Caltrans", "type": "Bulletin", "num": "Lane widths", "title": "Lane Width Comparison: DIB 94, MPP 531, BOE E 612",
            "img": "", "url": f"{BASE}/bulletins/lane-widths/", "topics": ["striping-intersections"],
            "kw": "lane width, travel lane width, minimum lane width, 10 foot lane, 11 foot lane, 12 foot lane, turn lane width, bus lane width, curb lane, parking lane width",
            "sum": "Lane widths side by side from Caltrans DIB 94, LADOT MPP 531 and the City of Los Angeles street standards."})
for k in ["LANEWIDTH", "LANEWIDTHS"]:
    ent = ["Lane width comparison (DIB 94, MPP 531, BOE)", f"{BASE}/bulletins/lane-widths/"]
    if ent not in lookup.get(k, []):
        lookup.setdefault(k, []).append(ent)
json.dump(det, open("public/data/details.json", "w"))
json.dump(lookup, open("public/data/lookup.json", "w"))
print("bulletins:", len(CT), "Caltrans,", len(LA), "LADOT")
