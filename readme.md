# 贴吧->HTML

## 使用方法

1. clone仓库到本地
2. 安装依赖项
3. 去贴吧上找到对应的帖子的tid
4. 运行
```sh
$ python3 tieba.py <tid> <filename>
```
如果没有提供文件名, 文件名会在数据爬取后产生, 具体懒得说了  
此外, 还会产生一个名为`data.json`的文件

## 这个页面太丑了, 我想换一个

1. 修改`tieba.py`内的`write_file`函数
2. 运行`json2html.py`

## 安全验证???

1. 访问浏览器, 进行人工安全验证
2. 打开DevTools, 把页面请求的Cookies复制下来
3. 运行`cookies2json.py`

## `-t`和`-p`选项是干什么的?

用来刷帖的, 懒得说了