"""공통 렌더링 헬퍼 (이메일 호환: 표 + 인라인 CSS, 글자 14px 기준)."""
import html

C = {'R': ('#DC2626', '#FEE2E2', '#991B1B'), 'A': ('#F59E0B', '#FEF3C7', '#92400E'),
     'G': ('#16A34A', '#DCFCE7', '#166534'), 'B': ('#2563EB', '#DBEAFE', '#1E40AF'),
     'P': ('#7C3AED', '#EDE9FE', '#5B21B6'), 'N': ('#9CA3AF', '#F3F4F6', '#374151')}
STATE_LABEL = {'R': '경계', 'A': '주의', 'G': '양호'}


def chip(t, k):
    return f'<span style="display:inline-block;background:{C[k][0]};color:#fff;font-size:12px;font-weight:bold;padding:2px 9px;border-radius:10px;">{t}</span>'


def tag(t, k):
    c = C[k]
    return f'<span style="display:inline-block;background:{c[1]};color:{c[2]};font-size:12px;font-weight:bold;padding:1px 7px;border-radius:3px;margin-right:5px;">{html.escape(t)}</span>'


def kpi(label, state, k, head, sub):
    c = C[k]
    return f'''<td width="25%" valign="top" style="padding:4px;"><div style="background:{c[1]};border-top:5px solid {c[0]};border-radius:6px;padding:10px 11px;">
<div style="font-size:12px;color:#374151;">{label}</div><div style="margin:4px 0;">{chip(state, k)}</div>
<div style="font-size:14px;font-weight:bold;color:{c[2]};line-height:1.4;">{head}</div>
<div style="font-size:12px;color:#374151;line-height:1.5;margin-top:3px;">{sub}</div></div></td>'''


def timeline(states, blocks):
    # 빈 셀은 메일 클라이언트(Gmail 등)에서 높이가 0으로 접히므로 &nbsp; + line-height 로 높이를 강제하고 bgcolor 속성도 함께 지정
    cells = ''.join(f'<td bgcolor="{C[s][0]}" height="16" style="background:{C[s][0]};height:16px;line-height:16px;font-size:12px;border-right:2px solid #ffffff;">&nbsp;</td>' for s in states)
    hrs = ''.join(f'<td style="font-size:10px;color:#6B7280;padding-top:2px;">{b}</td>' for b in blocks)
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 2px 0;"><tr>{cells}</tr><tr>{hrs}</tr></table>'


def acard(name, icao, state_text, k, now, head, note, tl_states, blocks, span_label):
    c = C[k]
    return f'''<td width="50%" valign="top" style="padding:5px;"><div style="border:1px solid #E5E7EB;border-left:6px solid {c[0]};border-radius:6px;padding:11px 12px;background:#fff;">
<div><b style="font-size:15px;">{name}</b> <span style="font-size:11px;color:#6B7280;">{icao}</span> &nbsp;{chip(state_text, k)}</div>
<div style="font-size:14px;font-weight:bold;color:{c[2]};margin:6px 0 3px 0;line-height:1.45;">{head}</div>
<div style="font-size:12px;color:#374151;line-height:1.55;">{now}</div>
{timeline(tl_states, blocks)}
<div style="font-size:11px;color:#6B7280;">{span_label} · <span style="color:#DC2626;">■</span>경계 <span style="color:#F59E0B;">■</span>주의 <span style="color:#16A34A;">■</span>양호</div>
<div style="font-size:12px;color:#1F2937;line-height:1.55;margin-top:6px;background:#F9FAFB;padding:6px 8px;border-radius:4px;">{note}</div></div></td>'''


def route(area, state, k, routes, what, when):
    c = C[k]
    return f'''<tr><td style="padding:8px 9px;border-bottom:1px solid #E5E7EB;background:{c[1]};width:92px;vertical-align:top;"><b style="font-size:13px;color:{c[2]};">{area}</b><br>{chip(state, k)}</td>
<td style="padding:8px 9px;border-bottom:1px solid #E5E7EB;font-size:12.5px;line-height:1.55;vertical-align:top;"><b>{routes}</b><br>{what}</td>
<td style="padding:8px 9px;border-bottom:1px solid #E5E7EB;font-size:12px;color:#374151;width:96px;vertical-align:top;">{when}</td></tr>'''


def sec(t, k):
    return f'<div style="margin:24px 0 8px 0;"><span style="display:inline-block;width:6px;height:18px;background:{C[k][0]};vertical-align:middle;border-radius:2px;"></span> <b style="font-size:16px;vertical-align:middle;">{t}</b></div>'


def news_item(tg, k, url, title, summary, source, big=False):
    sz = '15px' if big else '14px'
    return f'''<div style="padding:8px 0;border-bottom:1px solid #EEF0F3;">{tag(tg, k)}<a href="{html.escape(url, quote=True)}" style="color:#1E3A8A;text-decoration:none;font-weight:bold;font-size:{sz};">{html.escape(title)}</a>
<div style="font-size:12.5px;color:#374151;margin-top:3px;line-height:1.55;">{html.escape(summary)}</div><div style="font-size:11.5px;color:#6B7280;margin-top:1px;">{html.escape(source)}</div></div>'''
