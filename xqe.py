import os
import sys
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
import importlib.util
import threading

# 全局缓存与线程锁
_SCHOOL_MODULE_CACHE = {}
_MODULE_LOCK = threading.Lock()
_TIMETABLE_DATA_CACHE = None
_TIMETABLE_LOCK = threading.Lock()
_FILE_LOCK = threading.Lock()

USER_DIR_BASE = "user"
CACHE_MINUTES = 40
STALE_DAYS = 14


def get_user_dir(school_code: str, username: str) -> str:
    return os.path.join(USER_DIR_BASE, school_code, username)


def get_cache_path(school_code: str, username: str) -> str:
    return os.path.join(get_user_dir(school_code, username), "cache.json")


def get_user_info_path(school_code: str, username: str) -> str:
    return os.path.join(get_user_dir(school_code, username), "user_info.json")


def is_user_exists(school_code: str, username: str) -> bool:
    return os.path.exists(get_user_info_path(school_code, username))


def load_user_info(school_code: str, username: str) -> Dict[str, Any]:
    path = get_user_info_path(school_code, username)
    if os.path.exists(path):
        with _FILE_LOCK:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}


def save_user_info(school_code: str, username: str, info: Dict[str, Any]):
    user_dir = get_user_dir(school_code, username)
    os.makedirs(user_dir, exist_ok=True)
    path = get_user_info_path(school_code, username)
    with _FILE_LOCK:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=4)


def load_cache(school_code: str, username: str) -> Dict[str, Any]:
    path = get_cache_path(school_code, username)
    if os.path.exists(path):
        with _FILE_LOCK:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}


def save_cache(school_code: str, username: str, data: Dict[str, Any]):
    user_dir = get_user_dir(school_code, username)
    os.makedirs(user_dir, exist_ok=True)
    path = get_cache_path(school_code, username)
    with _FILE_LOCK:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def is_cache_fresh(school_code: str, username: str) -> bool:
    info = load_user_info(school_code, username)
    last_fetch = info.get('last_fetch_time')
    if not last_fetch:
        return False
    try:
        last_fetch_dt = datetime.fromisoformat(last_fetch)
        diff = datetime.now() - last_fetch_dt
        return diff.total_seconds() < CACHE_MINUTES * 60
    except (ValueError, TypeError):
        return False


class SchoolDispatcher:
    @staticmethod
    def load_school_module(school_code: str):
        with _MODULE_LOCK:
            if school_code in _SCHOOL_MODULE_CACHE:
                return _SCHOOL_MODULE_CACHE[school_code]
            
            module_path = os.path.join('schools', school_code, 'main.py')
            if not os.path.exists(module_path):
                raise ValueError(f"学校代码 {school_code} 不存在")
            
            spec = importlib.util.spec_from_file_location(f"school_{school_code}", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            _SCHOOL_MODULE_CACHE[school_code] = module
            return module
    
    @staticmethod
    def get_timetable(school_code: str, username: str, password: str, 
                      school_year: str = None, term: str = None, all_semesters: bool = False, **kwargs) -> Dict[str, Any]:
        module = SchoolDispatcher.load_school_module(school_code)
        
        result_json = module.Main(username, password, school_year, term, all_semesters)
        
        if isinstance(result_json, str):
            return json.loads(result_json)
        return result_json


class TimetableParser:
    @staticmethod
    def parse_weeks(weeks_str: str) -> List[int]:
        if not weeks_str:
            return []
        
        numbers = []
        
        parts = str(weeks_str).split(',')
        for part in parts:
            part = part.strip()
            is_odd = '单' in part
            is_even = '双' in part
            
            clean_part = part.replace('单', '').replace('双', '').strip()
            
            if '-' in clean_part:
                try:
                    start, end = map(int, clean_part.split('-'))
                    range_nums = list(range(start, end + 1))
                    if is_odd:
                        range_nums = [n for n in range_nums if n % 2 == 1]
                    elif is_even:
                        range_nums = [n for n in range_nums if n % 2 == 0]
                    numbers.extend(range_nums)
                except ValueError:
                    pass
            else:
                try:
                    num = int(clean_part)
                    if (is_odd and num % 2 == 1) or (is_even and num % 2 == 0) or (not is_odd and not is_even):
                        numbers.append(num)
                except ValueError:
                    pass
        
        return numbers
    
    @staticmethod
    def parse_periods(periods_str: str) -> List[int]:
        if not periods_str:
            return []
        
        numbers = []
        parts = str(periods_str).split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    numbers.extend(range(start, end + 1))
                except ValueError:
                    pass
            else:
                try:
                    numbers.append(int(part))
                except ValueError:
                    pass
        return numbers


class SchoolCalendar:
    def __init__(self, calendar_path: str = None):
        self.calendar = {}
        if calendar_path and os.path.exists(calendar_path):
            with open(calendar_path, 'r', encoding='utf-8') as f:
                self.calendar = json.load(f)
    
    def get_first_monday(self, school_year: str, term: str) -> Optional[str]:
        key = f"{school_year}-{term}"
        if key in self.calendar:
            start_date = self.calendar[key].get('termStartDate')
            if start_date:
                first_monday = datetime.strptime(start_date, "%Y-%m-%d")
                weekday = first_monday.weekday()
                if weekday != 0:
                    first_monday -= timedelta(days=weekday)
                return first_monday.strftime("%Y-%m-%d")
        return None
    
    def get_term_info(self, school_year: str, term: str) -> Optional[Dict[str, Any]]:
        key = f"{school_year}-{term}"
        return self.calendar.get(key)


class ICSBuilder:
    def __init__(self, remind_time: str = "15", calendar_path: str = None, timetable_config: Dict[str, str] = None, school_code: str = None):
        self.remind_time = remind_time
        self.calendar = SchoolCalendar(calendar_path)
        self.timetable = timetable_config or self._load_default_timetable(school_code)
        
        self._events: List[Dict[str, Any]] = []
    
    def _load_default_timetable(self, school_code: str = None) -> Dict[str, str]:
        global _TIMETABLE_DATA_CACHE
        
        if school_code:
            school_timetable_path = os.path.join('schools', school_code, 'timetable.json')
            if os.path.exists(school_timetable_path):
                try:
                    with open(school_timetable_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
        
        with _TIMETABLE_LOCK:
            if _TIMETABLE_DATA_CACHE is None:
                try:
                    with open("timetable.json", "r", encoding="utf-8") as f:
                        _TIMETABLE_DATA_CACHE = json.load(f)
                except Exception:
                    _TIMETABLE_DATA_CACHE = {}
        return _TIMETABLE_DATA_CACHE
    
    def get_time_range(self, periods: List[int]) -> Tuple[Optional[str], Optional[str]]:
        if not periods:
            return None, None
        
        start_period = min(periods)
        end_period = max(periods)
        
        start_time = self.timetable.get(str(start_period), "00:00-00:00").split('-')[0]
        end_time = self.timetable.get(str(end_period), "00:00-00:00").split('-')[1]
        
        return start_time or None, end_time or None
    
    def calculate_date(self, week_num: int, weekday: int, first_monday: str) -> datetime.date:
        first_monday_date = datetime.strptime(first_monday, "%Y-%m-%d").date()
        delta_days = (week_num - 1) * 7 + (weekday - 1)
        return first_monday_date + timedelta(days=delta_days)
    
    def add_course(self, course: Dict[str, Any], school_year: str = None, term: str = None, 
                   first_monday: str = None):
        teaching_weeks = TimetableParser.parse_weeks(course.get('teaching_weeks', ''))
        class_periods = TimetableParser.parse_periods(course.get('class_periods', ''))
        
        if not teaching_weeks or not class_periods:
            return
        
        start_time_str, end_time_str = self.get_time_range(class_periods)
        if not start_time_str or not end_time_str:
            return
        
        if not first_monday and school_year and term:
            first_monday = self.calendar.get_first_monday(school_year, term)
        
        if not first_monday:
            return
        
        weekday = course.get('weekday', 1)
        
        for week_num in teaching_weeks:
            date = self.calculate_date(week_num, weekday, first_monday)
            
            start_datetime = datetime.strptime(f"{date} {start_time_str}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{date} {end_time_str}", "%Y-%m-%d %H:%M")
            
            event = {
                'title': course.get('title', ''),
                'teacher': course.get('teacher', ''),
                'location': course.get('location', ''),
                'teaching_weeks': course.get('teaching_weeks', ''),
                'class_periods': course.get('class_periods', ''),
                'weekday': weekday,
                'week_num': week_num,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
            }
            self._events.append(event)
    
    def add_courses_from_dict(self, courses_data: Dict[str, Any]):
        courses = courses_data.get('courses', [])
        
        for course in courses:
            if '_schoolYear' in course and '_term' in course:
                school_year = course.get('_schoolYear')
                term = course.get('_term')
                first_monday = course.get('_first_monday')
                self.add_course(course, school_year, term, first_monday)
            else:
                school_year = courses_data.get('schoolYear')
                term = courses_data.get('term')
                first_monday = courses_data.get('first_monday')
                self.add_course(course, school_year, term, first_monday)
    
    def add_error_event(self, reason: str, last_fetch_time: str):
        last_fetch_dt = datetime.fromisoformat(last_fetch_time)
        if last_fetch_dt.tzinfo is None:
            last_fetch_dt = last_fetch_dt.astimezone()
        start_datetime = (last_fetch_dt + timedelta(days=STALE_DAYS)).date()
        end_datetime = start_datetime + timedelta(days=1)
        last_fetch_display = last_fetch_dt.strftime("%Y-%m-%d %H:%M:%S")

        event = {
            'title': f'⚠️课表过期且无法更新⚠️-{reason}',
            'description': f"上次成功从教务系统获取时间：{last_fetch_display}\n\n\n当你看到这个那么代表课表已经超过{STALE_DAYS}天未更新，而且尝试更新时遇到了【{reason}】问题，导致无法更新。\n如需帮助请访问blog.hishutdown.cn/?p=201",
            'is_all_day': True,
            'start_datetime': datetime.combine(start_datetime, datetime.min.time()),
            'end_datetime': datetime.combine(end_datetime, datetime.min.time()),
        }
        self._events.append(event)
    
    def _generate_alarm_component(self) -> List[str]:
        if self.remind_time == "-1" or int(self.remind_time) < 0:
            return []
        
        alarm = [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:课程提醒"
        ]
        
        if self.remind_time == "0":
            alarm.append("TRIGGER;RELATED=START:PT0M")
        else:
            alarm.append(f"TRIGGER:-PT{self.remind_time}M")
        
        alarm.append("END:VALARM")
        return alarm
    
    def _escape_ics_text(self, text: str) -> str:
        text = text.replace('\\', '\\\\')
        text = text.replace(';', '\\;')
        text = text.replace(',', '\\,')
        text = text.replace('\n', '\\n')
        return text
    
    def export(self) -> str:
        ics_lines = []
        
        ics_lines.append("BEGIN:VCALENDAR")
        ics_lines.append("VERSION:2.0")
        ics_lines.append("PRODID:-//Course Schedule Generator//")
        ics_lines.append("CALSCALE:GREGORIAN")
        ics_lines.append("METHOD:PUBLISH")
        ics_lines.append("X-WR-CALNAME:喜鹊儿")
        
        ics_lines.extend([
            "BEGIN:VTIMEZONE",
            "TZID:Asia/Shanghai",
            "X-LIC-LOCATION:Asia/Shanghai",
            "BEGIN:STANDARD",
            "TZOFFSETFROM:+0800",
            "TZOFFSETTO:+0800",
            "TZNAME:CST",
            "DTSTART:19700101T000000",
            "END:STANDARD",
            "END:VTIMEZONE"
        ])
        
        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        
        for event in self._events:
            start_datetime = event['start_datetime']
            end_datetime = event['end_datetime']
            
            is_all_day = event.get('is_all_day', False)
            
            event_uid = f"{event.get('title', 'event')}_{start_datetime.strftime('%Y%m%d')}@courses"
            
            ics_lines.append("BEGIN:VEVENT")
            ics_lines.append(f"SUMMARY:{self._escape_ics_text(event['title'])}")
            if is_all_day:
                ics_lines.append(f"DESCRIPTION:{self._escape_ics_text(event.get('description', ''))}")
                ics_lines.append(f"DTSTART;VALUE=DATE:{start_datetime.strftime('%Y%m%d')}")
                ics_lines.append(f"DTEND;VALUE=DATE:{end_datetime.strftime('%Y%m%d')}")
            else:
                ics_lines.append(f"DESCRIPTION:教师: {self._escape_ics_text(event.get('teacher', ''))}\\n教学周: {self._escape_ics_text(event.get('teaching_weeks', ''))}\\n节次: {self._escape_ics_text(event.get('class_periods', ''))}")
                ics_lines.append(f"LOCATION:{self._escape_ics_text(event.get('location', ''))}")
                ics_lines.append(f"DTSTART;TZID=Asia/Shanghai:{start_datetime.strftime('%Y%m%dT%H%M%S')}")
                ics_lines.append(f"DTEND;TZID=Asia/Shanghai:{end_datetime.strftime('%Y%m%dT%H%M%S')}")
            
            ics_lines.append(f"DTSTAMP:{dtstamp}")
            ics_lines.append(f"UID:{event_uid}")
            
            if not is_all_day:
                ics_lines.extend(self._generate_alarm_component())
            
            ics_lines.append("END:VEVENT")
        
        ics_lines.append("END:VCALENDAR")
        return '\n'.join(ics_lines)


def Main(username: str, onceMd5Password: str, remindTime: str,
         school_code: str, school_year: str = None, term: str = None, 
         all_semesters: bool = True, force: bool = False, **kwargs) -> str:
    
    now = datetime.now().isoformat()
    school_calendar_path = os.path.join('schools', school_code, 'school_calendar.json')
    user_exists = is_user_exists(school_code, username)
    
    if not user_exists or force:
        try:
            school_data = SchoolDispatcher.get_timetable(
                school_code, username, onceMd5Password,
                school_year=school_year, term=term, all_semesters=all_semesters, **kwargs
            )
        except Exception as e:
            if force:
                if user_exists:
                    info = load_user_info(school_code, username)
                    info["last_access_time"] = now
                    save_user_info(school_code, username, info)
                raise e
            raise e
        
        save_cache(school_code, username, school_data)
        
        info = {
            "last_access_time": now,
            "last_fetch_time": now
        }
        save_user_info(school_code, username, info)
    else:
        info = load_user_info(school_code, username)
        
        if is_cache_fresh(school_code, username):
            school_data = load_cache(school_code, username)
            info["last_access_time"] = now
            save_user_info(school_code, username, info)
        else:
            try:
                school_data = SchoolDispatcher.get_timetable(
                    school_code, username, onceMd5Password,
                    school_year=school_year, term=term, all_semesters=all_semesters, **kwargs
                )
                
                save_cache(school_code, username, school_data)
                info["last_access_time"] = now
                info["last_fetch_time"] = now
                save_user_info(school_code, username, info)
                
            except Exception as e:
                last_fetch = info.get("last_fetch_time", "")
                
                if last_fetch:
                    try:
                        last_fetch_dt = datetime.fromisoformat(last_fetch)
                        days_since = (datetime.now() - last_fetch_dt).days
                    except (ValueError, TypeError):
                        days_since = 0
                else:
                    days_since = 0
                
                if days_since >= STALE_DAYS:
                    school_data = load_cache(school_code, username)
                    if school_data and school_data.get('courses'):
                        timetable_config = school_data.get('timetable', {})
                        ics_builder = ICSBuilder(
                            remind_time=remindTime,
                            calendar_path=school_calendar_path,
                            timetable_config=timetable_config,
                            school_code=school_code
                        )
                        ics_builder.add_courses_from_dict(school_data)
                        ics_builder.add_error_event(str(e), last_fetch)
                        
                        info["last_access_time"] = now
                        save_user_info(school_code, username, info)
                        
                        return ics_builder.export()
                
                raise e
    
    timetable_config = school_data.get('timetable', {})
    
    ics_builder = ICSBuilder(
        remind_time=remindTime,
        calendar_path=school_calendar_path,
        timetable_config=timetable_config,
        school_code=school_code
    )
    
    ics_builder.add_courses_from_dict(school_data)
    
    return ics_builder.export()


if __name__ == "__main__":
    if len(sys.argv) >= 5:
        username = sys.argv[1]
        onceMd5Password = sys.argv[2]
        remindTime = sys.argv[3]
        school_code = sys.argv[4]
        force = sys.argv[5].lower() == "true" if len(sys.argv) > 5 else False
        school_year = sys.argv[6] if len(sys.argv) > 6 else None
        term = sys.argv[7] if len(sys.argv) > 7 else None

        
        o = Main(username=username, onceMd5Password=onceMd5Password, remindTime=remindTime,
                 school_code=school_code, school_year=school_year, term=term, force=force)
        choice = input("save or print? (s/P): ").strip().lower()
        if choice == "s":
            open("test.ics", "w", encoding="utf-8").write(o)
            print("File saved as test.ics")
        else:
            print (o)
    else:
        print("用法: python xqe.py <username> <onceMd5Password> <remindTime> <school_code> [FORCE] [school_year] [term]")
    
