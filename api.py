import logging
import os
import re
import tempfile
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response

# Configure logging - INFO for production, DEBUG if DEBUG env var is set
log_level = logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="XiQueEr2ICS",
    description="从喜鹊儿获取课表的工具",
    root_path="/xqe2ics/subscribe/v2"
)


def validate_student_id(student_id: str) -> bool:
    return student_id.isdigit()


def validate_password(password: str) -> bool:
    return bool(re.fullmatch(r'^[a-f0-9]{32}$', password))


@app.get("/{student_id}.ics")
async def get_ics_file(
    student_id: str,
    pwd: str = Query(..., description="用户密码（32位小写MD5）"),
    remindTime: int = Query(30, description="提醒时间（分钟），默认为30"),
    school_code: str = Query(None, description="学校代码"),
    school_year: str = Query(None, description="学年"),
    term: str = Query(None, description="学期"),
    all_semesters: bool = Query(True, description="是否获取所有可用学期的课表"),
    force: bool = Query(False, description="强制重新获取，忽略缓存，获取失败时返回错误而不是带错误事件的日历")
):
    pwd = pwd.lower()

    if not validate_student_id(student_id):
        logger.warning(f"Invalid student ID format: {student_id}")
        raise HTTPException(status_code=400, detail="学号格式错误")
    
    if not validate_password(pwd):
        logger.warning(f"Invalid password format: {student_id}")
        raise HTTPException(status_code=400, detail="密码不符合32位小写MD5格式")
    
    logger.info(f"Request: {student_id}, school={school_code}, all_sem={all_semesters}")
    
    try:
        import xqe
        result = xqe.Main(
            username=student_id,
            onceMd5Password=pwd,
            remindTime=str(remindTime),
            school_code=school_code,
            school_year=school_year,
            term=term,
            all_semesters=all_semesters,
            force=force
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
            logger.error(f"Invalid ICS content for {student_id}")
            raise HTTPException(status_code=500, detail="获取ICS文件失败")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing {student_id}: {e}")
        raise HTTPException(status_code=500, detail=f"{e}")


@app.get("/")
def read_root():
    return {
        "message": "ICS文件生成服务",
        "usage": "访问 https://blog.hishutdown.cn/?p=201 了解更多",
    }


@app.exception_handler(404)
async def custom_http_exception_handler(request, exc):
    return PlainTextResponse("页面未找到", status_code=404)


@app.exception_handler(500)
async def server_error_handler(request, exc):
    return PlainTextResponse("服务器内部错误", status_code=500)


@app.api_route("/{full_path:path}", methods=["HEAD"])
async def handle_head_request(full_path: str):
    return Response(status_code=200)
