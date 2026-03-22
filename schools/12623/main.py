"""
XiQueEr school module for code 12623.
Handles login, timetable fetching, and HTML parsing for this school.
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
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError as RequestsConnectionError
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# ============ Global caches ============
_KINGO_DES_JS_CACHE = None
_SCHOOL_CALENDAR_CACHE = None
_CONFIG_CACHE = None
_CALENDAR_PATH = os.path.join(os.path.dirname(__file__), 'school_calendar.json')
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
_TIMETABLE_CONFIG_CACHE = None


def _init_logging():
    """Initialize logging if not already done."""
    global logger
    if not logger.handlers:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def load_config() -> Dict[str, Any]:
    """Load school configuration from config.json."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            _CONFIG_CACHE = json.load(f)
    return _CONFIG_CACHE


def load_timetable_config() -> Dict[str, Any]:
    """Load timetable period configuration."""
    global _TIMETABLE_CONFIG_CACHE
    if _TIMETABLE_CONFIG_CACHE is None:
        config_path = os.path.join(os.path.dirname(__file__), 'timetable.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                _TIMETABLE_CONFIG_CACHE = json.load(f)
        except Exception:
            _TIMETABLE_CONFIG_CACHE = {}
    return _TIMETABLE_CONFIG_CACHE


def get_available_semesters() -> List[str]:
    """Get list of available semesters from school calendar."""
    calendar = SchoolCalendar.load_calendar()
    return list(calendar.keys())


# ============ Utility classes ============
class XqeLibs:
    """Helper utilities for encryption and encoding."""
    
    @staticmethod
    def md5(data: str) -> str:
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def base64_encode(data: str) -> str:
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')


class KingoDES:
    """DES encryption handler using JavaScript."""
    
    def __init__(self):
        global _KINGO_DES_JS_CACHE
        if _KINGO_DES_JS_CACHE is None:
            js_path = os.path.join(os.path.dirname(__file__), 'jkingo.des.js')
            with open(js_path, 'r', encoding='utf-8') as f:
                _KINGO_DES_JS_CACHE = f.read()
        self.kingo_des_compiled = execjs.compile(_KINGO_DES_JS_CACHE)
    
    def encrypt(self, data: str, des_key: str) -> str:
        """Encrypt data using DES."""
        encrypted_hex = self.kingo_des_compiled.call("strEnc", data, des_key, None, None)
        encrypted_base64 = base64.b64encode(encrypted_hex.encode('utf-8')).decode('utf-8')
        return encrypted_base64


class SchoolCalendar:
    """School calendar data handler."""
    
    @staticmethod
    def load_calendar() -> Dict[str, Any]:
        global _SCHOOL_CALENDAR_CACHE
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


# ============ Login and timetable fetching ============
_thread_local = threading.local()


class XqeClient:
    """Main client for XiQueEr login and timetable operations.
    
    Thread-safe: each thread gets its own requests.Session.
    """
    
    DEFAULT_TIMEOUT = 5
    
    def __init__(self, base_url: str, timeout: int = None):
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
            return response
        except Timeout:
            raise Timeout(f"教务系统服务器超时({self.timeout}s)")
        except RequestsConnectionError as e:
            raise ConnectionError(f"教务系统服务状态异常({str(e)})")
        except RequestException as e:
            raise RequestException(f"连接到教务系统时出错({str(e)})")
    
    def login(self, username: str, password: str) -> 'requests.Session':
        """
        Complete login flow and return session.
        Combines: GetDynamicParams + SignInParamsCombime + SignIn
        """
        try:
            logger.debug("Fetching login page...")
            response = self._request('GET', f"{self.base_url}/cas/login.action")
            
            jsessionid = self.session.cookies.get('JSESSIONID')
            if not jsessionid:
                raise ValueError("无法获取 JSESSIONID")
            
            match = re.search(r'var\s+_sessionid\s*=\s*"([A-F0-9]+)"', response.text)
            session_id = match.group(1) if match else None
            
            logger.debug("Fetching dynamic parameters...")
            deskey = self._request('GET', f"{self.base_url}/frame/homepage?method=getTempDeskey").text.strip()
            nowtime = self._request('GET', f"{self.base_url}/frame/homepage?method=getTempNowtime").text.strip()
            
            if not session_id or not deskey or not nowtime:
                raise ValueError("获取动态参数失败")
            
            logger.debug("Building login parameters...")
            params_u = XqeLibs.base64_encode(f"{username};;{session_id}")
            params_p = XqeLibs.md5(password + XqeLibs.md5(""))
            
            params_v1 = (
                f"_u={params_u}&_p={params_p}&randnumber=&isPasswordPolicy=1&"
                "txt_mm_expression=14&txt_mm_length=15&txt_mm_userzh=0&"
                "hid_flag=1&hidlag=1&hid_dxyzm="
            )
            
            token = XqeLibs.md5(XqeLibs.md5(params_v1) + XqeLibs.md5(nowtime))
            params_v1_encoded = self.kingo_des.encrypt(params_v1, deskey)
            
            params = f"params={params_v1_encoded}&token={token}&timestamp={nowtime}"
            params += f"&deskey={deskey}&ssessionid={session_id}"
            
            logger.debug("Submitting login...")
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f"{self.base_url}/cas/login.action",
                'Cookie': f"JSESSIONID={jsessionid}"
            }
            
            response = self._request('POST', f"{self.base_url}/cas/logon.action", data=params, headers=headers)
            result = response.json()
            if result.get("status") != "200":
                raise Exception(f"登录失败: {result.get('message', '未知错误')}")
            
            logger.info(f"Login successful for user: {username}")
            return self.session
        except (Timeout, RequestsConnectionError, RequestException):
            raise
        except Exception as e:
            raise
    
    def get_timetable(self, school_year: str, term: str, user_code: str) -> str:
        """Fetch timetable HTML for specified semester."""
        try:
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
        except (Timeout, RequestsConnectionError, RequestException):
            raise
        except Exception as e:
            raise


# ============ HTML parsing ============
class Table2Json:
    """Parse HTML timetable to JSON format."""
    
    @staticmethod
    def parse_course_schedule(html_content: str) -> List[Dict[str, Any]]:
        """Parse HTML and extract course information."""
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
        """Parse a single course div element."""
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


# ============ Main entry point ============
def main(
    username: str,
    once_md5_password: str,
    base_url: str = None,
    school_year: str = None,
    term: str = None,
    all_semesters: bool = True
) -> str:
    """
    Main function to fetch timetable and return as JSON.
    
    Args:
        username: Student ID
        once_md5_password: MD5 hashed password
        base_url: Optional base URL override
        school_year: Specific school year (e.g., "2025")
        term: Specific term (e.g., "1")
        all_semesters: Fetch all available semesters
    
    Returns:
        JSON string with timetable data
    """
    _init_logging()
    
    config = load_config()
    base_url = base_url or config.get('rootUrl')
    
    if not base_url:
        raise ValueError("未配置 base_url，请在 config.json 中设置 rootUrl")
    
    logger.info(f"Fetching timetable for user: {username}, all_semesters: {all_semesters}")
    
    # Login to system
    client = XqeClient(base_url)
    session = client.login(username, once_md5_password)
    
    available_semesters = get_available_semesters()
    timetable_config = load_timetable_config()
    
    if all_semesters:
        all_courses = []
        
        for sem_key in available_semesters:
            sem_year, sem_term = sem_key.split('-')
            
            logger.debug(f"Fetching semester: {sem_year}-{sem_term}")
            html = client.get_timetable(sem_year, sem_term, username)
            courses = Table2Json.parse_course_schedule(html)
            
            if not courses:
                logger.debug(f"No courses for semester {sem_year}-{sem_term}")
                continue
            
            first_monday = SchoolCalendar.get_first_monday(sem_year, sem_term)
            
            for course in courses:
                course['_schoolYear'] = sem_year
                course['_term'] = sem_term
                course['_first_monday'] = first_monday
            
            logger.info(f"Got {len(courses)} courses for {sem_year}-{sem_term}")
            all_courses.extend(courses)
        
        result = {
            "timetable": timetable_config,
            "courses": all_courses
        }
    else:
        # Single semester mode
        if school_year is None or term is None:
            current_sem = available_semesters[0]
            school_year, term = current_sem.split('-')
        
        logger.debug(f"Fetching single semester: {school_year}-{term}")
        html = client.get_timetable(school_year, term, username)
        courses = Table2Json.parse_course_schedule(html)
        
        logger.info(f"Got {len(courses)} courses for {school_year}-{term}")
        
        result = {
            "timetable": timetable_config,
            "courses": courses
        }
    
    logger.info(f"Total courses: {len(result['courses'])}")
    return json.dumps(result, ensure_ascii=False, indent=4)


# Alias for xqe.py compatibility (camelCase params)
def Main(username: str, onceMd5Password: str, base_url: str = None, school_year: str = None, term: str = None, all_semesters: bool = True) -> str:
    return main(username, onceMd5Password, base_url, school_year, term, all_semesters)
