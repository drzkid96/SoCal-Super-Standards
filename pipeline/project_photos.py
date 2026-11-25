"""Place documented Southern California field examples on related landing pages."""
from html import escape

BASE = '/SoCal-Super-Standards'

def place(root):
    nacto = {
        'bus-bulb': ('Bus bulbs', 'Extending the boarding area to the travel lane lets a bus serve the stop without pulling out and merging back into traffic. Follow the passenger route from sidewalk to door, then check how the stop interacts with the bikeway.', 'urban-street-design-guide/street-design-elements/curb-extensions/bus-bulbs/'),
        'refuge': ('Pedestrian safety islands', 'The island gives people a place to wait between traffic streams. Trace each crossing leg separately and check whether a person waiting on the island can see approaching traffic.', 'urban-street-design-guide/intersection-design-elements/crosswalks-and-crossings/pedestrian-safety-islands/'),
        'intersection': ('Signalized bikeway intersections', 'Use the chart to compare dedicated and protected intersection layouts. Review corner geometry, crossing setback and signal phasing together when resolving conflicts between turning drivers and people riding through.', 'urban-bikeway-design-guide/designing-safe-intersections/design-strategies-for-signalized-intersections/'),
    }
    for page, keys in {
        'guides/nacto-urban-street': ['refuge','bus-bulb'],
        'guides/nacto-urban-bikeway': ['intersection'],
        'topics/transit': ['bus-bulb'], 'topics/crosswalks': ['refuge'],
        'topics/bikeways': ['intersection'], 'topics/signals': ['intersection'],
        'topics/accessibility': ['refuge'],
    }.items():
        path = root/(page+'.md')
        source = path.read_text()
        cards = []
        for key in keys:
            title, guidance, slug = nacto[key]
            image = BASE+'/figs/nacto/'+key+'.webp'
            url = 'https://nacto.org/publication/'+slug
            cards.append(f'<figure><a href="{image}"><img src="{image}" loading="lazy" alt="NACTO illustration of {title.lower()}" /></a><figcaption><strong>{title}</strong> · {guidance}<a href="{url}">NACTO · original illustration and design guidance</a></figcaption></figure>')
        section = '\n\n## NACTO design guidance\n\n<div class="project-gallery nacto-gallery">'+''.join(cards)+'</div>\n\n'
        pos = source.find('\n## ')
        path.write_text(source[:pos]+section+source[pos:] if pos>=0 else source+section)
