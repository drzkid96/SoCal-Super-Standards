"""Place documented Southern California field examples on related landing pages."""
from html import escape

BASE = '/SoCal-Super-Standards'
DIB = BASE+'/bulletins/caltrans-dib-89-02/'
PROJECTS = {
 'venice': ('projects/venice.webp', 'Venice Boulevard, Los Angeles', 'Safety and Mobility Project', 'LADOT project story', 'https://ladot.lacity.gov/dotnews/ladot-and-metro-celebrate-completion-venice-blvd-safety-and-mobility-project'),
 'harvard': ('projects/harvard.webp', 'South Harvard Boulevard, Los Angeles', 'Mini-roundabout with a raised center island', 'City design guide · Figure 7-1', 'https://ladot.lacity.gov/sites/default/files/documents/supplemental-design-guide-073020-final.pdf#page=89'),
 'redondo': ('bulletins/dib-89-02/photo-2-redondo-two-way.webp', 'Redondo Beach', 'Two-way separated bikeway', 'Caltrans DIB 89-02 · Photo 2', DIB),
 'driveway': ('bulletins/dib-89-02/photo-5-la-driveway-green.webp', 'Los Angeles', 'Green bikeway markings across driveway access', 'Caltrans DIB 89-02 · Photo 5', DIB),
}
PAGES = {
 'index.mdx': ('venice','harvard','redondo'), 'ladot/index.md': ('venice','harvard'),
 'topics/bikeways.md': ('redondo','driveway'), 'topics/transit.md': ('venice',),
 'topics/speed-and-calming.md': ('harvard',), 'topics/striping-intersections.md': ('driveway',),
 'ladot/games-corridors/index.md': ('driveway','redondo'), 'ladot/supplemental-street-design-guide/index.md': ('harvard',),
 'guides/nacto-urban-bikeway.md': ('redondo','driveway'), 'guides/nacto-urban-street.md': ('venice','harvard'),
}

def place(root):
    for filename, keys in PAGES.items():
        path = root/filename
        source = path.read_text()
        cards = []
        for key in keys:
            image,place_name,caption,credit,url = PROJECTS[key]
            src = BASE+'/figs/'+image
            cards.append(f'<figure><a href="{src}"><img loading="lazy" src="{src}" alt="{escape(caption)} in {escape(place_name)}" /></a><figcaption><strong>{place_name}</strong><br/>{caption}<a href="{url}">{credit}</a></figcaption></figure>')
        gallery = '\n\n## Local project examples\n\n<div class="project-gallery">' + ''.join(cards) + '</div>\n\n'
        pos = source.index('<nav class="home-jumps"') if filename=='index.mdx' else source.find('\n## ')
        if filename=='index.mdx': pos=source.index('</nav>',pos)+len('</nav>')
        path.write_text(source[:pos]+gallery+source[pos:] if pos>=0 else source+gallery)

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
