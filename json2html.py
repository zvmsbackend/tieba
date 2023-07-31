import webbrowser
import argparse
import json

import tieba


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tid', help='帖子的ID')
    parser.add_argument('-b', '--browser',
                        action='store_true', help='结束以后打开浏览器')
    parser.add_argument('-d', '--download', action='store_true', help='下载图片文件')
    parser.add_argument('-s', '--separate',
                        action='store_true', help='是否给下载的图片分配单独文件夹')
    parser.add_argument('-n', '--img-task-size', type=int,
                        default=100, help='下载图片时一次启动多少个线程')
    args = parser.parse_args()

    data = json.load(open(f'{args.tid}.json', encoding='utf-8'))
    filename = tieba.determine_filename(
        data['title'], None, args.tid.endswith('-lz'))
    tieba.write_file(
        args.tid,
        data['title'],
        data['result'],
        filename,
        tieba.get_img_mode(args),
        args.img_task_size
    )
    if args.browser:
        webbrowser.open(filename)


if __name__ == '__main__':
    main()
