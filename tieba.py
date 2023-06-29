import json
import os.path
import argparse
from threading import Thread
from functools import partial
from collections import defaultdict

import bs4
import requests

def get_total_comments(tid: int) -> dict:
    res = requests.get('https://tieba.baidu.com/p/totalComment?tid={}'.format(tid))
    data = json.loads(res.content.decode())['data']
    return {
        'comment_list': defaultdict(partial(defaultdict, list), data['comment_list']),
        'user_list': data['user_list']
    }

def get_cookies() -> dict[str, str]:
    try:
        return json.load(open('cookies.json', encoding='utf-8'))
    except OSError:
        return {}

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

def crawl_page(tid: int, pn: int, total_comments: dict, result: list, cookies: dict[str, str], return_total_title_and_page: bool = False) -> int:
    print('开始爬取第', pn, '页')
    res = requests.get('https://tieba.baidu.com/p/{}?pn={}'.format(tid, pn), cookies=cookies)
    soup = bs4.BeautifulSoup(res.content.decode(), 'lxml')
    if soup.title.string == '百度安全验证':
        raise Exception('百度安全验证')
    result[pn - 1] = [
        {
            'author': {
                'icon': (lambda img: img['src' if not img['src'].startswith('//') else 'data-tb-lazyload'])(div.find('li', class_='icon').img),
                'name': div.find('li', class_='d_name').a.string
            },
            'content': ''.join(map(str.strip, map(str, div.find('div', class_='d_post_content j_d_post_content').contents))),
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
            soup.find('h3', class_='core_title_txt pull-left text-overflow').string.strip(),
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
    {}
    <ul class="list-group">
    {}
    </ul>
</div>
</div>
<hr>""".format(
                            lou['author']['icon'],
                            lou['author']['name'],
                            lou['content'],
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

def main(tid: int, filename: str | None) -> None:
    cookies = get_cookies()
    total_comments = get_total_comments(tid)
    result = [None]
    title, total_page = crawl_page(tid, 1, total_comments, result, cookies, True)
    print('爬取', title, ', 共', total_page, '页')
    result.extend([None] * (total_page - 2))
    threads = []
    for i in range(2, total_page):
        thread = Thread(target=crawl_page, args=(
            tid,
            i,
            total_comments,
            result,
            cookies
        ))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    json.dump({
        'title': title,
        'result': result
    }, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=4)
    filename = determine_filename(title, filename)
    write_file(title, result, filename)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tid', type=int)
    parser.add_argument('filename', nargs='?')
    args = parser.parse_args()
    main(args.tid, args.filename)