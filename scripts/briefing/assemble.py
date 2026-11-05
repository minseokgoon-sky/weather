#!/usr/bin/env python3
"""brief.json + weather.json -> mail.html (순서: 헤더 → KPI → 오늘의 핵심 → 뉴스 → 기상 → 안내)
사용: python3 assemble.py brief.json weather.json mail.html
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

brief = json.load(open(sys.argv[1], encoding='utf-8')); w = json.load(open(sys.argv[2], encoding='utf-8'))
out = sys.argv[3]
d = w['domestic']
def dk(ic):
    s = d.get(ic, {}); st = s.get('state', 'N')
    return kpi(f'{s.get("name", ic)} {ic}', STATE_LABEL.get(st, '확인 불가'), st if st in 'RAG' else 'N', s.get('head', '확인 불가'), s.get('now', '')[:60])
a = brief['kpi_airline']
sea = w['sea']
sk = {'R': 'R', 'A': 'B', 'G': 'G'}.get(sea['worst'], 'B')
o = ['<div style="font-family:\'Malgun Gothic\',sans-serif;max-width:800px;line-height:1.6;color:#111827;font-size:14px;">']
o.append(f'''<div style="background:linear-gradient(90deg,#0B2A4A,#1D4ED8);background-color:#0B2A4A;border-radius:8px;padding:14px 16px;color:#fff;"><div style="font-size:12px;color:#BFDBFE;">DAILY AVIATION BRIEFING · {brief.get("to_label","")}</div>
<div style="font-size:19px;font-weight:bold;margin-top:2px;">항공 동향 및 기상 브리핑</div><div style="font-size:12px;color:#DBEAFE;margin-top:3px;">{brief["as_of"]} KST 기준 · 최근 24시간 · 기상 시각은 KST</div></div>''')
o.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:10px 0 6px 0;"><tr>' + dk('RKPC') + dk('RKPK') +
         kpi('국적사', a['state'], a['color'], a['head'], a['sub']) +
         kpi('동남아 경로', {'R': '경계', 'A': '주의', 'G': '양호'}[sea['worst']], sk, f'뇌우 SIGMET 발효 {sea["active_sigmet"]}건', brief['kpi_sea_sub']) + '</tr></table>')
dots = {'R': '#DC2626', 'A': '#F59E0B', 'B': '#2563EB', 'G': '#16A34A'}
o.append('<div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:6px;padding:10px 12px;margin:6px 0 0 0;"><b style="color:#92400E;">오늘의 핵심</b><div style="font-size:13px;line-height:1.7;margin-top:3px;">' +
         '<br>'.join(f'<span style="color:{dots[p["color"]]};">●</span> {p["text"]}' for p in brief['key_points']) + '</div></div>')
for secd in brief['news_sections']:
    o.append(sec(secd['title'], secd['color']))
    if secd.get('featured'):
        f = secd['featured']
        o.append(f'<div style="background:#ECFDF5;border:1px solid #86EFAC;border-radius:6px;padding:4px 12px;margin-bottom:4px;"><div style="font-size:12px;color:#166534;font-weight:bold;padding-top:6px;">★ {f["label"]}</div>' +
                 ''.join(news_item(n['tag'], n['color'], n['url'], n['title'], n['summary'], n['source'], i == 0) for i, n in enumerate(f['items'])) + '</div>')
    o.extend(news_item(n['tag'], n['color'], n['url'], n['title'], n['summary'], n['source']) for n in secd['items'])
o.append(sec('국내 공항 기상 보드', 'R')); o.append(w['domestic_html'])
o.append(sec('동남아 노선 기상 보드', 'B')); o.append(w['sea_html'])
gaps = w.get('gaps') or []
o.append('<div style="font-size:11.5px;color:#374151;background:#F9FAFB;border:1px solid #E5E7EB;border-radius:6px;padding:9px 11px;margin-top:14px;line-height:1.6;"><b>안내</b> · 운항 판단에는 항공기상청 원문(METAR/TAF·공항경보)을 확인하세요. <b>확인 불가:</b> 공항경보(윈드시어 경보 포함), PAGASA·베트남 기상청 현지 예보' + (' · ' + ' / '.join(gaps) if gaps else '') + '</div></div>')
open(out, 'w', encoding='utf-8').write('\n'.join(o)); print('saved', out, len('\n'.join(o)))
