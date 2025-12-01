from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response
import re
import tempfile
import logging
from urllib.parse import urlparse

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="XiQueEr To ICS",
    description="从喜鹊儿获取课表的工具",
    root_path="/xqe2ics/subscribe/v1" # root_path用于供生产环境中反向代理使用
)  

def validate_student_id(student_id: str) -> bool:
    """验证学号是否为纯数字"""
    return student_id.isdigit()

def validate_password(password: str) -> bool:
    """验证密码格式：32位小写MD5"""
    return bool(re.fullmatch(r'^[a-f0-9]{32}$', password))

def validate_and_normalize_site(site: str) -> str:
    """验证并标准化 site URL"""
    # 兼容v1.0.0-Beta版本（无法自定义地址）
    if not site:
        return "http://202.103.141.242"
    
    # 去除末尾斜杠
    site = site.rstrip('/')
    
    # 验证是否为合法的 HTTP/HTTPS URL
    parsed = urlparse(site)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("site 必须是有效的 HTTP 或 HTTPS URL")
    
    return site

@app.get("/{student_id}.ics")
async def get_ics_file(
    student_id: str,
    pwd: str = Query(..., description="用户密码（32位小写MD5）"),
    site: str = Query(None, description="站点地址，默认为 http://202.103.141.242"),
    remindTime: int = Query(30, description="提醒时间（分钟），默认为30")
):
    """
    获取ICS日历文件
    - student_id: 学号
    - pwd: 用户密码（32位小写MD5）
    - site: 可选，站点地址，默认为 http://202.103.141.242
    - remindTime: 可选，提醒时间（分钟），默认为30
    """
    pwd = pwd.lower()

    # 验证学号格式
    if not validate_student_id(student_id):
        logger.warning(f"Invalid student ID format: {student_id}")
        raise HTTPException(status_code=400, detail="学号格式错误")
    
    # 验证密码格式
    if not validate_password(pwd):
        logger.warning(f"Invalid password format for student ID: {student_id}")
        raise HTTPException(status_code=400, detail="密码不符合32位小写MD5格式")
    
    # 验证并标准化 site
    try:
        normalized_site = validate_and_normalize_site(site)
    except ValueError as e:
        logger.warning(f"Invalid site format: {site} - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    logger.info(f"Valid request for student ID: {student_id}, site: {normalized_site}, remindTime: {remindTime}")
    
    try:
        import xqe
        result = xqe.Main(
            username=student_id,
            onceMd5Password=pwd,
            base_url=normalized_site,
            remindTime=remindTime
        )
        
        if isinstance(result, str) and result.startswith("BEGIN:VCALENDAR"):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ics', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(result)
                temp_file_path = temp_file.name
            
            return FileResponse(
                path=temp_file_path,
                media_type='text/calendar',
                filename=f"{student_id}.ics",
                headers={"Content-Disposition": f"attachment; filename={student_id}.ics"}
            )
        else:
            logger.error(f"Main function did not return valid ICS content for student ID: {student_id}")
            raise HTTPException(status_code=500, detail="获取ICS文件失败，服务内部错误")
    
    except Exception as e:
        logger.error(f"Error processing request for student ID {student_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"发生了错误：{e}")

@app.get("/")
def read_root():
    """根路径，提供API使用说明"""
    return {
        "message": "ICS文件生成服务",
        "usage": "访问 https://blog.hishutdown.cn/?p=201 了解更多",
    }

# 错误处理中间件
@app.exception_handler(404)
async def custom_http_exception_handler(request, exc):
    return PlainTextResponse("页面未找到", status_code=404)

@app.exception_handler(500)
async def server_error_handler(request, exc):
    logger.error(f"Server error: {str(exc)}")
    return PlainTextResponse("服务器内部错误", status_code=500)

# HEAD请求支持
@app.api_route("/{full_path:path}", methods=["HEAD"])

async def handle_head_request(full_path: str):

    # 可以返回空响应体，只带状态码和必要头信息

    return Response(status_code=200)