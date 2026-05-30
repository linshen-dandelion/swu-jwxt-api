"""
SWU 教务系统 API 后端服务器
FastAPI 实现，部署到 
"""
import os
import re
import sys
import base64
import urllib.parse
import requests
import urllib3
import json
import logging
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from cryptography.fernet import Fernet

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================

# 加密密钥（从环境变量读取，或生成一个默认值用于开发）
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# IDM 登录的 GOTO_B64
GOTO_B64 = (
    "aHR0cDovL2lkbS5zd3UuZWR1LmNuL2FtL29hdXRoMi9hdXRob3JpemU/"
    "c2VydmljZT1pbml0U2VydmljZSZyZXNwb25zZV90eXBlPWNvZGUmY2xp"
    "ZW50X2lkPTdjMXpva29samw5YmJpaG82eXVvJnNjb3BlPXVpZCtjbit1"
    "c2VySWRDb2RlJnJlZGlyZWN0X3VyaT1odHRwcyUzQSUyRiUyRnVhYWFw"
    "LnN3dS5lZHUuY24lMkZjYXMlMkZsb2dpbiUzRnNlcnZpY2UlM0RodHRw"
    "cyUyNTNBJTI1MkYlMjUyRnVhYWFwLnN3dS5lZHUuY24lMjUyRmNhcyUy"
    "NTJGb2F1dGhyLjAlMjUyRmNhbGxiYWNrQXV0aG9yaXplJTI2b3JpZ2lu"
    "YWxSZXF1ZXN0VXJsJTNEaHR0cHMlMjUzQSUyNTJGJTI1MkZ1YWFhcC5z"
    "d3UuZWR1LmNuJTI1MkZjYXMlMjUyRm9hdXRoMi4wJTI1MkZhdXRob3Jp"
    "emUlMjUzRmNsaWVudF9pZCUyNTNEeXpzbWhzJTI1MjZyZWRpcmVjdF91"
    "cmklMjUzRGh0dHBzJTI1MjUzQSUyNTI1MkYlMjUyNTJGb2Yuc3d1LmVk"
    "dS5jbiUyNTI1M0E0NDMlMjUyNTJGY2FzJTI1MjUyRm9hdXRoJTI1MjUy"
    "RmNhbGxiYWNrJTI1MjUyRlNXVV9DQVMyX0ZBREVSQUwlMjUyNnN0YXRl"
    "JTI1M0Q1ZTU2M2JiY2E1MjM0ZTA0YmRjM2JkODEzMTc0OWVjNSUyNTI2"
    "c2NvcGUlMjUzRHNpbXBsZSUyNTI2ZmVkZXJhbEVuYWJsZSUzRHRydWUm"
    "ZGVjaXNpb249QWxsb3c="
)


# ============================================================
# 数据模型
# ============================================================

class BindAccountRequest(BaseModel):
    student_id: str
    password: str


class QueryRequest(BaseModel):
    xnm: str = "2025"
    xqm: str = "12"


class EmptyRoomRequest(BaseModel):
    xnm: str = "2025"
    xqm: str = "12"
    week: int = 13
    day: int = 1
    sections: List[int] = [1, 2]
    campus_id: int = 1
    building: str = ""  # 教学楼筛选（如 "23教", "01教"）


class ScheduleItem(BaseModel):
    kcmc: str  # 课程名称
    xqj: str   # 星期几
    jc: str    # 节次
    cdmc: str  # 教室
    xm: str    # 教师
    xf: str    # 学分
    zcd: str   # 周次
    zxs: str   # 总学时


class GradeItem(BaseModel):
    xnmmc: str  # 学年
    xqmmc: str  # 学期
    kcmc: str   # 课程名称
    zpcj: str   # 总评成绩
    xf: str     # 学分


class ExamItem(BaseModel):
    kcmc: str   # 课程名称
    ksrq: str   # 考试日期
    kssj: str   # 考试时间
    cdmc: str   # 考试地点


class EmptyRoomItem(BaseModel):
    cdmc: str   # 教室名称
    xqmc: str   # 校区
    zws: str    # 座位数
    cdlbmc: str # 教室类别


# ============================================================
# 简单的内存数据库（生产环境应使用真实数据库）
# ============================================================

# 用户绑定信息存储
# 格式: {user_id: {"student_id": "...", "encrypted_password": "..."}}
user_accounts = {}

# 用户 token 存储（简化版，生产环境应使用 JWT）
# 格式: {token: user_id}
user_tokens = {}


# ============================================================
# 登录模块（从 swu_jwxt_query.py 移植）
# ============================================================

def login_to_swu(student_id: str, password: str):
    """登录教务系统，返回session"""
    try:
        # 导入 DES 加密模块
        sys.path.insert(0, '/app')  # Railway 容器中的路径
        from des import strEnc
        
        session = requests.Session()
        session.verify = False
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        # 尝试导入 ddddocr（验证码识别）
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
        except ImportError:
            logger.error("ddddocr not available")
            raise HTTPException(status_code=500, detail="验证码识别模块不可用")
        
        # 获取验证码
        r = session.get(
            "http://idm.swu.edu.cn/am/UI/Login?goto=" + GOTO_B64 + "&service=initService",
            timeout=10
        )
        rk = re.search(r'id="random"[^>]*value="([^"]+)"', r.text).group(1)
        
        # 识别验证码
        captcha_img = session.get(
            "https://idm.swu.edu.cn/am/validate.code",
            timeout=10
        ).content
        cc = ocr.classification(captcha_img)
        logger.info(f"验证码: {cc}")
        
        # 提交验证码
        session.post(
            "https://idm.swu.edu.cn/am/validatecode/verify.do",
            data={"validateCode": cc},
            timeout=10
        )
        
        # IDM 登录
        eu = strEnc(student_id, rk, "", "")
        ep = strEnc(password, rk, "", "")
        
        r = session.post(
            "https://idm.swu.edu.cn/am/UI/Login",
            data={
                "IDToken1": eu,
                "IDToken2": ep,
                "IDToken3": "",
                "goto": GOTO_B64,
                "gotoOnFail": "",
                "SunQueryParamsString": "c2VydmljZT1pbml0U2VydmljZQ==",
                "encoded": "false",
                "validateCode": cc,
                "gx_charset": "UTF-8"
            },
            allow_redirects=False,
            timeout=10
        )
        
        if r.status_code != 302 or not session.cookies.get("iPlanetDirectoryPro"):
            raise HTTPException(status_code=401, detail="IDM 登录失败，请检查学号和密码")
        
        logger.info("[OK] IDM 登录成功")
        
        # CAS 认证
        gd = base64.b64decode(GOTO_B64).decode()
        r = session.get(gd, allow_redirects=False, timeout=10)
        if r.status_code == 302:
            r = session.get(r.headers["Location"], allow_redirects=False, timeout=10)
        if r.status_code == 302 and "code=" in r.headers.get("Location", ""):
            r = session.get(r.headers["Location"], allow_redirects=False, timeout=10)
        
        # 获取 JWXT session
        cu = "https://uaaap.swu.edu.cn/cas/login?service=" + urllib.parse.quote(
            "https://jw.swu.edu.cn/sso/zllogin"
        )
        r = session.get(cu, allow_redirects=False, timeout=10)
        r = session.get(r.headers["Location"], allow_redirects=False, timeout=10)
        if r.status_code == 302:
            r = session.get(r.headers["Location"], allow_redirects=False, timeout=10)
        if r.status_code in [301, 302, 303, 307]:
            session.get(
                r.headers["Location"].replace("http://", "https://", 1),
                allow_redirects=True,
                timeout=15
            )
        
        # 验证是否登录成功
        has = any(c.name == "JSESSIONID" and c.path == "/jwglxt" for c in session.cookies)
        if not has:
            raise HTTPException(status_code=401, detail="教务系统登录失败")
        
        logger.info("[OK] 教务系统登录成功")
        return session
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


# ============================================================
# 查询模块
# ============================================================

def query_schedule(session, student_id: str, xnm: str = "2025", xqm: str = "12"):
    """查询课表"""
    base = "https://jw.swu.edu.cn/jwglxt"
    
    # 先 GET 页面初始化
    session.get(
        f"{base}/kbcx/xskbcx_cxXskbcxIndex.html?gnmkdm=N253508&layout=default&su={student_id}",
        timeout=10
    )
    
    # 调用 API
    r = session.post(
        f"{base}/kbcx/xskbcx_cxXsgrkb.html",
        data={"xnm": xnm, "xqm": xqm, "kzlx": "ck", "xsdm": ""},
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": f"{base}/kbcx/xskbcx_cxXskbcxIndex.html?gnmkdm=N253508&layout=default&su={student_id}",
        },
        timeout=10
    )
    
    if r.status_code == 200:
        try:
            data = r.json()
            items = data.get("kbList", [])
            return [
                {
                    "kcmc": item.get("kcmc", ""),
                    "xqj": item.get("xqj", ""),
                    "jc": item.get("jc", ""),
                    "cdmc": item.get("cdmc", ""),
                    "xm": item.get("xm", ""),
                    "xf": item.get("xf", ""),
                    "zcd": item.get("zcd", ""),
                    "zxs": item.get("zxs", "")
                }
                for item in items
            ]
        except:
            return []
    return []


def query_grades(session, student_id: str, xnm: str = "", xqm: str = ""):
    """查询成绩（自动分页获取所有数据）"""
    base = "https://jw.swu.edu.cn/jwglxt"
    
    session.get(
        f"{base}/cjcx/cjcx_cxDgXsxmcj.html?gnmkdm=N305007&layout=default&su={student_id}",
        timeout=10
    )
    
    all_items = []
    page = 1
    
    while True:
        r = session.post(
            f"{base}/cjcx/cjcx_cxXsKcList.html",
            data={
                "xnm": xnm,
                "xqm": xqm,
                "currentPage": str(page),
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": f"{base}/cjcx/cjcx_cxDgXsxmcj.html?gnmkdm=N305007&layout=default&su={student_id}",
            },
            timeout=10
        )
        
        if r.status_code == 200:
            try:
                data = r.json()
                items = data.get("items", [])
                total = int(data.get("totalResult", 0))
                
                for item in items:
                    all_items.append({
                        "xnmmc": item.get("xnmmc", ""),
                        "xqmmc": item.get("xqmmc", ""),
                        "kcmc": item.get("kcmc", ""),
                        "zpcj": item.get("zpcj", ""),
                        "xf": item.get("xf", "")
                    })
                
                # 检查是否还有更多页
                if len(all_items) >= total or len(items) == 0:
                    break
                
                page += 1
            except:
                break
        else:
            break
    
    return all_items


def query_exams(session, student_id: str, xnm: str = "2025", xqm: str = "12"):
    """查询考试（自动分页获取所有数据）"""
    base = "https://jw.swu.edu.cn/jwglxt"
    
    session.get(
        f"{base}/kwgl/kscx_cxXsksxxIndex.html?gnmkdm=N358105&layout=default&su={student_id}",
        timeout=10
    )
    
    all_items = []
    page = 1
    
    while True:
        r = session.post(
            f"{base}/kwgl/kscx_cxXsksxxIndex.html?doType=query",
            data={
                "xnm": xnm,
                "xqm": xqm,
                "currentPage": str(page),
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": f"{base}/kwgl/kscx_cxXsksxxIndex.html?gnmkdm=N358105&layout=default&su={student_id}",
            },
            timeout=10
        )
        
        if r.status_code == 200:
            try:
                data = r.json()
                items = data.get("items", [])
                total = int(data.get("totalResult", 0))
                
                for item in items:
                    all_items.append({
                        "kcmc": item.get("kcmc", ""),
                        "ksrq": item.get("ksrq", ""),
                        "kssj": item.get("kssj", ""),
                        "cdmc": item.get("cdmc", "")
                    })
                
                # 检查是否还有更多页
                if len(all_items) >= total or len(items) == 0:
                    break
                
                page += 1
            except:
                break
        else:
            break
    
    return all_items


def query_empty_rooms(
    session, 
    student_id: str, 
    xnm: str = "2025", 
    xqm: str = "12",
    week: int = 13,
    day: int = 1,
    sections: List[int] = [1, 2],
    campus_id: int = 1,
    building: str = ""  # 教学楼筛选（如 "23教", "01教"）
):
    """查询空教室（自动分页获取所有数据）"""
    base = "https://jw.swu.edu.cn/jwglxt"
    
    session.get(
        f"{base}/cdjy/cdjy_cxKxcdlb.html?gnmkdm=N2155&layout=default&su={student_id}",
        timeout=10
    )
    
    # 计算位图
    zcd = 2 ** (week - 1)
    jcd = sum(2 ** (s - 1) for s in sections)
    
    all_items = []
    page = 1
    
    while True:
        r = session.post(
            f"{base}/cdjy/cdjy_cxKxcdlb.html?doType=query",
            data={
                "xnm": xnm,
                "xqm": xqm,
                "xqh_id": str(campus_id),
                "zcd": str(zcd),
                "xqj": str(day),
                "jcd": str(jcd),
                "cdmc": "",
                "lh": building,  # 教学楼筛选
                "cdlb_id": "",
                "cdejlb_id": "",
                "qszws": "",
                "jszws": "",
                "jyfs": "0",
                "currentPage": str(page),
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": f"{base}/cdjy/cdjy_cxKxcdlb.html?gnmkdm=N2155&layout=default&su={student_id}",
            },
            timeout=10
        )
        
        if r.status_code == 200:
            try:
                data = r.json()
                items = data.get("items", [])
                total = int(data.get("totalResult", 0))
                
                for item in items:
                    all_items.append({
                        "cdmc": item.get("cdmc", ""),
                        "xqmc": item.get("xqmc", ""),
                        "zws": item.get("zws", ""),
                        "cdlbmc": item.get("cdlbmc", "")
                    })
                
                # 检查是否还有更多页
                if len(all_items) >= total or len(items) == 0:
                    break
                
                page += 1
            except:
                break
        else:
            break
    
    return all_items


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="SWU 教务系统 API",
    description="西南大学教务系统查询接口",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """健康检查"""
    return {
        "message": "SWU 教务系统 API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/bind-account")
def bind_account(request: BindAccountRequest):
    """
    绑定教务系统账号
    用于测试：直接返回绑定成功，实际应验证账号密码
    """
    try:
        # 生成一个简单的 token（生产环境应使用 JWT）
        token = base64.b64encode(f"{request.student_id}:{datetime.now().timestamp()}".encode()).decode()
        
        # 加密密码
        encrypted_password = cipher.encrypt(request.password.encode()).decode()
        
        # 存储绑定信息
        user_accounts[token] = {
            "student_id": request.student_id,
            "encrypted_password": encrypted_password,
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "message": "绑定成功",
            "token": token,
            "student_id": request.student_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedule")
def get_schedule(
    token: str,
    xnm: str = "2025",
    xqm: str = "12"
):
    """查询课表"""
    # 验证 token
    if token not in user_accounts:
        raise HTTPException(status_code=401, detail="请先绑定教务账号")
    
    account = user_accounts[token]
    student_id = account["student_id"]
    
    # 解密密码
    password = cipher.decrypt(account["encrypted_password"].encode()).decode()
    
    # 登录并查询
    session = login_to_swu(student_id, password)
    return query_schedule(session, student_id, xnm, xqm)


@app.get("/api/grades")
def get_grades(
    token: str,
    xnm: str = "",
    xqm: str = ""
):
    """查询成绩"""
    if token not in user_accounts:
        raise HTTPException(status_code=401, detail="请先绑定教务账号")
    
    account = user_accounts[token]
    student_id = account["student_id"]
    
    password = cipher.decrypt(account["encrypted_password"].encode()).decode()
    session = login_to_swu(student_id, password)
    return query_grades(session, student_id, xnm, xqm)


@app.get("/api/exams")
def get_exams(
    token: str,
    xnm: str = "2025",
    xqm: str = "12"
):
    """查询考试"""
    if token not in user_accounts:
        raise HTTPException(status_code=401, detail="请先绑定教务账号")
    
    account = user_accounts[token]
    student_id = account["student_id"]
    
    password = cipher.decrypt(account["encrypted_password"].encode()).decode()
    session = login_to_swu(student_id, password)
    return query_exams(session, student_id, xnm, xqm)


@app.post("/api/empty-rooms")
def get_empty_rooms(
    request: EmptyRoomRequest,
    token: str
):
    """查询空教室"""
    if token not in user_accounts:
        raise HTTPException(status_code=401, detail="请先绑定教务账号")
    
    account = user_accounts[token]
    student_id = account["student_id"]
    
    password = cipher.decrypt(account["encrypted_password"].encode()).decode()
    session = login_to_swu(student_id, password)
    
    return query_empty_rooms(
        session,
        student_id,
        request.xnm,
        request.xqm,
        request.week,
        request.day,
        request.sections,
        request.campus_id,
        request.building
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
