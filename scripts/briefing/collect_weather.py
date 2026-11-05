#!/usr/bin/env python3
"""기상 데이터 수집 + 보드 HTML 생성.
필요: 환경변수 KMA_SERVICE_KEY (기상청 API허브 authKey). 출력: weather.json
사용: python3 collect_weather.py [출력경로]
"""
import json, os, re, subprocess, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

KEY = os.environ.get('KMA_SERVICE_KEY', '')
HUB = 'https://apihub.kma.go.kr/api/typ02/openApi/AmmIwxxmService'
NOAA = 'https://aviationweather.gov/api/data'
I = '{http://icao.int/iwxxm/2023-1}'; G = '{http://www.opengis.net/gml/3.2}'; A = '{http://www.aixm.aero/schema/5.1.1}'
NOW = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC naive
KST = timedelta(hours=9)
DOM = [('제주', 'RKPC'), ('김해', 'RKPK'), ('김포', 'RKSS'), ('인천', 'RKSI')]
WX = {'RA': '비', 'DZ': '이슬비', 'BR': '박무', 'FG': '안개', 'HZ': '연무', 'TS': '뇌우', 'SN': '눈', 'SH': '소나기', 'GR': '우박', 'FU': '연기'}
DIR8 = ['북', '북동', '동', '남동', '남', '남서', '서', '북서']


def curl(url, timeout=25):
    try:
        return subprocess.run(['curl', '-sS', '-m', str(timeout), url], capture_output=True, text=True, timeout=timeout + 5).stdout
    except Exception:
        return ''


def hub(svc, **p):
    q = '&'.join(f'{k}={v}' for k, v in p.items())
    r = None
    for _ in range(5):  # 일시적 응답 실패 재시도
        txt = curl(f'{HUB}/{svc}?pageNo=1&dataType=XML&{q}&authKey={KEY}')
        try:
            r = ET.fromstring(txt); break
        except Exception:
            import time; time.sleep(2)
    if r is None:
        return None, '응답 파싱 실패'
    if r.tag == 'result':
        return None, r.findtext('message') or 'error'
    return r, None


def kst(s):  # 'YYYY-MM-DDTHH:MM..Z' -> naive KST datetime
    return datetime.strptime(s[:16], '%Y-%m-%dT%H:%M') + KST


def num(e):
    if e is None or e.text is None: return None
    try: return float(e.text)
    except ValueError: return None


def kt(e):
    v = num(e)
    if v is None: return None
    return v * 1.944 if (e.get('uom') or '').startswith('m/s') or e.get('uom') == 'm/s' else v


def wind(x):
    return (num(next(x.iter(I + 'meanWindDirection'), None)), kt(next(x.iter(I + 'meanWindSpeed'), None)), kt(next(x.iter(I + 'windGustSpeed'), None)))


def vis_m(x):
    return num(next(x.iter(I + 'prevailingVisibility'), None))


def parse_metar(r):
    it = r.find('.//item') if r is not None else None
    x = None if it is None else (it.find('.//' + I + 'METAR') or it.find('.//' + I + 'SPECI'))
    if x is None: return None
    t = x.find('.//' + I + 'observationTime//' + G + 'timePosition')
    d, s, g = wind(x)
    wx = [h.get('{http://www.w3.org/1999/xlink}href', '').rsplit('/', 1)[-1] for h in x.iter(I + 'presentWeather')]
    cl = []
    for cll in x.iter(I + 'CloudLayer'):
        am = cll.find(I + 'amount'); b = cll.find(I + 'base')
        if am is not None and b is not None:
            cl.append((am.get('{http://www.w3.org/1999/xlink}href', '').rsplit('/', 1)[-1], num(b)))
    ws = [e.text for e in x.iter(I + 'runway')]
    cavok = x.find('.//' + I + 'MeteorologicalAerodromeObservation')
    cavok = cavok is not None and cavok.get('cloudAndVisibilityOK') == 'true'
    return dict(t=kst(t.text), dir=d, spd=s, gust=g, vis=vis_m(x), wx=wx, cloud=cl, ws=ws, cavok=cavok)


def parse_taf(r):
    it = r.find('.//item') if r is not None else None
    x = None if it is None else it.find('.//' + I + 'TAF')
    if x is None: return None
    vb = next(x.iter(G + 'beginPosition')); ve = next(x.iter(G + 'endPosition'))
    def grp(e, ind):
        tb = next(e.iter(G + 'beginPosition'), None); te = next(e.iter(G + 'endPosition'), None)
        d, s, g = wind(e)
        return dict(ind=ind, b=kst(tb.text) if tb is not None else None, e=kst(te.text) if te is not None else None, dir=d, spd=s, gust=g, vis=vis_m(e))
    base = x.find('.//' + I + 'baseForecast')
    out = dict(valid=(kst(vb.text), kst(ve.text)), issue=kst(x.find(I + 'issueTime//' + G + 'timePosition').text),
               base=grp(base, 'BASE'), changes=[])
    for c in x.iter(I + 'changeForecast'):
        ind = None
        for el in c.iter():
            if el.get('changeIndicator'): ind = el.get('changeIndicator'); break
        out['changes'].append(grp(c, ind or 'BECOMING'))
    return out


def level(spd, gust, vis, ws=False, ts=False):
    spd = spd or 0; gust = gust or 0
    if gust >= 30 or (vis is not None and vis < 800) or (ws and gust >= 20): return 'R'
    if gust >= 20 or spd >= 15 or (vis is not None and vis < 5000) or ws or ts: return 'A'
    return 'G'


def taf_state_at(taf, t0, t1):
    """블록 [t0,t1) 상태. BECMG: 시작이 블록 시작 이전이면 반영, 블록 안에서 시작하면 변화 전/후 중 나쁜 쪽. TEMPO: 구간이 겹치면 반영."""
    def apply(cur, c):
        n = dict(cur)
        if c['dir'] is not None:
            n['dir'], n['spd'], n['gust'] = c['dir'], c['spd'], c['gust']
        if c['vis'] is not None: n['vis'] = c['vis']
        return n
    cur = dict(spd=taf['base']['spd'], gust=taf['base']['gust'], vis=taf['base']['vis'], dir=taf['base']['dir'])
    cands = []
    for c in sorted([c for c in taf['changes'] if c['ind'].startswith('BECOM')], key=lambda z: z['b']):
        if c['b'] <= t0: cur = apply(cur, c)
        elif c['b'] < t1: cands.append(apply(cur, c))
    for c in taf['changes']:
        if not c['ind'].startswith('BECOM') and c['b'] < t1 and c['e'] > t0:
            cands.append(apply(cur, c))
    st = [level(x['spd'], x['gust'], x['vis']) for x in [cur] + cands]
    return min(st, key=lambda z: 'RAG'.index(z))


def dtxt(d):
    return '-' if d is None else f'{int(round(d)):03d}°({DIR8[int(((d % 360) + 22.5) // 45) % 8]})'


def vtxt(v):
    return '정보 없음' if v is None else (f'{v/1000:.0f}km+' if v >= 9999 else f'{int(v):,}m')


def wxtxt(m):
    w = []
    for c in m['wx']:
        pre = '약한 ' if c.startswith('-') else ('강한 ' if c.startswith('+') else '')
        for k, v in WX.items():
            if k in c: w.append(pre + v)
    return '·'.join(dict.fromkeys(w))


def low_ceiling(m):
    c = [b for a, b in m['cloud'] if a in ('BKN', 'OVC') and b is not None]
    return min(c) if c else None


def noaa_metar(ids):
    out = {}
    for ln in curl(f'{NOAA}/metar?ids={ids}&format=raw&hours=2').splitlines():
        p = ln.split()
        if len(p) > 2 and p[0] in ('METAR', 'SPECI') and p[1] not in out: out[p[1]] = ln
    return out


def mini_obs(line):
    m = re.search(r'\b(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT', line)
    v = re.search(r'KT (?:\d{3}V\d{3} )?(\d{4}|CAVOK)', line)
    cb = re.findall(r'\b(?:FEW|SCT|BKN)\d{3}(?:CB|TCU)', line)
    def vf(x):
        return '10km+' if x == '9999' else ('CAVOK' if x == 'CAVOK' else (f'{int(x):,}m' if x.isdigit() else x))
    return dict(dir=m.group(1) if m else '-', spd=m.group(2).lstrip('0') or '0' if m else '-', gust=m.group(4) if m and m.group(4) else None,
                vis=(vf(v.group(1)) if v else '-'), cb=cb, t=re.search(r'\d{6}Z', line).group(0) if re.search(r'\d{6}Z', line) else '')


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'weather.json'
    gaps = []
    nowk = NOW + KST
    b0 = (nowk.hour // 3) * 3
    start = nowk.replace(minute=0, second=0, microsecond=0, hour=b0)
    blocks = [start + timedelta(hours=3 * i) for i in range(8)]
    labels = [f'{b.hour:02d}' for b in blocks]
    span = f'{blocks[0]:%d일 %H시} → {blocks[-1] + timedelta(hours=3):%d일 %H시} (KST, 3시간 단위)'
    if not KEY: gaps.append('KMA_SERVICE_KEY 미설정')
    cards, summ = [], {}
    for name, ic in DOM:
        rm, em = hub('getMetar', numOfRows=1, icao=ic); rt, et = hub('getTaf', numOfRows=1, icao=ic)
        m = parse_metar(rm); taf = parse_taf(rt)
        if em: gaps.append(f'{ic} METAR: {em}')
        if et: gaps.append(f'{ic} TAF: {et}')
        if not m:
            cards.append(acard(name, ic, '확인 불가', 'N', '실황 확인 불가', '실황 확인 불가', '기상청 API 응답 없음', ['N'] * 8, labels, span)); summ[ic] = dict(state='N', head='확인 불가', sub=''); continue
        ws = bool(m['ws']); ts = any('TS' in c for c in m['wx'])
        st = level(m['spd'], m['gust'], m['vis'], ws, ts)
        tl = [taf_state_at(taf, b, b + timedelta(hours=3)) for b in blocks] if taf else ['N'] * 8
        worst_tl = min(tl, key=lambda z: 'RAG'.index(z)) if taf else st
        ctext = wxtxt(m); lc = low_ceiling(m)
        now_line = f'{m["t"]:%H:%M} 실황 · 풍향 {dtxt(m["dir"])} {m["spd"]:.0f}kt' + (f', 순간 {m["gust"]:.0f}kt' if m['gust'] else '') + ('' if m['cavok'] else f' · 시정 {vtxt(m["vis"])}') + (f' · {ctext}' if ctext else '') + (f' · 운고 {lc:.0f}ft' if lc else '') + (' · CAVOK' if m['cavok'] else '')
        head = []
        if m['gust'] and m['gust'] >= 20: head.append('돌풍')
        if ws: head.append(f'윈드시어({"·".join(m["ws"])})')
        if m['vis'] is not None and m['vis'] < 5000: head.append('저시정' + (f'({ctext})' if ctext else ''))
        head = ' + '.join(head) if head else ('양호' if st == 'G' else '주의')
        later = [i for i, s in enumerate(tl[1:], 1) if s != 'G'] if (st == 'G' and taf) else []
        state_text = STATE_LABEL[st] if not (st == 'G' and later) else '양호→주의'
        k = st if not (st == 'G' and later) else 'G'
        if st == 'G' and later: head = f'현재 양호, {blocks[later[0]]:%d일 %H시}경부터 주의 예보'
        note = '확인 불가(TAF 없음)'
        if taf:
            parts = []
            for c in taf['changes']:
                bits = []
                if c['dir'] is not None: bits.append(f'풍향 {c["dir"]:03.0f}° {c["spd"]:.0f}kt' + (f' 순간 {c["gust"]:.0f}kt' if c['gust'] else ''))
                if c['vis'] is not None: bits.append(f'시정 {vtxt(c["vis"])}')
                if bits and c['b'] and c['e']:
                    tagt = 'TEMPO' if not c['ind'].startswith('BECOM') else '변화'
                    parts.append(f'<b>{c["b"]:%d일 %H~}{c["e"]:%H시}</b> {tagt} ' + ' / '.join(bits))
            b = taf['base']
            note = f'TAF({taf["issue"]:%d일 %H:%M} 발표) 기본: 풍향 {b["dir"]:03.0f}° {b["spd"]:.0f}kt' + (f' 순간 {b["gust"]:.0f}kt' if b['gust'] else '') + f' 시정 {vtxt(b["vis"])}' + (' → ' + ' → '.join(parts) if parts else '')
        cards.append(acard(name, ic, state_text, k, now_line, head, note, tl, labels, span))
        summ[ic] = dict(state=st, label=state_text, head=head, now=now_line, name=name)
    rows = ''.join(f'<tr>{cards[i]}{cards[i+1]}</tr>' for i in (0, 2))
    dom_html = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'
    # 대구 + 인천 FIR SIGMET
    nm = noaa_metar('RKTN,RPLL,RPVM,VVTS,VVDN,VTBS,WSSS,WMKK')
    tn = mini_obs(nm['RKTN']) if 'RKTN' in nm else None
    extra = ''
    if tn:
        tk = tn['t'][2:4] + ':' + tn['t'][4:6] if tn['t'] else ''
        try:
            dt = NOW.replace(day=int(tn['t'][:2]), hour=int(tn['t'][2:4]), minute=int(tn['t'][4:6]), second=0, microsecond=0) + KST; tk = f'{dt:%H:%M}'
        except Exception: pass
        extra += f'<b style="color:#B45309;">대구 RKTN</b> {tk} 실황 · 풍향 {tn["dir"]}° {tn["spd"]}kt · 시정 {tn["vis"]} · NOAA 중계 &nbsp;|&nbsp; '
    rs, es = hub('getSigmet', numOfRows=10)
    kr_sig = []
    if rs is not None:
        for it in rs.findall('.//item'):
            x = it.find('.//' + I + 'SIGMET')
            if x is None: continue
            vb = kst(next(x.iter(G + 'beginPosition')).text); ve = kst(next(x.iter(G + 'endPosition')).text)
            ph = x.find('.//' + I + 'phenomenon'); ph = ph.get('{http://www.w3.org/1999/xlink}href', '').rsplit('/', 1)[-1] if ph is not None else ''
            kr_sig.append((vb, ve, ph))
    elif es: gaps.append(f'SIGMET: {es}')
    if kr_sig:
        extra += '인천 FIR SIGMET: ' + ', '.join(f'{v1:%d일 %H:%M}~{v2:%H:%M} {ph.replace("_", " ")} → <b>{"발효 중" if v1 <= nowk <= v2 else ("종료" if v2 < nowk else "예정")}</b>' for v1, v2, ph in kr_sig)
    else:
        extra += '인천 FIR SIGMET: 발표 없음'
    dom_html += f'<div style="font-size:12px;color:#374151;margin-top:4px;">{extra}</div>'
    dom_html += '<div style="font-size:11.5px;color:#6B7280;margin-top:3px;">실황·예보·SIGMET: 기상청 API허브(IWXXM) · 대구: NOAA 중계 METAR. 공항경보 API는 연동 전(확인 불가).</div>'
    # 동남아
    isig = curl(f'{NOAA}/isigmet?format=raw&hazard=ts')
    FIRS = {'RPHI': '필리핀', 'VVHM': '베트남·캄보디아', 'VVHN': '베트남·캄보디아', 'VDPF': '베트남·캄보디아', 'VTBB': '태국·미얀마', 'VYYF': '태국·미얀마',
            'WMFC': '말레이·싱가포르·인니', 'WSJC': '말레이·싱가포르·인니', 'WIIF': '말레이·싱가포르·인니', 'WAAF': None, 'WBFC': '보르네오'}
    REG = {'필리핀': ('마닐라·세부·클락 방면', ['RPLL', 'RPVM']), '베트남·캄보디아': ('호치민·다낭·하노이·푸꾸옥 방면', ['VVTS', 'VVDN']), '태국·미얀마': ('방콕 방면(안다만해 인접)', ['VTBS']),
           '말레이·싱가포르·인니': ('쿠알라룸푸르·싱가포르 방면', ['WMKK', 'WSSS']), '보르네오': ('코타키나발루 방면', [])}
    sigs = {k: [] for k in REG}
    for blk in isig.split('----------------------'):
        m = re.search(r'(\w{4}) SIGMET (\S+) VALID (\d{2})(\d{4})/(\d{2})(\d{4})', blk)
        if not m: continue
        fir = m.group(1); reg = FIRS.get(fir)
        if not reg: continue
        def z(dd, hhmm):
            d = NOW.replace(day=int(dd), hour=int(hhmm[:2]), minute=int(hhmm[2:]), second=0, microsecond=0)
            return d + KST
        v1, v2 = z(m.group(3), m.group(4)), z(m.group(5), m.group(6))
        top = re.search(r'TOP\s*(?:ABV )?(FL\d+)', blk); mov = re.search(r'(MOV [A-Z]+ \d+KT|STNR)', blk)
        fc = 'FCST' if 'TS FCST' in blk else 'OBS'
        sigs[reg].append(dict(fir=fir, v1=v1, v2=v2, top=top.group(1) if top else '', mov=mov.group(1) if mov else '', fc=fc))
    rows = ''; rsum = {}
    for reg, (routes, stns) in REG.items():
        act = [s for s in sigs[reg] if s['v1'] <= nowk <= s['v2']]
        obs = []; cbflag = False
        for s in stns:
            if s in nm:
                o = mini_obs(nm[s]); obs.append(f'{s} ' + ('풍향 변동' if o['dir'] == 'VRB' else f'{o["dir"]}°') + f' {o["spd"]}kt 시정 {o["vis"]}' + (f' <b>{"/".join(o["cb"])}</b>' if o['cb'] else '')); cbflag |= bool(o['cb'])
        st = 'R' if len(act) >= 3 else ('A' if (act or cbflag) else 'G')
        if reg == '말레이·싱가포르·인니' and len(act) >= 2: st = 'R'
        what = ' / '.join(f'{s["fir"]} 뇌우{"예상" if s["fc"]=="FCST" else "관측"} {s["top"]}{(" " + s["mov"]) if s["mov"] else ""}' for s in act) or 'SIGMET 없음'
        if obs: what += '<br>' + ' / '.join(obs)
        when = '·'.join(sorted({f'{s["v1"]:%H:%M}~{s["v2"]:%H:%M}' for s in act})) or '-'
        rows += route(reg, STATE_LABEL[st], st, routes, what, when); rsum[reg] = dict(state=st, n=len(act))
    jt = curl('https://www.metoc.navy.mil/jtwc/products/abpwweb.txt'); flat = ' '.join(jt.split())
    ty = re.findall(r'(SUPER TYPHOON|TYPHOON|TROPICAL STORM|TROPICAL DEPRESSION) (\d+[WP]?) \(([A-Z\-]+)\) WAS LOCATED NEAR ([\d\.]+[NS]) ([\d\.]+[EW]).*?TRACKED ([A-Z\- ]+?) AT (\d+) KNOTS.*?WINDS WERE ESTIMATED AT (\d+) KNOTS GUSTING TO (\d+) KNOTS', flat)
    hdr = re.search(r'ABPW10 PGTW (\d{2})(\d{4})', jt)
    if ty:
        parts = []; far = True
        for kind, no, nmn, la, lo, mv, sp, w, gu in ty:
            lov = float(lo[:-1]); lav = float(la[:-1])
            if not (lov >= 125 and lav >= 20): far = False
            MV = {'NORTHWARD': '북진', 'SOUTHWARD': '남진', 'WESTWARD': '서진', 'EASTWARD': '동진', 'NORTHWESTWARD': '북서진', 'NORTHEASTWARD': '북동진', 'WEST-NORTHWESTWARD': '서북서진', 'WEST- NORTHWESTWARD': '서북서진'}
            parts.append(f'{kind} {no}({nmn}) {la} {lo}, {MV.get(mv.strip(), mv.strip())} {sp}kt, 최대풍속 {w}kt(순간 {gu}kt)')
        tsum = ' / '.join(parts) + (' — 동남아 항로와 거리 멂(위치 기준 자동 판단)' if far else ' — 동남아 항로 영향 여부 확인 필요')
        tst = 'G' if far else 'R'; tlab = '영향 낮음' if far else '확인 필요'
    else:
        tsum = '활성 열대저기압 없음(JTWC)' if jt else '확인 불가(JTWC 응답 없음)'; tst = 'G' if jt else 'N'; tlab = '없음' if jt else '확인 불가'
    if not jt: gaps.append('JTWC 응답 없음')
    rows += route('태풍', tlab, tst, f'JTWC {hdr.group(0)[-6:] if hdr else ""}Z 발표', tsum, 'JTWC')
    sea_html = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E5E7EB;border-radius:6px;">' + rows + '</table>'
    sea_html += '<div style="font-size:11.5px;color:#6B7280;margin-top:3px;">출처: NOAA 국제 SIGMET(뇌우)·METAR, JTWC. 노선 연결은 방면 기준 참고용. PAGASA·베트남 기상청 현지 예보는 연동 전(확인 불가). 시각은 KST.</div>'
    active = sum(rsum[r]['n'] for r in rsum)
    worst = min([v['state'] for v in rsum.values()] or ['G'], key=lambda z: 'RAG'.index(z))
    data = dict(generated_kst=f'{nowk:%Y-%m-%d %H:%M}', domestic=summ, sea=dict(regions=rsum, active_sigmet=active, worst=worst, typhoon=tsum),
                domestic_html=dom_html, sea_html=sea_html, gaps=gaps)
    json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print(f'saved {out} · gaps={gaps}')


if __name__ == '__main__':
    main()
