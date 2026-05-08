"""
喜鹊儿课表模块 - 学校代码 12623
处理登录、课表获取与 HTML 解析
"""
import logging
import os
import sys
import hashlib
import base64
import execjs
import re
import json
import threading
import time
import requests
from urllib.parse import parse_qs, urlparse, unquote
from requests.exceptions import RequestException, Timeout, ConnectionError as RequestsConnectionError
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

# 配置日志
logger = logging.getLogger(__name__)

# ============ 全局缓存 ============
_KINGO_DES_JS_CACHE = None
_SCHOOL_CALENDAR_CACHE = None
_CONFIG_CACHE = None
_CALENDAR_PATH = os.path.join(os.path.dirname(__file__), 'school_calendar.json')
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
_TIMETABLE_CONFIG_CACHE = None
_INIT_LOCK = threading.Lock()


def _init_logging():
    """初始化日志配置（仅在未配置时执行一次）"""
    global logger
    if not logger.handlers:
        logging.basicConfig(
            level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def load_config() -> Dict[str, Any]:
    """从 config.json 加载学校配置"""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        with _INIT_LOCK:
            if _CONFIG_CACHE is None:
                with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def load_timetable_config() -> Dict[str, Any]:
    """加载作息时间配置"""
    global _TIMETABLE_CONFIG_CACHE
    if _TIMETABLE_CONFIG_CACHE is None:
        with _INIT_LOCK:
            if _TIMETABLE_CONFIG_CACHE is None:
                config_path = os.path.join(os.path.dirname(__file__), 'timetable.json')
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        _TIMETABLE_CONFIG_CACHE = json.load(f)
                except Exception:
                    _TIMETABLE_CONFIG_CACHE = {}
    return _TIMETABLE_CONFIG_CACHE


def get_available_semesters() -> List[str]:
    """从校历中获取所有可用学期"""
    calendar = SchoolCalendar.load_calendar()
    return list(calendar.keys())


# ============ 工具类 ============
class XqeLibs:
    """加密与编码工具"""
    
    @staticmethod
    def md5(data: str) -> str:
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def base64_encode(data: str) -> str:
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')


class KingoDES:
    """基于 JavaScript 的 DES 加密"""
    
    def __init__(self):
        global _KINGO_DES_JS_CACHE
        if _KINGO_DES_JS_CACHE is None:
            with _INIT_LOCK:
                if _KINGO_DES_JS_CACHE is None:
                    js_path = os.path.join(os.path.dirname(__file__), 'jkingo.des.js')
                    with open(js_path, 'r', encoding='utf-8') as f:
                        _KINGO_DES_JS_CACHE = f.read()
        self.kingo_des_compiled = execjs.compile(_KINGO_DES_JS_CACHE)
    
    def encrypt(self, data: str, des_key: str) -> str:
        """DES 加密"""
        encrypted_hex = self.kingo_des_compiled.call("strEnc", data, des_key, None, None)
        encrypted_base64 = base64.b64encode(encrypted_hex.encode('utf-8')).decode('utf-8')
        return encrypted_base64


class SchoolCalendar:
    """校历数据管理"""
    
    @staticmethod
    def load_calendar() -> Dict[str, Any]:
        global _SCHOOL_CALENDAR_CACHE
        if _SCHOOL_CALENDAR_CACHE is None:
            with _INIT_LOCK:
                if _SCHOOL_CALENDAR_CACHE is None:
                    with open(_CALENDAR_PATH, 'r', encoding='utf-8') as f:
                        _SCHOOL_CALENDAR_CACHE = json.load(f)
        return _SCHOOL_CALENDAR_CACHE
    
    @staticmethod
    def get_term_info(school_year: str, term: str) -> Optional[Dict[str, Any]]:
        calendar = SchoolCalendar.load_calendar()
        return calendar.get(f"{school_year}-{term}")
    
    @staticmethod
    def get_first_monday(school_year: str, term: str) -> Optional[str]:
        term_info = SchoolCalendar.get_term_info(school_year, term)
        if term_info:
            start_date = term_info.get('termStartDate')
            if start_date:
                first_monday = datetime.strptime(start_date, "%Y-%m-%d")
                weekday = first_monday.weekday()
                if weekday != 0:
                    first_monday -= timedelta(days=weekday)
                return first_monday.strftime("%Y-%m-%d")
        return None


# ============ 登录与课表获取 ============
_thread_local = threading.local()


class XqeClient:
    """喜鹊儿登录与课表操作客户端
    
    线程安全：每个线程拥有独立的 requests.Session
    """
    
    DEFAULT_TIMEOUT = 5
    
    def __init__(self, base_url: str, timeout: Optional[int] = None):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.kingo_des = KingoDES()
    
    @property
    def session(self) -> requests.Session:
        if not hasattr(_thread_local, 'session'):
            _thread_local.session = requests.Session()
        return _thread_local.session
    
    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop('timeout', self.timeout)
        try:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            # 检测教务系统错误页面（频率限制等触发的重定向）
            if '/frame/errors/' in response.url:
                parsed = urlparse(response.url)
                qs = parse_qs(parsed.query)
                errormsg = unquote(qs.get('errormsg', [''])[0])
                raise Exception(f"教务系统返回错误：{errormsg or '未知错误'}")
            return response
        except Timeout:
            raise Timeout(f"教务系统服务器超时({self.timeout}s)")
        except RequestsConnectionError as e:
            raise RequestsConnectionError(f"教务系统服务状态异常({str(e)})") from e
        except RequestException as e:
            raise RequestException(f"连接到教务系统时出错({str(e)})") from e
    
    def login(self, username: str, password: str) -> 'requests.Session':
        """
        完成登录流程并返回会话
        
        合并步骤：获取动态参数 → 组合登录参数 → 提交登录
        """
        logger.debug("正在获取登录页面...")
        response = self._request('GET', f"{self.base_url}/cas/login.action")
        
        jsessionid = self.session.cookies.get('JSESSIONID')
        if not jsessionid:
            raise ValueError("登录过程失败，无法获取 JSESSIONID")
        
        match = re.search(r'var\s+_sessionid\s*=\s*"([A-F0-9]+)"', response.text)
        session_id = match.group(1) if match else None
        
        logger.debug("正在获取动态参数...")
        deskey = self._request('GET', f"{self.base_url}/frame/homepage?method=getTempDeskey").text.strip()
        nowtime = self._request('GET', f"{self.base_url}/frame/homepage?method=getTempNowtime").text.strip()
        
        if not session_id or not deskey or not nowtime:
            raise ValueError("登录过程失败，获取动态参数失败")
        
        logger.debug("正在构建登录参数...")
        params_u = XqeLibs.base64_encode(f"{username};;{session_id}")
        params_p = XqeLibs.md5(password + XqeLibs.md5(""))
        
        params_v1 = (
            f"_u={params_u}&_p={params_p}&randnumber=&isPasswordPolicy=1&"
            "txt_mm_expression=14&txt_mm_length=15&txt_mm_userzh=0&"
            "hid_flag=1&hidlag=1&hid_dxyzm="
        )
        
        token = XqeLibs.md5(XqeLibs.md5(params_v1) + XqeLibs.md5(nowtime))
        params_v1_encoded = self.kingo_des.encrypt(params_v1, deskey)
        
        params = f"params={params_v1_encoded}&token={token}&timestamp={nowtime}&deskey={deskey}&ssessionid={session_id}"
        
        logger.debug("正在提交登录...")
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f"{self.base_url}/cas/login.action",
            'Cookie': f"JSESSIONID={jsessionid}"
        }
        
        response = self._request('POST', f"{self.base_url}/cas/logon.action", data=params, headers=headers)
        result = response.json()
        if result.get("status") != "200":
            logger.warning(f"用户 {username} 登录失败：{result.get('message', '未知错误')}")
            raise Exception(f"登录失败: {result.get('message', '未知错误')}")
        
        logger.info(f"用户 {username} 登录成功")
        return self.session
    
    def get_timetable(self, school_year: str, term: str, user_code: str) -> str:
        """获取指定学期的课表 HTML"""
        jsessionid = self.session.cookies.get('JSESSIONID')
        
        headers = {
            "Referer": f"{self.base_url}/student/xkjg.wdkb.jsp?menucode=S20301",
            "Cookie": f"JSESSIONID={jsessionid}",
        }
        
        params_raw = f"xn={school_year}&xq={term}&xh={user_code}"
        params_encoded = XqeLibs.base64_encode(params_raw)
        
        url = f"{self.base_url}/student/wsxk.xskcb10319.jsp?params={params_encoded}"
        response = self._request('GET', url, headers=headers)
        
        return response.text


# ============ HTML 解析 ============
class Table2Json:
    """将 HTML 课表解析为 JSON 格式"""
    
    @staticmethod
    def parse_course_schedule(html_content: str) -> List[Dict[str, Any]]:
        """解析 HTML 并提取课程信息"""
        soup = BeautifulSoup(html_content, 'html.parser')
        weekdays_mapping = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7}
        
        courses = []
        
        table = soup.find('table', {'id': 'mytable'})
        if not table:
            return courses
        
        for row in table.find_all('tr')[1:]:
            if not row.find_all('td', class_='td1'):
                continue
            
            course_cells = row.find_all('td', class_='td')[:7]
            
            for i, cell in enumerate(course_cells[:7]):
                weekday = weekdays_mapping[i]
                
                for div in cell.find_all('div', style=lambda v: v and 'padding-bottom:5px;clear:both;' in v):
                    course_info = Table2Json._parse_course_div(div, weekday)
                    if course_info:
                        courses.append(course_info)
        
        return courses
    
    @staticmethod
    def _parse_course_div(div: BeautifulSoup, weekday: int) -> Optional[Dict[str, Any]]:
        """解析单个课程 div 元素"""
        try:
            title_tag = div.find('font', style='font-weight: bolder')
            if not title_tag:
                return None
            
            title = title_tag.get_text(strip=True)
            text_lines = [line.strip() for line in div.get_text(separator='|').split('|') if line.strip()]
            
            teacher = text_lines[1] if len(text_lines) > 1 else ""
            
            week_time_info = text_lines[2] if len(text_lines) > 2 else ""
            
            teaching_weeks = ""
            class_periods = ""
            if '[' in week_time_info and ']' in week_time_info:
                teaching_weeks = week_time_info.split('[')[0].strip()
                class_periods = week_time_info.split('[')[1].split(']')[0].strip()
            
            location = text_lines[3] if len(text_lines) > 3 else ""
            
            course_data = {
                "weekday": weekday,
                "title": title,
                "teacher": teacher.replace("教师:", "").strip(),
                "teaching_weeks": teaching_weeks,
                "class_periods": class_periods,
                "location": location
            }
            
            if not all([course_data["title"], course_data["teaching_weeks"], course_data["class_periods"]]):
                return None
            
            return course_data
        except Exception:
            return None


# ============ 主入口 ============
def main(
    username: str,
    once_md5_password: str,
    school_year: str = None,
    term: str = None,
    all_semesters: bool = True
) -> str:
    """
    主函数：获取课表并返回 JSON 字符串
    
    参数:
        username: 学号
        once_md5_password: MD5 哈希后的密码
        school_year: 指定学年（如 "2025"）
        term: 指定学期（如 "1"）
        all_semesters: 是否获取所有可用学期的课表
    
    返回:
        包含课表数据的 JSON 字符串
    """
    _init_logging()
    
    config = load_config()
    base_url = config.get('rootUrl')
    
    if not base_url:
        raise ValueError("未配置 base_url，请在 config.json 中设置 rootUrl")
    
    logger.info(f"获取课表: 用户={username}, 全部学期={all_semesters}")
    
    # 登录教务系统
    client = XqeClient(base_url)
    session = client.login(username, once_md5_password)
    
    available_semesters = get_available_semesters()[:8]
    timetable_config = load_timetable_config()
    
    if all_semesters:
        all_courses = []
        
        for sem_key in available_semesters:
            sem_year, sem_term = sem_key.split('-')
            
            logger.debug(f"获取学期: {sem_year}-{sem_term}")
            html = client.get_timetable(sem_year, sem_term, username)
            courses = Table2Json.parse_course_schedule(html)
            
            # 学期间延迟，避免触发频率限制
            time.sleep(0.2)
            
            if not courses:
                logger.debug(f"学期 {sem_year}-{sem_term} 无课程数据")
                continue
            
            first_monday = SchoolCalendar.get_first_monday(sem_year, sem_term)
            
            for course in courses:
                course['_schoolYear'] = sem_year
                course['_term'] = sem_term
                course['_first_monday'] = first_monday
            
            logger.info(f"学期 {sem_year}-{sem_term} 获取到 {len(courses)} 门课程")
            all_courses.extend(courses)
        
        result = {
            "timetable": timetable_config,
            "courses": all_courses
        }
    else:
        # 单学期模式
        if school_year is None or term is None:
            current_sem = available_semesters[0]
            school_year, term = current_sem.split('-')
        
        logger.debug(f"获取单学期: {school_year}-{term}")
        html = client.get_timetable(school_year, term, username)
        courses = Table2Json.parse_course_schedule(html)
        
        logger.info(f"学期 {school_year}-{term} 获取到 {len(courses)} 门课程")
        
        result = {
            "timetable": timetable_config,
            "courses": courses
        }
    
    logger.info(f"课程总数: {len(result['courses'])}")
    return json.dumps(result, ensure_ascii=False, indent=4)


# 兼容 xqe.py 的驼峰参数命名
def Main(username: str, onceMd5Password: str, school_year: str = None, term: str = None, all_semesters: bool = True) -> str:
    return main(username, onceMd5Password, school_year, term, all_semesters)
