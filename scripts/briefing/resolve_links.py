#!/usr/bin/env python3
"""구글 뉴스 중계 링크(news.google.com/rss/articles/...)를 언론사 원문 URL로 변환.
메일 링크 클릭 시 뜨는 '리디렉션 알림'을 없애기 위함.
사용: python3 resolve_links.py brief.json   (news_sections/featured 의 url 을 제자리에서 치환)
실패한 링크는 원래 주소를 유지하고 stderr 로 알린다.
"""
import json, re, subprocess, sys, time, urllib.parse


def _curl(args):
    return subprocess.run(['curl', '-sS', '-m', '25', '-L'] + args, capture_output=True, text=True).stdout


def resolve(url):
    if 'news.google.com/rss/articles/' not in url: return url
    aid = url.split('/articles/')[1].split('?')[0]
    for _ in range(3):
        page = _curl([f'https://news.google.com/rss/articles/{aid}'])
        sg = re.search(r'data-n-a-sg="([^"]+)"', page); ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        if sg and ts:
            inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts.group(1)), sg.group(1)])
            body = 'f.req=' + urllib.parse.quote(json.dumps([[["Fbv4je", inner, None, "generic"]]]))
            r = _curl(['-X', 'POST', '-H', 'Content-Type: application/x-www-form-urlencoded;charset=UTF-8', '--data', body, 'https://news.google.com/_/DotsSplashUi/data/batchexecute'])
            m = re.search(r'garturlres\\",\\"(https?://.*?)\\"', r)
            if m: return m.group(1).replace('\\\\u003d', '=').replace('\\\\u0026', '&')
        time.sleep(1)
    return None


def main():
    p = sys.argv[1]; d = json.load(open(p, encoding='utf-8'))
    items = []
    for s in d['news_sections']:
        items += s.get('items', [])
        if s.get('featured'): items += s['featured']['items']
    ok = 0
    for n in items:
        u = resolve(n['url'])
        if u: n['url'] = u; ok += 1
        else: print('resolve 실패(원래 주소 유지):', n['title'], file=sys.stderr)
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'resolved {ok}/{len(items)}')


if __name__ == '__main__':
    main()
