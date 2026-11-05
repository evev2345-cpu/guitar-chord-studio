"""Validated fret geometry; numbering is never inferred from list position."""
import math
import numpy as np


def resolve_frets(result, width=800, height=150, *, board_boundaries=False):
    records = {}
    for item in result['frets']:
        number = item.get('fret_num')
        if type(number) is not int or number < 0 or number > 36:
            raise ValueError('fret_num must be an integer between 0 and 36')
        if number in records:
            raise ValueError(f'Duplicate fret number: {number}')
        record = dict(fret_num=number, occluded=bool(item.get('occluded', False)),
                      interpolated=False)
        if record['occluded']:
            record.update(source='occluded', reason=item.get('reason', 'unknown'))
        else:
            points = []
            for key in ('p1', 'p2'):
                point = item.get(key)
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError(f'Fret {number}: missing or malformed {key}')
                if any(type(v) not in (int, float) or not math.isfinite(v)
                       or not 0 <= v <= 1000 for v in point):
                    raise ValueError(f'Fret {number}: invalid coordinates')
                points.append((point[1] * width / 1000, point[0] * height / 1000))
            (x1, y1), (x2, y2) = points
            if abs(y2-y1) <= abs(x2-x1):
                raise ValueError(f'Fret {number}: segment must be distinct and steep')
            m = (x2-x1)/(y2-y1)
            b = x1-m*y1
            record.update(source='observed', xt=b, xb=b+m*height,
                          m=m, b=b, raw_p1=points[0], raw_p2=points[1])
        records[number] = record
    # Extrapolating a short visible segment can leave the image. Preserve the
    # original geometry and never pass a materially out-of-board line to cells.
    tolerance = width * 0.005
    for record in records.values():
        if 'xt' not in record:
            continue
        xt, xb = record['xt'], record['xb']
        excess = max(0, -xt, -xb, xt-width, xb-width)
        if excess:
            record['original_endpoints'] = [xt, xb]
            if excess <= tolerance:
                record.update(xt=min(width,max(0,xt)), xb=min(width,max(0,xb)),
                              geometry_adjustment='boundary_clip')
                record.update(m=(record['xb']-record['xt'])/height, b=record['xt'])
            else:
                for key in ('xt','xb','m','b'):
                    record.pop(key, None)
                record.update(source='rejected', reason='line extrapolates outside board')
    if board_boundaries:
        add_boundary_estimates(records, result.get('last_fret_num'), width, height)
    observed = sorted(n for n, r in records.items() if 'xt' in r)
    for left, right in zip(observed, observed[1:]):
        a, b = records[left], records[right]
        if a['xt'] >= b['xt'] or a['xb'] >= b['xb']:
            raise ValueError(f'Crossed or reversed fret order: {left}, {right}')
        count = right-left
        r = 2 ** (-1/12)
        total = sum(r**i for i in range(count))
        accum = 0
        for offset in range(1, count):
            accum += r**(offset-1)
            number = left+offset
            record = records.setdefault(number, dict(
                fret_num=number, occluded=False, reason='missing detection'))
            ratio = accum/total
            xt = a['xt']+(b['xt']-a['xt'])*ratio
            xb = a['xb']+(b['xb']-a['xb'])*ratio
            if record.get('source') == 'boundary_estimated':
                continue
            record.update(source='interpolated', interpolated=True,
                          anchors=[left, right], xt=xt, xb=xb,
                          m=(xb-xt)/height, b=xt)
    # Gaps without a validated boundary or two anchors remain unresolved.
    return [records[n] for n in sorted(records)]


def add_boundary_estimates(records, claimed_last, width, height):
    """Use the detected nut/last-wire crop contract, never image evidence claims.

    Fit a projective transform of 12-TET positions to account for residual
    perspective. An end number is accepted only when enough observed wires
    predict that boundary consistently at both board edges.
    """
    observed=[r for r in records.values() if r.get('source')=='observed' and 'xt' in r]
    if len(observed) < 6:
        return
    def put(number, x, evidence):
        record=records.setdefault(number,dict(fret_num=number,occluded=True,reason='not observed'))
        if 'xt' in record:
            return
        record.update(source='boundary_estimated', estimated=True, interpolated=False,
                      xt=float(x),xb=float(x),m=0.0,b=float(x),
                      boundary_evidence=evidence)
    # Nut identity comes from stage-1 semantic corners, not extrapolated spacing.
    if 0 not in records or 'xt' not in records[0]:
        put(0,0,'stage1 nut corners; not a visible wire measurement')
    t=np.array([1-2**(-r['fret_num']/12) for r in observed])
    fits=[]
    for edge in ('xt','xb'):
        x=np.array([r[edge]/width for r in observed])
        a,b,c=np.linalg.lstsq(np.column_stack([t,np.ones(len(t)),-x*t]),x,rcond=None)[0]
        def predict(n, a=a,b=b,c=c):
            v=1-2**(-n/12)
            return width*(a*v+b)/(c*v+1)
        residual=float(np.mean(abs(np.array([predict(r['fret_num']) for r in observed])-x*width)))
        if not math.isfinite(residual) or residual > width*0.004:
            return
        fits.append(predict)
    highest=max(r['fret_num'] for r in observed)
    candidates=[]
    for number in range(highest, min(highest+7,36)+1):
        deviations=[]
        for predict in fits:
            positions=[predict(n) for n in range(number+1)]
            if not all(math.isfinite(x) for x in positions) or any(b<=a for a,b in zip(positions,positions[1:])):
                break
            spacing=predict(number)-predict(number-1)
            deviations.append(abs(predict(number)-width)/spacing)
        if len(deviations)==2 and max(deviations)<=0.65:
            candidates.append(number)
    # Ambiguity is retained rather than silently choosing a terminal number.
    if len(candidates)!=1:
        return
    last=candidates[0]
    if claimed_last is not None and (type(claimed_last) is not int or claimed_last!=last):
        return
    if any(n>last and 'xt' in r for n,r in records.items()):
        return
    put(last,width,'stage1 last-wire corners + projective spacing agreement')


def build_cells(frets):
    wires = sorted((f for f in frets if 'xt' in f), key=lambda f: f['fret_num'])
    return [(a,b) for a,b in zip(wires,wires[1:])
            if b['fret_num'] == a['fret_num']+1]
