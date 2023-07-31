from itertools import chain
import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tid')
    args = parser.parse_args()
    data = json.load(open(args.tid + '.json', encoding='utf-8'))
    print(*(i['content'] for i in chain(*data['result']) if any('诗' in j['content'] for j in chain(*i['comments']))), sep='\n')

if __name__ == '__main__':
    main()