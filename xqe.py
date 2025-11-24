import requests
import hashlib
import base64
import execjs
import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import threading

# 全局缓存，避免重复读取文件
_KINGO_DES_JS_CACHE = None
_TIMETABLE_DATA_CACHE = None
_CACHE_LOCK = threading.Lock()

class XqeLibs:
    @staticmethod
    def md5(data):
        return hashlib.md5(data.encode('utf-8')).hexdigest()
    
    @staticmethod
    def base64_encode(data):
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')
    
    @staticmethod
    def base64_decode(data):
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')
    

class KingoDES:
    def __init__(self):
        global _KINGO_DES_JS_CACHE
        with _CACHE_LOCK:
            if _KINGO_DES_JS_CACHE is None:
                with open('jkingo.des.js', 'r', encoding='utf-8') as f:
                    _KINGO_DES_JS_CACHE = f.read()
        
        # 每个实例独立编译JS执行环境
        self.kingoDesJs_compiled = execjs.compile(_KINGO_DES_JS_CACHE)
        
    def encrypt_data(self, data, des_key):
        """简化的加密函数"""
        encrypted_hex = self.kingoDesJs_compiled.call("strEnc", data, des_key, None, None)
        encrypted_base64 = base64.b64encode(encrypted_hex.encode('utf-8')).decode('utf-8')
        return encrypted_base64


class XqeLogin:
    def __init__(self, base_url):
        self.base_url = base_url
        # 每个实例独立的会话和加密模块
        self.session = requests.Session()
        self.kingoDes = KingoDES()

    def GetDynamicParams(self):
        """初始化加密模块与会话"""
        """获取Session$JSESSIONID"""
        url = f"{self.base_url}/cas/login.action"
        try:
            response = self.session.get(url)
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"网络请求错误：{e}")

        # 从Cookie获取JSESSIONID
        jsessionid = self.session.cookies.get('JSESSIONID')
        if not jsessionid:
            raise ValueError("无法获取JSESSIONID")
        
        # 获取Session ID
        content = response.text
        match = re.search(r'var\s+_sessionid\s*=\s*"([A-F0-9]+)"', content)
        sessionid = match.group(1) if match else None
        
        """获取deskey&nowtime"""
        # Get encryption parameters
        enc_url = f"{self.base_url}/custom/js/SetKingoEncypt.jsp"
        try:
            enc_response = self.session.get(enc_url)
            enc_response.raise_for_status()
        except Exception as e:
            raise Exception(f"获取加密参数失败：{e}")
        
        deskey_match = re.search(r'var _deskey = \'([^\']+)\'', enc_response.text)
        nowtime_match = re.search(r'var _nowtime = \'([^\']+)\'', enc_response.text)
        
        deskey = deskey_match.group(1) if deskey_match else None
        nowtime = nowtime_match.group(1) if nowtime_match else None

        # 错误检测
        if not jsessionid or not sessionid or not deskey or not nowtime:
            raise ValueError("获取动态参数失败")

        return jsessionid, sessionid, deskey, nowtime

    def SignInParamsCombime(self, originUsername, onceMd5Password, timestamp, deskey, session_id):
        """注意：传入的timestamp应当是服务器时间（格式为：2025-10-26 00:17:41）"""        
        ## 第一步最初的数据整合：_u=<base64:"学号;;sessionid">==&_p=<md5(密码)md5("")>&randnumber=&isPasswordPolicy=1&txt_mm_expression=14&txt_mm_length=15&txt_mm_userzh=0&hid_flag=1&hidlag=1&hid_dxyzm=
        params_u = XqeLibs.base64_encode(originUsername + ';;' + session_id)
        params_p = XqeLibs.md5(onceMd5Password + XqeLibs.md5("")) 

        paramsV1 = "_u=" + params_u + "&_p=" + params_p + "&randnumber=&isPasswordPolicy=1&txt_mm_expression=14&txt_mm_length=15&txt_mm_userzh=0&hid_flag=1&hidlag=1&hid_dxyzm="

        ## 生成token
        token = XqeLibs.md5(XqeLibs.md5(paramsV1) + XqeLibs.md5(timestamp))

        ## 第二步模拟动态加载的js模块的getEncParams()函数
        paramsV1_desEncoded = self.kingoDes.encrypt_data(paramsV1, deskey)

        paramsV2 = "params=" + paramsV1_desEncoded + "&token="+token+"&timestamp="+timestamp

        ## 第三部最后合并
        paramsV3 = paramsV2 + "&deskey=" + deskey + "&ssessionid=" + session_id
        
        return paramsV3

    def SignIn(self, params, jsessionid):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': f"{self.base_url}/cas/login.action",
            'Cookie': f"JSESSIONID={jsessionid}"
        }
        
        login_url = f"{self.base_url}/cas/logon.action"

        # 发送登录请求
        try:
            response = self.session.post(login_url, data=params, headers=headers)
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"网络请求错误： {e}")

        # 判断登录结果
        try:
            response_json = json.loads(response.text)
        except json.JSONDecodeError:
            raise Exception("登录响应格式错误")
            
        if response_json.get("status") != "200":
            raise Exception(f"登录失败: {response_json.get('message', '未知错误')}")
        
        ## 获取新的JSESSIONID
        updatedJsessionId = response.cookies.get('JSESSIONID')
        if not updatedJsessionId:
            raise Exception("登录后未能获取新的JSESSIONID")
        
        return updatedJsessionId


class Table2Json:

    @staticmethod
    def parse_course_schedule(html_content):
        """
        解析HTML课程表，提取周一到周日的课程信息
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 星期映射（数字表示）
        weekdays_mapping = {
            0: 1,  # 星期一 -> 1
            1: 2,  # 星期二 -> 2
            2: 3,  # 星期三 -> 3
            3: 4,  # 星期四 -> 4
            4: 5,  # 星期五 -> 5
            5: 6,  # 星期六 -> 6
            6: 7   # 星期日 -> 7
        }
        
        courses = []
        
        # 找到课程表主体
        table = soup.find('table', {'id': 'mytable'})
        if not table:
            return courses
        
        # 获取所有行
        rows = table.find_all('tr')
        
        # 跳过表头行
        for row in rows[1:]:
            # 获取时间段信息（上午、下午、晚上）
            time_period_cells = row.find_all('td', class_='td1')
            if not time_period_cells:
                continue
                
            # 获取课程单元格（周一到周日）
            course_cells = row.find_all('td', class_='td')[:7]  # 取7列（周一到周日）
            
            for i, cell in enumerate(course_cells):
                if i >= 7:  # 只处理周一到周日
                    break
                    
                weekday = weekdays_mapping[i]
                
                # 查找所有课程div
                course_divs = cell.find_all('div', style=lambda value: value and 'padding-bottom:5px;clear:both;' in value)
                
                for div in course_divs:
                    course_info = Table2Json.parse_course_div(div, weekday)
                    if course_info:
                        courses.append(course_info)
        
        return courses

    @staticmethod
    def parse_course_div(div, weekday):
        """
        解析单个课程div的信息
        """
        try:
            # 提取课程标题
            title_tag = div.find('font', style='font-weight: bolder')
            if not title_tag:
                return None
                
            title = title_tag.get_text(strip=True)
            
            # 提取所有文本并按换行分割
            text_lines = div.get_text(separator='|').split('|')
            text_lines = [line.strip() for line in text_lines if line.strip()]
            
            # 教师信息通常在第二行
            teacher = text_lines[1] if len(text_lines) > 1 else ""
            
            # 周次和节次信息通常在第三行
            week_time_info = text_lines[2] if len(text_lines) > 2 else ""
            
            # 解析教学周
            teaching_weeks = ""
            # 解析节次
            class_periods = ""
            
            if '[' in week_time_info and ']' in week_time_info:
                # 提取括号前的内容作为教学周
                teaching_weeks = week_time_info.split('[')[0].strip()
                # 提取括号内的内容作为节次
                class_periods = week_time_info.split('[')[1].split(']')[0].strip()
            
            # 地点信息通常在第四行
            location = text_lines[3] if len(text_lines) > 3 else ""
            
            # 改进的课程信息处理
            course_data = {
                "weekday": weekday,
                "title": title,
                "teacher": teacher.replace("教师:", "").strip(),
                "teaching_weeks": teaching_weeks,
                "class_periods": class_periods,
                "location": location
            }
            
            # 数据验证
            if not all([course_data["title"], course_data["teaching_weeks"], course_data["class_periods"]]):
                return None
                
            return course_data
            
        except Exception as e:
            raise Exception(f"解析课程信息时出错: {e}")

    @staticmethod
    def main(html_content):
        # 解析课程信息
        courses = Table2Json.parse_course_schedule(html_content)
        return json.dumps(courses, ensure_ascii=False, indent=4)


class Json2Ics:
    def __init__(self, remind_time="15"):
        """
        初始化ICS生成器
        Args:
            remind_time: 提醒时间（分钟），-1表示禁用，0表示开始时，正数表示提前分钟数
        """
        global _TIMETABLE_DATA_CACHE
        with _CACHE_LOCK:
            if _TIMETABLE_DATA_CACHE is None:
                try:
                    with open("timetable.json", "r", encoding="utf-8") as f:
                        timetable_data = json.load(f)
                        # 扩展数据结构，支持开学日期配置
                        _TIMETABLE_DATA_CACHE = {
                            "timetable": timetable_data,
                            "first_monday": timetable_data.get("first_monday", "2025-09-01")  # 默认值
                        }
                except Exception as e:
                    raise Exception(f"无法读取timetable文件: {e}")
        
        self.settingTimetable = _TIMETABLE_DATA_CACHE["timetable"]
        self.first_monday = _TIMETABLE_DATA_CACHE["first_monday"]
        self.remind_time = remind_time
    
    def parse_weeks(self, weeks_str):
        """解析教学周字符串"""
        if not weeks_str:
            return []
            
        weeks = []
        parts = str(weeks_str).split(',')
        for part in parts:
            part = part.strip()
            
            # 检查是否为单双周格式
            is_odd = '单' in part  # 单周
            is_even = '双' in part  # 双周
            
            # 移除单双周标识符，获取纯数字部分
            clean_part = part.replace('单', '').replace('双', '').strip()
            
            if '-' in clean_part:
                try:
                    start, end = map(int, clean_part.split('-'))
                    week_range = list(range(start, end + 1))
                    
                    # 根据单双周过滤
                    if is_odd:
                        week_range = [week for week in week_range if week % 2 == 1]  # 奇数周
                    elif is_even:
                        week_range = [week for week in week_range if week % 2 == 0]  # 偶数周
                    
                    weeks.extend(week_range)
                except ValueError:
                    raise Exception(f"无效的周次范围: {part}")
            else:
                try:
                    week = int(clean_part)
                    # 检查单双周限制
                    if (is_odd and week % 2 == 1) or (is_even and week % 2 == 0) or (not is_odd and not is_even):
                        weeks.append(week)
                    # 如果指定了单双周但不匹配，则不添加（如"5 双"）
                except ValueError:
                    raise Exception(f"无效的周次: {part}")
        
        return weeks
    
    def parse_periods(self, periods_str):
        """解析节次字符串"""
        if not periods_str:
            return []
            
        periods = []
        parts = str(periods_str).split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    periods.extend(range(start, end + 1))
                except ValueError:
                    raise Exception(f"无效的节次范围: {part}")
            else:
                try:
                    periods.append(int(part))
                except ValueError:
                    raise Exception(f"无效的节次: {part}")
        return periods
    
    def get_time_range(self, periods):
        """根据节次列表获取时间范围"""
        if not periods:
            return None, None
        
        start_period = min(periods)
        end_period = max(periods)
        
        start_time_str = self.settingTimetable.get(str(start_period), "").split('-')[0]
        end_time_str = self.settingTimetable.get(str(end_period), "").split('-')[1]
        
        return start_time_str, end_time_str
    
    def calculate_date(self, week_num, weekday):
        """计算具体日期"""
        # 从配置中读取开学日期
        first_monday = datetime.strptime(self.first_monday, "%Y-%m-%d")
        target_date = first_monday + timedelta(days=(week_num - 1) * 7 + (weekday - 1))
        return target_date
    
    def generate_alarm_component(self):
        """生成提醒组件"""
        if self.remind_time == "-1" or int(self.remind_time) < 0:
            return []  # 禁用通知
        
        alarm_component = []
        alarm_component.append("BEGIN:VALARM")
        alarm_component.append("ACTION:DISPLAY")
        alarm_component.append("DESCRIPTION:课程提醒")
        
        # 设置提醒时间
        if self.remind_time == "0":
            # 事件开始时提醒
            alarm_component.append("TRIGGER;RELATED=START:PT0M")
        else:
            # 提前指定分钟提醒
            alarm_component.append(f"TRIGGER:-PT{self.remind_time}M")
        
        alarm_component.append("END:VALARM")
        return alarm_component
    
    def generate_ics_content(self, courses_data):
        """生成ICS文件内容并返回字符串"""
        ics_content = []
        ics_content.append("BEGIN:VCALENDAR")
        ics_content.append("VERSION:2.0")
        ics_content.append("PRODID:-//Course Schedule Generator//")
        ics_content.append("CALSCALE:GREGORIAN")
        ics_content.append("METHOD:PUBLISH")
        ics_content.append("X-WR-CALNAME:喜鹊儿")
        
        # 添加时区定义
        ics_content.append("BEGIN:VTIMEZONE")
        ics_content.append("TZID:Asia/Shanghai")
        ics_content.append("X-LIC-LOCATION:Asia/Shanghai")
        ics_content.append("BEGIN:STANDARD")
        ics_content.append("TZOFFSETFROM:+0800")
        ics_content.append("TZOFFSETTO:+0800")
        ics_content.append("TZNAME:CST")
        ics_content.append("DTSTART:19700101T000000")
        ics_content.append("END:STANDARD")
        ics_content.append("END:VTIMEZONE")
        
        event_count = 0
        
        for course in courses_data:
            try:
                teaching_weeks = self.parse_weeks(course['teaching_weeks'])
                class_periods = self.parse_periods(course['class_periods'])
                
                if not teaching_weeks or not class_periods:
                    continue
                
                start_time_str, end_time_str = self.get_time_range(class_periods)
                if not start_time_str or not end_time_str:
                    raise Exception(f"无法获取课程时间范围: {course['title']}")
                
                for week_num in teaching_weeks:
                    date = self.calculate_date(week_num, course['weekday'])
                    
                    # 格式化时间
                    start_datetime = datetime.strptime(f"{date.strftime('%Y%m%d')} {start_time_str}", "%Y%m%d %H:%M")
                    end_datetime = datetime.strptime(f"{date.strftime('%Y%m%d')} {end_time_str}", "%Y%m%d %H:%M")
                    
                    # 生成唯一ID
                    event_uid = f"{course['title']}_{week_num}_{course['weekday']}_{start_time_str}@courses"
                    
                    # 添加事件（带时区）
                    ics_content.append("BEGIN:VEVENT")
                    ics_content.append(f"SUMMARY:{course['title']}")
                    ics_content.append(f"DESCRIPTION:教师: {course['teacher']}\\n教学周: {course['teaching_weeks']}\\n节次: {course['class_periods']}")
                    ics_content.append(f"LOCATION:{course['location']}")
                    ics_content.append(f"DTSTART;TZID=Asia/Shanghai:{start_datetime.strftime('%Y%m%dT%H%M%S')}")
                    ics_content.append(f"DTEND;TZID=Asia/Shanghai:{end_datetime.strftime('%Y%m%dT%H%M%S')}")
                    ics_content.append(f"UID:{event_uid}")
                    
                    # 添加 Outlook 特定的提醒属性（在 VEVENT 级别）
                    if self.remind_time != "-1" and int(self.remind_time) >= 0:
                        # REMINDERMINUTESBEFORESTART 是 Outlook 特定的属性
                        ics_content.append(f"REMINDERMINUTESBEFORESTART:{self.remind_time}")

                    # 添加提醒
                    alarm_lines = self.generate_alarm_component()
                    ics_content.extend(alarm_lines)
                    
                    ics_content.append("END:VEVENT")
                    
                    event_count += 1
                    
            except Exception as e:
                raise Exception(f"处理课程信息时出错: {e}, 课程: {course}")
        
        ics_content.append("END:VCALENDAR")
        
        result = '\n'.join(ics_content)
        return result
    
    def main(self, courses_str):
        courses_json = json.loads(courses_str)
        return self.generate_ics_content(courses_json)    


class XqeTablePull:
    @staticmethod
    def GetTableParams(jsessionid, base_url):
        # 请求课表
        headers = {
            "Referer": f"{base_url}/jw/common/showYearTerm.action",
            "Cookie": f"JSESSIONID={jsessionid}",
        }
        try:
            response = requests.get(f"{base_url}/jw/common/showYearTerm.action", headers=headers)
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"获取个人信息时出错: {e}")
        
        # 匹配结果
        try:
            response_json = json.loads(response.text)
            schoolYear = response_json['xn']
            term = response_json['xqM']
            userCode = response_json['userCode']
        except (KeyError, json.JSONDecodeError) as e:
            raise Exception(f"解析用户信息失败: {e}")

        if not schoolYear or not term:
            raise Exception("无法获取用户信息")
        return schoolYear, term, userCode
        
    @staticmethod    
    def GetTable(jsessionid, schoolYear, term, userCode, base_url):
        headers = {
            "Referer": f"{base_url}/student/xkjg.wdkb.jsp?menucode=S20301",
            "Cookie": f"JSESSIONID={jsessionid}",
        }

        # 合成参数
        params = XqeLibs.base64_encode(f"xn={schoolYear}&xq={term}&xh={userCode}")

        # 请求课表
        try:
            response = requests.get(f"{base_url}/student/wsxk.xskcb10319.jsp?params={params}", headers=headers)
            response.raise_for_status()
        except Exception as e:
            raise Exception(f"从教务系统获取课表时出现错误：{e}")

        return response.text


def Main(username, onceMd5Password, base_url, remindTime):
    """
    主函数：获取课程表ICS内容
    输入: 用户名, 密码, 主页链接, 提醒时间
    输出: ICS格式的课程表内容
    """
    xqel = XqeLogin(base_url)

    # 获取动态参数
    jsessionid, sessionid, deskey, nowtime = xqel.GetDynamicParams()

    # 生成登录参数
    signInParams = xqel.SignInParamsCombime(username, onceMd5Password, nowtime, deskey, sessionid)

    # 登录
    jsessionid = xqel.SignIn(signInParams, jsessionid)

    # 获取课表参数
    schoolYear, term, userCode = XqeTablePull.GetTableParams(jsessionid, base_url)
    
    # 请求课表
    xqeTable_html = XqeTablePull.GetTable(jsessionid, schoolYear, term, userCode, base_url)
    
    # 转换到JSON
    courses = Table2Json.main(xqeTable_html)

    # 转换为ICS
    json2ics = Json2Ics(remind_time=remindTime)
    ics_content = json2ics.main(courses)


    return ics_content
