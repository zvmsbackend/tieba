import re
import json
import os.path
import argparse
from threading import Thread
from functools import partial
from collections import defaultdict

import bs4
import requests
from bs4.element import Tag

def make_baidu_soup(url: str) -> bs4.BeautifulSoup:
    res = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(res.content.decode(), 'lxml')
    if soup.title.string == '百度安全验证':
        raise Exception('百度安全验证')
    return soup

def prettify_tag(tag: Tag):
    return re.sub('\n+', '\n', tag.get_text().strip())

def get_total_comments(tid: int) -> dict:
    res = requests.get('https://tieba.baidu.com/p/totalComment?tid={}'.format(tid))
    data = json.loads(res.content.decode())['data']
    return {
        'comment_list': defaultdict(partial(defaultdict, list), data['comment_list']),
        'user_list': data['user_list']
    }
    
try:
    cookies = json.load(open('cookies.json', encoding='utf-8'))
except OSError:
    cookies = {}

def determine_filename(title: str, filename: str | None) -> str:
    if filename is None:
        filename = input('文件路径: ')
        if not filename:
            return title + '.html'
    if os.path.isdir(filename):
        return '{}/{}.html'.format(filename, title)
    if not filename.endswith('.html'):
        filename += '.html'
    return filename

def crawl_page(tid: int, pn: int, total_comments: dict, result: list, return_total_title_and_page: bool = False) -> int:
    print('开始爬取第', pn, '页')
    soup = make_baidu_soup('https://tieba.baidu.com/p/{}?pn={}'.format(tid, pn))
    result[pn - 1] = [
        {
            'author': {
                'icon': (lambda img: img['src' if not img['src'].startswith('//') else 'data-tb-lazyload'])(div.find('li', class_='icon').img),
                'name': div.find('li', class_='d_name').a.get_text()
            },
            'content': ''.join(map(str.strip, map(str, div.find('div', class_='d_post_content j_d_post_content').contents))),
            'ip': div.find('div', class_='post-tail-wrap').span.string[5:],
            'time': div.find('div', class_='post-tail-wrap').find_all('span', class_='tail-info')[-1].string,
            'comments': [ 
                {
                    'author': comment['show_nickname'],
                    'icon': total_comments['user_list'][str(comment['user_id'])]['portrait'],
                    'content': comment['content']
                }
                for comment in total_comments['comment_list'][div['data-pid']]['comment_info']
            ]
        }
        for div in soup.find_all('div', class_='l_post l_post_bright j_l_post clearfix')
    ]
    print('第', pn, '页爬取完成')
    if return_total_title_and_page:
        return (
            soup.find('h3', class_='core_title_txt').string.strip(),
            int(soup.find('li', class_='l_reply_num').find_all('span')[1].string)
        )
    
def write_file(title: str, result: list, filename: str):
    open(filename, 'w', encoding='utf-8').write(
        """<html>
<head>
  <link rel="stylesheet" href="https://cdn.staticfile.org/twitter-bootstrap/5.1.1/css/bootstrap.min.css">
</head>
<body>
  <div class="container" style="margin-top: 50px">
    <h1 class="text-primary" id="top">{}</h1>
    <ul class="pagination fixed-top">
    {}
    </ul>
    <div>
    {}
    </div>
  </div>
</body>
</html>""".format(
            title,
            '\n'.join(
                '<li class="page-item"><a class="page-link" href="#_{}">{}</a></li>'.format(
                    i, i + 1
                )
                for i in range(len(result))
            ),
            '\n'.join(
                '<h4 id="_{}">第{}页</h4>\n{}'.format(
                    i,
                    i + 1,
                    '\n'.join(
                        """<div class="row">
<div class="col-2">
    <img style="width: 80px; height: 80px;" src="{}">
    <p>{}</p>
</div>
<div class="col">
    <blockquote class="blockquote">
        {}
        <footer class="blockquote-footer"><small>IP属地: {} {}</small></footer>
    </blockquote>
    <ul class="list-group">
    {}
    </ul>
</div>
</div>
<hr>""".format(
                            lou['author']['icon'],
                            lou['author']['name'],
                            lou['content'],
                            lou['ip'],
                            lou['time'],
                            '\n'.join(
                                """<li class="list-group-item">
<img style="width: 32px; height: 32px;" src="https://gss0.bdstatic.com/6LZ1dD3d1sgCo2Kml5_Y_D3/sys/portrait/item/{}">{}: {}
</li>""".format(
                                    comment['icon'],
                                    comment['author'],
                                    comment['content']
                                )
                                for comment in lou['comments']
                            )
                        )
                        for lou in page
                    )
                )
                for i, page in enumerate(result)
            )
        )
    )
    print('写入', os.path.abspath(filename))
    
def roam_tieba(kw: str, pn: int):
    soup = make_baidu_soup('https://tieba.baidu.com/f?kw=' + kw)
    ties = [tie for tie in soup.find('ul', id='thread_list').contents if tie.name == 'li' and tie.find('i', class_='icon-top') is None]
    selection = int(input('\n'.join(
        '{}: {}\n{}'.format(
            i,
            prettify_tag(tie.find('div', class_='threadlist_lz clearfix')),
            prettify_tag(tie.find('div', class_='threadlist_detail clearfix'))
        )
        for i, tie in enumerate(ties)
    )))
    tid = int(ties[selection]['data-tid'])
    main(tid, None)

def main(tid: int, filename: str | None) -> None:
    total_comments = get_total_comments(tid)
    result = [None]
    title, total_page = crawl_page(tid, 1, total_comments, result, True)
    print('爬取', title, ', 共', total_page, '页')
    result.extend([None] * (total_page - 2))
    threads = []
    for i in range(2, total_page):
        thread = Thread(target=crawl_page, args=(
            tid,
            i,
            total_comments,
            result
        ))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    json.dump({
        'title': title,
        'result': result
    }, open('{}.json'.format(tid), 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
    filename = determine_filename(title, filename)
    write_file(title, result, filename)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tid', type=int, nargs='?')
    parser.add_argument('filename', nargs='?')
    parser.add_argument('-t')
    parser.add_argument('-p', type=int)
    args = parser.parse_args()
    if args.t is not None:
        roam_tieba(args.t, args.p or 0)
    else:
        main(args.tid, args.filename)