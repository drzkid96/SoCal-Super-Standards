"""Reproduce reviewed sign-face crops from converted source DXFs and recorded entity handles."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, svg
from ezdxf.fonts import fonts
from ezdxf.math import BoundingBox2d
import fitz
from PIL import Image

CATALOG = Path('data/reference/plan-examples/cad-sign-art.json')
PUBLIC = Path('public')


def render(drawing, context, record):
    entities = []
    for handle in record['entities']:
        entity = drawing.entitydb[handle]
        if entity.dxftype() == 'MTEXT' and not fonts.font_manager.has_font('arialnb.ttf'):
            # Preserve inline bold/italic, tracking, and alignment from the source.
            # The metric-compatible narrow font is bundled in the build workspace.
            if 'Arial Narrow|' in entity.text and fonts.font_manager.has_font('LiberationSansNarrow-Bold.ttf'):
                entity = entity.copy()
                entity.text = entity.text.replace('Arial Narrow|', 'Liberation Sans Narrow|')
        entities.append(entity)
    backend = svg.SVGBackend()
    settings = config.Configuration(background_policy=config.BackgroundPolicy.WHITE,
                                    color_policy=config.ColorPolicy.BLACK,
                                    lineweight_policy=config.LineweightPolicy.RELATIVE)
    frontend = Frontend(context, backend, config=settings)
    frontend.set_background('#ffffff')
    frontend.draw_entities(entities)
    frontend.pipeline.finalize()
    boundary = BoundingBox2d(record['bounds']) if 'bounds' in record else backend.player().bbox()
    width, height = boundary.size
    page = layout.Page(110*width/max(width,height)+4,110*height/max(width,height)+4,
                       margins=layout.Margins.all(2))
    vector = backend.get_string(page, render_box=boundary,
                                settings=layout.Settings(output_coordinate_space=22000, output_layers=False))
    # MuPDF's SVG importer can ignore CSS classes inside defs. Set literal drawing
    # styles on each path so unfilled curves stay unfilled when rasterizing.
    xml = ET.fromstring(vector)
    styles = {}
    for rule in re.finditer(r'\.(C\d+)\s*\{([^}]+)\}',vector):
        attrs = {k.strip():v.strip() for k,v in (t.split(':',1) for t in rule[2].split(';') if ':' in t)}
        if attrs.get('stroke-width') == 'none':
            del attrs['stroke-width']
        elif 'stroke-width' in attrs:
            attrs['stroke-width'] = str(max(float(attrs['stroke-width']),60))
        styles[rule[1]] = attrs
    for node in xml.iter():
        if node.get('class') in styles:
            node.attrib.update(styles[node.get('class')])
    ET.register_namespace('','http://www.w3.org/2000/svg')
    with fitz.open(stream=ET.tostring(xml),filetype='svg') as document:
        sheet = document[0]
        scale = 576/max(sheet.rect.width,sheet.rect.height)
        pixels = sheet.get_pixmap(matrix=fitz.Matrix(scale,scale), alpha=False)
        return Image.open(BytesIO(pixels.tobytes('png'))).convert('RGB')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dxf_folder', type=Path, help='Directory containing geo.dxf and pico.dxf')
    parser.add_argument('--font-folder', type=Path, help='Directory with Arial Narrow or Liberation Sans Narrow Bold')
    args = parser.parse_args()
    if args.font_folder:
        fonts.font_manager.scan_folder(args.font_folder)
    records = json.loads(CATALOG.read_text())
    for series in sorted({r['drawing'] for r in records}):
        drawing = ezdxf.readfile(args.dxf_folder/(series+'.dxf'))
        context = RenderContext(drawing)
        for style in drawing.styles:
            original = style.dxf.font.lower()
            if original not in {'arialn.ttf','arialnb.ttf'}:
                continue
            fallback = 'LiberationSansNarrow-Bold.ttf' if original == 'arialnb.ttf' else 'LiberationSansNarrow-Regular.ttf'
            for font in (original, fallback):
                if fonts.font_manager.has_font(font):
                    context.fonts[style.dxf.name.lower()] = fonts.font_manager.get_font_face(font)
                    break
        for record in records:
            if record['drawing'] != series:
                continue
            picture = render(drawing, context, record)
            target = PUBLIC/record['image'].lstrip('/')
            target.parent.mkdir(parents=True,exist_ok=True)
            pending = target.with_suffix('.tmp')
            picture.save(pending,'WEBP',lossless=True,method=5)
            pending.replace(target)
            record['width'], record['height'] = picture.size
    CATALOG.write_text(json.dumps(records,ensure_ascii=False,separators=(',',':'))+'\n')


if __name__ == '__main__':
    main()
