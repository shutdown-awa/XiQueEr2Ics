# XiQueEr2Ics
一个可以自动获取喜鹊儿课表并转换成.ics文件的工具

## 用户使用方法
1. 自行搭建（废话😋
2. 公开服务：[由5hUtd0wN提供](https://blog.hishutdown.cn/?p=201)

## 添加自己的学校
如果需要添加自己的学校，请按照如下步骤尝试（不一定成功）：
`tips:您可以尝试复制其它学校的配置后进行修改，通常情况下各学校的喜鹊儿应该差别不大`
1. 在/schools下添加自己的学校，请使用纯数字作为文件夹名称。如果您计划提交PR，请使用学校代码（可在百度搜索）作为文件夹名称。
2. 可以尝试复制别的学校的文件夹内容。
3. 修改/schools/your_school_code/config.json的内容使其符合实际情况。
4. 自己根据实际情况修改/schools/your_school_code/timetable.json，这是上下课时间，没有选择从教务系统拉取是因为开发者的学校的作息表就是不准的嘻嘻。
5. 跑一次maintain.py，正常情况下它会自动拉取5年内所有学期的开学时间、假期时间。请在务必在每个学期的开始也这么做一次。请在完成第3步后再这么做。
6. 如果您想搭建Web来方便地生成订阅链接，请修改/web/school.json并参照上文添加您的学校。

## 自行搭建服务
以下步骤不一定要全部做、做了也不一定就能用～
1. 必须安装Python环境和Nodejs环境。
2. 修改api.py的监听目录。
3. 必须修改/web/scripts.js内顶部的请求api域名与路径。
4. 其它可能包含"hishutdown.cn"域名的代码。
5. 使用pip -r requirements.txt安装第三方Python库
6. api.py启动命令（请按照实际需求修改）：uvicorn main:app --host 0.0.0.0 --port 8000
若不能使用，请自行解决，如果您认为这是代码缺陷而非适配问题，请提交issue。


Copyright © 2026 [5hUtd0wN](https://blog.hishutdown.cn). All rights reserved.
本项目开放源代码但未使用开源协议，这意味着除在法律许可的范围内，你不可以将代码用于您的项目。项目所有者[5hUtd0wN](https://blog.hishutdown.cn)授权所有人出于“个人使用”为目的自行搭建本项目的行为，同时保留无条件撤回授权的权利。
