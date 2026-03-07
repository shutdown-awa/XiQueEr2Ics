import requests
import json
import re
from bs4 import BeautifulSoup
import logging
import os
import time
import random

class SchoolCalendarSync:
    """校历同步工具类，负责获取学期列表并解析每个学期的起止日期和假期。"""

    def __init__(self, config_path="config.json"):
        """初始化：创建会话，加载配置文件，设置日志。"""
        # ========设置日志========
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        # ========获取配置========
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        # 如果传入的是相对路径，则相对于脚本目录构建完整路径
        if not os.path.isabs(config_path):
            config_path = os.path.join(self.script_dir, config_path)
        self.config = self._load_config(config_path)
        # 从配置中获取 rootUrl
        self.url = self.config.get("rootUrl", "")
        if not self.url:
            raise ValueError("rootUrl not found in config")
        
        #=========初始化session========
        self._initializeSession()
        

    def _initializeSession(self):
        """初始化会话，设置必要的 headers 和 cookies（如果需要）。"""
        self.session = requests.Session()
        # 设置默认 headers
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,zh-HK;q=0.7,en-US;q=0.6,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        })
        try:
            self.session.get(self.url)  # 访问一次主页以获取必要的 cookies
        except Exception as e:
            logging.error(f"Failed to initialize session: {e}")
            raise e


    def _load_config(self, path):
        """加载配置文件，返回配置字典。(内部方法)"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return {}


    def _get_terms(self):
        """
        获取学期列表（内部方法）。

        Returns:
        - list of tuples: [(year, semester), ...]，按年份和学期降序排序，包含最近5年的数据。
        - 如果获取失败或没有数据，返回空列表。
        """
        url = f"{self.url}/frame/droplist/getDropLists.action"
        headers = {
            "Referer": self.url + "/public/SchoolCalendar.jsp",
            "Origin": self.url,
        }
        data = {
            "comboBoxName": "MsXnxqFbDesc",
            "paramValue": "",
            "isYXB": 0,
            "isCDDW": 0,
            "isXQ": 0,
            "isDJKSLB": 0,
            "isZY": 0
        }

        try:
            response = self.session.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            # 解析JSON
            terms = response.json()
            
            # 提取所有学期信息：年份、学期代号、完整code
            year_semester_list = []
            for item in terms:
                code = item.get('code', '')
                if '-' in code:
                    parts = code.split('-')
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        year = int(parts[0])
                        semester = int(parts[1])
                        year_semester_list.append((year, semester, code))
            
            if not year_semester_list:
                return []
            
            # 找出数据中的最大年份
            max_year = max(item[0] for item in year_semester_list)
            
            # 确定最近5年的起始年份（包含最大年份）
            start_year = max_year - 4
            
            # 筛选年份在 [start_year, max_year] 范围内的学期
            filtered = [item for item in year_semester_list if start_year <= item[0] <= max_year]
            
            # 按年份降序，同一学年内按学期降序（第二学期在前）
            filtered.sort(key=lambda x: (x[0], x[1]), reverse=True)
            
            # 返回多元数组（元组列表）
            return filtered

        except Exception as e:
            logging.error(f"Failed to get terms list: {e}")
            return []


    def get_school_calendar(self):
        """
        获取每个学期的校历信息，并保存为 JSON 文件

        Returns:
        - json object: { "school-year-semester-code": { "termStartDate": "YYYY-MM-DD", "termEndDate": "YYYY-MM-DD", "termVacationStartDate": "YYYY-MM-DD", "termVacationEndDate": "YYYY-MM-DD" }, ... }
        """
        # 获取学期列表
        termList = self._get_terms()
        if not termList:
            logging.warning("Stop syncing timetable due to failure in getting terms list.")
            return

        schoolCalendar = {}

        for year, semester, code in termList:
            # 请求数据
            data = {
                "xn": year,
                "xq_m": semester
            }

            url = f"{self.url}/public/SchoolCalendar.show.jsp"
            headers = {
                "Referer": self.url + "/public/SchoolCalendar.jsp",
                "Origin": self.url,
            }

            try:
                response = self.session.post(url, headers=headers, data=data)
                response.raise_for_status()

                # 解析 HTML 提取日期
                soup = BeautifulSoup(response.text, 'html.parser')
                textarea = soup.find('textarea', {'id': 'bz'})  # 根据 ID 定位备注框
                if not textarea:
                    logging.warning(f"No textarea with id 'bz' found for term {code}")
                    continue

                # 获取文本内容并清理多余空白
                content = textarea.get_text(strip=True)
                # 使用正则提取四个日期
                start_date = re.search(r'学期开始日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                end_date = re.search(r'学期结束日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                vacation_start = re.search(r'假期开始日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                vacation_end = re.search(r'假期结束日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                logging.debug(f"Extracted dates for term {code}: start_date={start_date.group(1) if start_date else 'N/A'}, end_date={end_date.group(1) if end_date else 'N/A'}, vacation_start={vacation_start.group(1) if vacation_start else 'N/A'}, vacation_end={vacation_end.group(1) if vacation_end else 'N/A'}")

                if not (start_date and end_date and vacation_start and vacation_end):
                    logging.warning(f"Missing some date fields for term {code}")
                    continue

                # 构建该学期的数据字典
                term_data = {
                    "termStartDate": start_date.group(1),
                    "termEndDate": end_date.group(1),
                    "termVacationStartDate": vacation_start.group(1),
                    "termVacationEndDate": vacation_end.group(1)
                }

                # 将数据存入总的日历字典
                schoolCalendar[code] = term_data
                logging.info(f"Successfully synced timetable for term {code}")

                # 随机等待1-2秒，模拟人类行为，避免过快请求被封禁
                time.sleep(1 + 1 * random.random())


            except Exception as e:
                logging.error(f"Failed to sync timetable for term {code}. Error: {e}")

        return schoolCalendar


if __name__ == "__main__":
    sync = SchoolCalendarSync()
    schoolCalendar = sync.get_school_calendar()

    output_file = "school_calendar.json"
    if not os.path.isabs(output_file):
        output_file = os.path.join(sync.script_dir, output_file)
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schoolCalendar, f, ensure_ascii=False, indent=4)
        logging.info(f"Calendar data saved to {output_file}")
    except Exception as e:
        logging.error(f"Failed to save JSON file: {e}")