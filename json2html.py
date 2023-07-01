import json
import argparse

import tieba

parser = argparse.ArgumentParser()
parser.add_argument('tid', type=int, help='帖子的ID')
parser.add_argument('-d', '--download', action='store_true', help='下载图片文件')
parser.add_argument('-s', '--separate', action='store_true', help='是否给下载的图片分配单独文件夹')
parser.add_argument('-n', '--img-task-size', type=int, default=100, help='下载图片时一次启动多少个线程')
args = parser.parse_args()

data = json.load(open('{}.json'.format(args.tid), encoding='utf-8'))
tieba.write_file(
    args.tid,
    data['title'], 
    data['result'], 
    tieba.determine_filename(data['title'], None),
    tieba.get_img_mode(args),
    args.img_task_size
)