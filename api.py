from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
import re
import tempfile
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="XiQueEr To ICS", description="从喜鹊儿获取课表的工具", root_path="/xqe2ics/subscribe/v1")# root_path用于供生产环境中反向代理使用

def validate_student_id(student_id: str) -> bool:
    """验证学号格式：12位数字"""
    return bool(re.match(r'^\d{12}$', student_id))

def validate_password(password: str) -> bool:
    """验证密码格式：通常的密码要求"""
    # 密码至少8-30位
    return bool(re.fullmatch(r'^[a-f0-9]{32}$', password))
    

@app.get("/{student_id}.ics")
async def get_ics_file(
    student_id: str,
    pwd: str = Query(..., description="用户密码")
):
    """
    获取ICS日历文件
    - student_id: 12位学号
    - pwd: 用户密码
    """
    # 将密码转为小写
    pwd = pwd.lower()

    # 验证学号格式
    if not validate_student_id(student_id):
        logger.warning(f"Invalid student ID format: {student_id}")
        raise HTTPException(status_code=400, detail="学号格式错误，应为12位数字")
    
    # 验证密码格式
    if not validate_password(pwd):
        logger.warning(f"Invalid password format for student ID: {student_id}")
        raise HTTPException(status_code=400, detail="密码不符合MD5格式")
    
    logger.info(f"Valid request for student ID: {student_id}")
    
    try:
        # 导入xqe模块并调用Main函数
        import xqe
        
        # 调用xqe.py中的Main函数
        result = xqe.Main(username=student_id, onceMd5Password=pwd, base_url="http://202.103.141.242")
        
        # 检查返回结果是否为有效的ICS文件内容
        if isinstance(result, str) and result.startswith("BEGIN:VCALENDAR"):
            # 创建临时ICS文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ics', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(result)
                temp_file_path = temp_file.name
            
            # 返回ICS文件
            return FileResponse(
                path=temp_file_path,
                media_type='text/calendar',
                filename=f"{student_id}.ics",
                headers={"Content-Disposition": f"attachment; filename={student_id}.ics"}
            )
        else:
            # 如果返回的不是ICS内容，尝试返回结果作为文本
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
        "usage": "访问https://blog.hishutdown.cn/?p=201了解更多",
    }

# 错误处理中间件
@app.exception_handler(404)
async def custom_http_exception_handler(request, exc):
    return PlainTextResponse("页面未找到", status_code=404)

@app.exception_handler(500)
async def server_error_handler(request, exc):
    logger.error(f"Server error: {str(exc)}")
    return PlainTextResponse("服务器内部错误", status_code=500)
