"""Place documented field conditions and source illustrations next to the relevant guidance."""
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path

BASE = '/SoCal-Super-Standards'
LADOT_REPORT = 'https://ladot.lacity.gov/sites/default/files/documents/annual-report-year-2023.pdf'
DIB = 'https://dot.ca.gov/-/media/dot-media/programs/design/documents/dib-89-02-final-a11y.pdf'
TRANSIT = {r[0]:r[4] for r in json.loads(Path('data/reference/transit-guides.json').read_text())}


@dataclass(frozen=True)
class Photo:
    file: str
    treatment: str
    place: str
    description: str
    credit: str
    source: str


PHOTOS = {
    'venice': Photo('venice','Post-separated bikeway','Venice Boulevard, Los Angeles',
        'A rider travels next to the curb. Flexible posts stand inside the striped buffer between the bikeway and the adjoining lane.',
        'LADOT 2023 Annual Report · p. 6',LADOT_REPORT+'#page=8'),
    'harvard': Photo('harvard','Mini-roundabout','South Harvard Boulevard, Los Angeles',
        'Yield markings sit on the approach to a raised, planted central island.',
        'Los Angeles Supplemental Street Design Guide · Figure 7-1',
        'https://ladot.lacity.gov/sites/default/files/documents/supplemental-design-guide-073020-final.pdf#page=89'),
    'redondo': Photo('redondo-two-way','Two-way separated bikeway','Redondo Beach',
        'The bicycle crossing continues across the side street. The painted buffer and posts resume beyond the crossing.',
        'Caltrans DIB 89-02 · Photo 2',DIB+'#page=10'),
    'driveway': Photo('la-green-driveway','Bikeway at a driveway','Los Angeles',
        'Green pavement carries the curbside bikeway across the driveway opening. The flexible posts stop before the crossing.',
        'Caltrans DIB 89-02 · Photo 5',DIB+'#page=14'),
    'griffith': Photo('griffith-park-buffer','Buffered bicycle lane','Griffith Park Boulevard, Los Angeles',
        'Hatching separates the bicycle lane from moving traffic. The parking lane is on the rider’s right.',
        'LADOT 2023 Annual Report · p. 8',LADOT_REPORT+'#page=10'),
    'bus-lane': Photo('la-bus-lane','Bus-only lane marking','Los Angeles',
        'A Metro bus travels in a lane marked BUS ONLY. The white lane line separates it from adjacent traffic.',
        'LADOT 2023 Annual Report · p. 7',LADOT_REPORT+'#page=9'),
    'sbx-center': Photo('sbx-center-platform','Center-running sbX station','San Bernardino Valley',
        'The shelter and waiting area sit on a raised median platform between the bus lanes.',
        'Omnitrans Transit Design Guidelines · Figure 4-4',TRANSIT['omnitrans']+'#page=14'),
    'sbx-curb': Photo('sbx-curb-platform','Side-running sbX station','San Bernardino Valley',
        'The platform and shelter run alongside the sidewalk, with a marked boarding edge at the curb.',
        'Omnitrans Transit Design Guidelines · Figure 4-5',TRANSIT['omnitrans']+'#page=14'),
    'mts-platform': Photo('mts-rapid-platform','Rapid bus boarding area','San Diego MTS',
        'The bus doors face a sheltered platform. The stop information is set back from the boarding edge.',
        'MTS Designing for Transit · Figure 2-5',TRANSIT['mts']+'#page=22'),
    'mts-refuge': Photo('mts-crossing-refuge','Pedestrian median refuge','San Diego MTS',
        'The marked crossing passes through a raised median. Detectable warning surfaces mark the edges of the waiting area.',
        'MTS Designing for Transit · Figure 3-1',TRANSIT['mts']+'#page=34'),
    'anaheim': Photo('anaheim-transit-center','Transit center boarding bays','ARTIC, Anaheim',
        'The passenger plaza connects the station entrance to signed bus bays along its outer edge.',
        'OCTA Transit Supportive Design Guidelines · p. 138',TRANSIT['octa']+'#page=148'),
}

# Topic and publication placements name the facility visible in the photograph.
PAGES = {
    'topics/bikeways.md': ('venice','redondo','griffith'),
    'topics/transit.md': ('bus-lane','sbx-center','sbx-curb'),
    'topics/speed-and-calming.md': ('harvard',),
    'topics/striping-intersections.md': ('driveway','griffith'),
    'topics/crosswalks.md': ('mts-refuge',),
    'topics/accessibility.md': ('mts-refuge','mts-platform'),
    'transit/octa/index.md': ('anaheim',),
    'transit/mts/index.md': ('mts-platform','mts-refuge'),
    'transit/omnitrans/index.md': ('sbx-center','sbx-curb'),
    'bulletins/ladot-bikeway-marking-2022.md': ('driveway',),
    'bulletins/bikeway-design-comparison.md': ('redondo','griffith'),
    'bulletins/ladot-lane-reconfiguration-2023.md': ('venice',),
}


def field_card(key, home=False):
    photo = PHOTOS[key]
    image = BASE+'/figs/projects/'+photo.file+'.webp'
    if home:
        image = BASE+'/thumbs/figs/projects/'+photo.file+'.webp'
        return (f'<figure class="home-photo"><img decoding="async" src="{image}" alt="{escape(photo.description)}" />'
                f'<figcaption><strong>{escape(photo.treatment)}</strong><span>{escape(photo.place)}</span>'
                f'<a href="{escape(photo.source)}">{escape(photo.credit)}</a></figcaption></figure>')
    return (f'<figure><a href="{image}"><img loading="lazy" decoding="async" src="{image}" alt="{escape(photo.description)}" /></a>'
            f'<figcaption><strong>{escape(photo.treatment)}</strong> · {escape(photo.place)}<br/>{escape(photo.description)}'
            f'<a href="{escape(photo.source)}">{escape(photo.credit)}</a></figcaption></figure>')


def insert_gallery(path, section):
    source = path.read_text()
    pos = source.find('\n## ')
    path.write_text(source[:pos]+section+source[pos:] if pos>=0 else source+section)


def place(root):
    for filename, keys in PAGES.items():
        path = root/filename
        cards = ''.join(field_card(key) for key in keys)
        insert_gallery(path, '\n\n## Local project examples\n\n<div class="project-gallery">'+cards+'</div>\n\n')

    street = 'urban-street-design-guide/'
    bikeway = 'urban-bikeway-design-guide/designing-safe-intersections/design-strategies-for-signalized-intersections/'
    nacto = {
        'bus-bulb': ('Bus bulb','The sidewalk extends to the travel lane at the shelter. Trace the boarding path from the shelter to the front and rear doors.',street+'street-design-elements/curb-extensions/bus-bulbs/'),
        'four-lane-refuge': ('Four-lane crossing with a refuge','The four-lane plan places a waiting area at the center of the marked crossing. Follow each direction of traffic up to the island.',street+'intersection-design-elements/crosswalks-and-crossings/pedestrian-safety-islands/'),
        'protected-corner': ('Protected intersection corner','The corner island separates the bikeway from turning vehicles. Follow the green bicycle crossing beside the pedestrian crosswalk.',bikeway),
        'protected-plan': ('Protected intersection plan','The overhead view shows how corner islands, set-back bicycle crossings and pedestrian crossings connect across the four approaches.',bikeway),
    }
    for page, keys in {
        'guides/nacto-urban-street': ('four-lane-refuge','bus-bulb'),
        'guides/nacto-urban-bikeway': ('protected-corner','protected-plan'),
        'topics/transit': ('bus-bulb',), 'topics/crosswalks': ('four-lane-refuge',),
        'topics/bikeways': ('protected-corner',), 'topics/signals': ('protected-plan',),
        'topics/accessibility': ('four-lane-refuge',),
    }.items():
        cards = []
        for key in keys:
            title, guidance, slug = nacto[key]
            image = BASE+'/figs/nacto/'+key+'.webp'
            url = 'https://nacto.org/publication/'+slug
            cards.append(f'<figure><a href="{image}"><img src="{image}" loading="lazy" decoding="async" alt="{escape(title)}" /></a>'
                         f'<figcaption><strong>{title}</strong> · {guidance}<a href="{url}">NACTO · original illustration and guidance</a></figcaption></figure>')
        insert_gallery(root/(page+'.md'), '\n\n## NACTO design guidance\n\n<div class="project-gallery nacto-gallery">'+''.join(cards)+'</div>\n\n')
