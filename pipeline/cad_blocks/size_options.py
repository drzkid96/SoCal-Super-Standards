"""Combine an issued sign face with separate, explicitly dimensioned drawing observations."""
import hashlib
import json
from pathlib import Path


def collect(work, batch_names):
    def load(path):
        return json.loads(path.read_text())

    official=load(work/'block-inputs'/'official-faces.json')
    published={r['code'].casefold():r for r in official}
    canonical=load(work/'cad-source-official'/'manifest.json')['records']
    dims={r['code'].casefold():(r['width'],r['height']) for r in canonical if not r.get('observationIds') and r['sizeStatus']!='Reference size unknown'}
    options={}
    for batch in batch_names:
        for r in load(work/batch/'manifest.json')['records']:
            code=r['code'].casefold()
            if code not in published or r['sizeStatus']!='source dimensions' or r.get('historicalLegend'):
                continue
            w,h=r['width'],r['height']
            if (w,h)==dims.get(code):
                continue
            k=(code,w,h)
            if k not in options:
                record=published[code]
                parts=f'{w:.4f}-{h:.4f}'.replace('.','p')
                options[k]=dict(record,id=record['id']+'-size-'+parts,verifiedBoundsInches=[w,h],
                                verifiedBoundsBasis=r['sizeBasis'],sizeReference=r['sizeReference'],observationIds=[],
                                notes='Issued artwork sized to the cited drawing dimension. '+record.get('notes',''))
            options[k]['observationIds'] += [o['id'] for o in r['observations']]
    target=work/'block-inputs'/'official-size-options.json'
    target.write_text(json.dumps(list(options.values()),indent=1)+'\n')
    return len(options)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('sources', nargs='+')
    args=parser.parse_args()
    print(collect(args.work,args.sources))
