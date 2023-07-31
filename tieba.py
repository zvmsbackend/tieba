from collections import defaultdict
from datetime import datetime
from functools import partial
from threading import Thread
import webbrowser
import argparse
import os.path
import hashlib
import json
import re

from bs4.element import Tag, ResultSet
import requests
import jinja2
import bs4


def inner_html(tag: Tag) -> str:
    return ''.join(map(str.strip, map(str, tag.contents)))


def make_baidu_soup(url: str) -> bs4.BeautifulSoup:
    res = requests.get(url, cookies=cookies)
    soup = bs4.BeautifulSoup(res.content.decode(), 'lxml')
    if soup.title.string == '百度安全验证':
        raise RuntimeError('百度安全验证')
    return soup


def prettify_tag(tag: Tag) -> str:
    return re.sub('\n+', '\n', tag.get_text().strip())


def get_total_comments(tid: int, pn: int, see_lz: bool) -> dict:
    res = requests.get(
        'https://tieba.baidu.com/p/totalComment?tid={}&pn={}&see_lz={}'.format(tid, pn, int(see_lz)))
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


def crawl_extra_comments(tid: int, pid: str, pn: int, pages: list) -> None:
    res = requests.get(
        'https://tieba.baidu.com/p/comment?tid={}&pid={}&pn={}'.format(tid, pid, pn))
    soup = bs4.BeautifulSoup(res.content.decode(), 'lxml')
    pages[pn - 1] = [
        {
            'author': li.div.a.get_text(),
            'icon': li.img['src'],
            'content': inner_html(li.span),
            'time': li.find('span', class_='lzl_time').string
        }
        for li in soup.find_all('li', class_='lzl_single_post')
    ]


def get_comments(tid: int, pid: str, total_comments: dict) -> list[list[dict]]:
    comments = total_comments['comment_list'][pid]
    pages = [[
        {
            'author': comment['show_nickname'],
            'icon': ('https://gss0.bdstatic.com/6LZ1dD3d1sgCo2Kml5_Y_D3/sys/portrait/item/' +
                     total_comments['user_list'][str(comment['user_id'])]['portrait']),
            'content': comment['content'],
            'time': datetime.fromtimestamp(comment['now_time']).strftime('%Y-%m-%d %H:%M')
        }
        for comment in comments['comment_info']
    ]]
    if comments['comment_num'] > comments['comment_list_num']:
        threads = []
        count = comments['comment_num'] // comments['comment_list_num']
        pages.extend([None] * count)
        for i in range(2, count + 2):
            thread = Thread(
                target=crawl_extra_comments,
                args=(
                    tid,
                    pid,
                    i,
                    pages
                )
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
    return pages


def crawl_page(tid: int, pn: int, result: list, see_lz: bool, return_total_title_and_page: bool) -> int:
    print('开始爬取第', pn, '页')
    soup = make_baidu_soup(
        'https://tieba.baidu.com/p/{}?pn={}&see_lz={}'.format(tid, pn, int(see_lz)))
    total_comments = get_total_comments(tid, pn, see_lz)
    result[pn - 1] = [
        {
            'author': {
                'icon': ((img := div.find('li', class_='icon').img) and
                         img['src' if not img['src'].startswith('//') else 'data-tb-lazyload']),
                'name': inner_html(div.find('li', class_='d_name').a),
                'title': div.find('div', class_='d_badge_title').string,
                'level': int(div.find('div', class_='d_badge_lv').string)
            },
            'content': inner_html(div.find('div', class_='d_post_content j_d_post_content')),
            'ip': tail.span.get_text()[5:],
            'time': tail_info[-1].string,
            'index': int(re.search(r'\d+', tail_info[1].string).group(0)),
            'comments': get_comments(tid, div['data-pid'], total_comments)
        }
        for div in soup.find_all('div', class_='l_post l_post_bright j_l_post clearfix')
        if (tail := div.find('div', class_='post-tail-wrap')) and (tail_info := tail.find_all('span', class_='tail-info'))
    ]
    print('第', pn, '页爬取完成')
    if return_total_title_and_page:
        return (
            soup.find(class_='core_title_txt').string.strip(),
            int(soup.find('li', class_='l_reply_num').find_all(
                'span')[1].string)
        )


def download_img(dir: str, url: str, code: str) -> None:
    print('下载', url)
    res = requests.get(url)
    open(os.path.join(dir, code), 'wb').write(res.content)


def download_imgs(imgs: ResultSet, dir: str, img_task_size: int) -> None:
    if not os.path.exists(dir):
        os.mkdir(dir)
    print('共有', len(imgs), '张图片')
    tasks = set()
    for img in imgs:
        md5 = hashlib.md5()
        md5.update(img['src'].encode())
        code = md5.hexdigest()
        tasks.add((img['src'], code))
        img['src'] = os.path.join(dir, code)
    while tasks:
        threads = []
        for _ in range(img_task_size):
            if not tasks:
                break
            thread = Thread(
                target=download_img,
                args=(dir, *tasks.pop())
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()


def format_comments(comments: list[dict]) -> str:
    return ''.join(
        """<li class="list-group-item">
<img style="width: 32px; height: 32px;" src="{}">{}: {}
</li>""".format(
            comment['icon'],
            comment['author'],
            comment['content']
        )
        for comment in comments
    )


def write_file(tid: int, title: str, result: list, filename: str, img_mode: str, img_task_size: int) -> None:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))
    template = env.get_template('template.html')
    soup = bs4.BeautifulSoup(template.render(
        range=range,
        len=len,
        max=max,
        min=min,
        enumerate=enumerate,
        title=title,
        result=result
    ), 'lxml')
    imgs = soup.find_all('img')
    for img in imgs:
        img['src'] = re.sub('^(//|http://)', 'https://', img['src'])
        if img['src'][0] == '/':
            img['src'] = 'https://tieba.baidu.com' + img['src']
    if img_mode != 'none':
        download_imgs(imgs, 'imgs' if img_mode ==
                      'download' else str(tid), img_task_size)
    open(filename, 'w', encoding='utf-8').write(soup.prettify())
    print('写入', os.path.abspath(filename))


def roam_tieba(kw: str, pn: int, see_lz: bool, img_mode: str, img_task_size: int, browser: bool) -> None:
    soup = make_baidu_soup('https://tieba.baidu.com/f?kw=' + kw)
    ties = [tie for tie in soup.find('ul', id='thread_list').contents if tie.name == 'li' and tie.find(
        'i', class_='icon-top') is None]
    selection = int(input('\n'.join(
        '{}: {}\n{}'.format(
            i,
            prettify_tag(tie.find('div', class_='threadlist_lz clearfix')),
            prettify_tag(tie.find('div', class_='threadlist_detail clearfix'))
        )
        for i, tie in enumerate(ties)
    ) + '\n'))
    tid = int(ties[selection]['data-tid'])
    main(tid, None, see_lz, img_mode, img_task_size, browser)


def main(tid: int, filename: str | None, see_lz: bool, img_mode: str, img_task_size: int, browser: bool) -> None:
    result = [None]
    title, total_page = crawl_page(tid, 1, result, see_lz, True)
    print('爬取', title, ', 共', total_page, '页')
    result.extend([None] * (total_page - 1))
    threads = []
    for i in range(2, total_page + 1):
        thread = Thread(target=crawl_page, args=(
            tid,
            i,
            result,
            see_lz,
            False
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
    write_file(tid, title, result, filename, img_mode, img_task_size)
    if browser:
        webbrowser.open(filename)


def get_img_mode(args: argparse.Namespace) -> str:
    if args.download:
        return 'download'
    elif args.separate:
        return 'separate'
    return 'none'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tid', type=int, nargs='?', help='帖子的ID')
    parser.add_argument('filename', nargs='?', help='输出文件名')
    parser.add_argument('-l', '--see-lz', action='store_true', help='只看楼主')
    parser.add_argument('-d', '--download', action='store_true', help='下载图片文件')
    parser.add_argument('-b', '--browser',
                        action='store_true', help='结束以后打开浏览器')
    parser.add_argument('-t', '--tieba', help='要刷的贴吧名')
    parser.add_argument('-p', '--pn', type=int, default=0, help='要刷的贴吧的页数')
    parser.add_argument('-s', '--separate',
                        action='store_true', help='是否给下载的图片分配单独文件夹')
    parser.add_argument('-n', '--img-task-size', type=int,
                        default=100, help='下载图片时一次启动多少个线程')
    args = parser.parse_args()
    img_mode = get_img_mode(args)
    if args.tieba is not None:
        roam_tieba(args.tieba, args.pn, args.see_lz,
                   img_mode, args.img_task_size, args.browser)
    else:
        main(args.tid, args.filename, args.see_lz,
             img_mode, args.img_task_size, args.browser)
