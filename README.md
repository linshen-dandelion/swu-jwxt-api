# SWU 教务系统查询 - 最终版本

## 📋 功能概览

本项目实现了西南大学教务系统（jw.swu.edu.cn）的四大核心查询功能：

| 功能 | API 端点 | 说明 |
|------|----------|------|
| 课表查询 | `GET /api/schedule` | 查询指定学期的课程表 |
| 成绩查询 | `GET /api/grades` | 查询所有学期或指定学期的成绩 |
| 考试查询 | `GET /api/exams` | 查询指定学期的考试安排 |
| 空教室查询 | `POST /api/empty-rooms` | 查询指定时间的空闲教室 |

## 📁 文件说明

```
final_version/
├── main.py              # FastAPI 后端服务器（部署到 Railway）
├── swu_jwxt_query.py    # 本地查询脚本（可直接运行）
├── des.py               # DES 加密模块（需要从 swu-auto-checkin 复制）
├── requirements.txt     # Python 依赖
├── Dockerfile           # Docker 部署配置
├── railway.json         # Railway 部署配置
└── README.md            # 本文档
```

---

## 🚀 方案一：Railway 部署（推荐）

### 1. 准备工作

**复制 des.py 文件**：
```bash
copy E:\swu-check\swu-auto-checkin\des.py E:\swu-check\test-school-api\final_version\
```

### 2. 创建 GitHub 仓库

```bash
cd E:\swu-check\test-school-api\final_version
git init
git add .
git commit -m "init: SWU JWXT API"
git remote add origin https://github.com/你的用户名/swu-jwxt-api.git
git push -u origin main
```

### 3. 部署到 Railway

1. 打开 https://railway.app
2. 用 GitHub 账号登录
3. 点击 **"New Project"** → **"Deploy from GitHub repo"**
4. 选择你的仓库 `swu-jwxt-api`
5. Railway 会自动检测 Dockerfile 并开始部署
6. 部署完成后，点击 **"Settings"** → **"Networking"**
7. 点击 **"Generate Domain"** 获取公网 URL（如 `https://xxx.up.railway.app`）

### 4. 设置环境变量（可选）

在 Railway 的 **"Variables"** 页面：
- `ENCRYPTION_KEY`：加密密钥（不设置会自动生成）

### 5. 测试 API

```bash
# 健康检查
curl https://你的域名.railway.app/

# 绑定账号
curl -X POST https://你的域名.railway.app/api/bind-account \
  -H "Content-Type: application/json" \
  -d '{"student_id": "你的学号", "password": "你的密码"}'

# 查询课表（使用返回的 token）
curl "https://你的域名.railway.app/api/schedule?token=你的token&xnm=2025&xqm=12"
```

### 6. Flutter App 调用

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class ApiService {
  static const baseUrl = 'https://你的域名.railway.app';
  
  // 绑定账号
  static Future<String> bindAccount(String studentId, String password) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/bind-account'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'student_id': studentId,
        'password': password,
      }),
    );
    final data = jsonDecode(response.body);
    return data['token'];
  }
  
  // 查询课表
  static Future<List<dynamic>> getSchedule(String token, {String xnm = '2025', String xqm = '12'}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/schedule?token=$token&xnm=$xnm&xqm=$xqm'),
    );
    return jsonDecode(response.body);
  }
  
  // 查询成绩
  static Future<List<dynamic>> getGrades(String token) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/grades?token=$token'),
    );
    return jsonDecode(response.body);
  }
  
  // 查询考试
  static Future<List<dynamic>> getExams(String token, {String xnm = '2025', String xqm = '12'}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/exams?token=$token&xnm=$xnm&xqm=$xqm'),
    );
    return jsonDecode(response.body);
  }
  
  // 查询空教室
  static Future<List<dynamic>> getEmptyRooms(
    String token, {
    String xnm = '2025',
    String xqm = '12',
    int week = 13,
    int day = 1,
    List<int> sections = const [1, 2],
    int campusId = 1,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/empty-rooms?token=$token'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'xnm': xnm,
        'xqm': xqm,
        'week': week,
        'day': day,
        'sections': sections,
        'campus_id': campusId,
      }),
    );
    return jsonDecode(response.body);
  }
}
```

---

## 🖥️ 方案二：本地运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 复制 des.py

```bash
copy E:\swu-check\swu-auto-checkin\des.py .
```

### 3. 运行脚本

```bash
python swu_jwxt_query.py
```

### 4. 代码调用

```python
from swu_jwxt_query import login, query_schedule, query_grades, query_exams, query_empty_rooms

# 登录
session = login()

# 查询课表
schedule = query_schedule(session, "222024501210122", xnm="2025", xqm="12")

# 查询所有成绩
grades = query_grades(session, "222024501210122")

# 查询考试安排
exams = query_exams(session, "222024501210122", xnm="2025", xqm="12")

# 查询空教室（第13周，星期1，第1-2节，南校区）
rooms = query_empty_rooms(session, "222024501210122", week=13, day=1, sections=[1,2], campus_id=1)
```

---

## 📊 API 数据格式

### 课表数据
```json
{
    "kcmc": "课程名称",
    "xqj": "星期几（1-7）",
    "jc": "节次（如 1-3节）",
    "cdmc": "教室名称",
    "xm": "教师姓名",
    "xf": "学分",
    "zcd": "周次（如 2-4周,6-13周）"
}
```

### 成绩数据
```json
{
    "xnmmc": "学年名称",
    "xqmmc": "学期名称",
    "kcmc": "课程名称",
    "zpcj": "总评成绩",
    "xf": "学分"
}
```

### 考试数据
```json
{
    "kcmc": "课程名称",
    "ksrq": "考试日期",
    "kssj": "考试时间",
    "cdmc": "考试地点"
}
```

### 空教室数据
```json
{
    "cdmc": "教室名称",
    "xqmc": "校区名称",
    "zws": "座位数",
    "cdlbmc": "教室类别"
}
```

---

## 🔧 技术实现

### 登录流程
1. **IDM登录**：通过 `idm.swu.edu.cn` 进行身份认证
   - 使用 DES 加密用户名密码
   - 使用 ddddocr 识别验证码
2. **CAS认证**：通过 `uaaap.swu.edu.cn` 进行单点登录
3. **教务系统登录**：获取 `jw.swu.edu.cn` 的 JSESSIONID

### 教务系统 API 端点

| 功能 | 教务系统 API | 请求方式 |
|------|-------------|----------|
| 课表查询 | `/kbcx/xskbcx_cxXsgrkb.html` | POST |
| 成绩查询 | `/cjcx/cjcx_cxXsKcList.html` | POST |
| 考试查询 | `/kwgl/kscx_cxXsksxxIndex.html?doType=query` | POST |
| 空教室查询 | `/cdjy/cdjy_cxKxcdlb.html?doType=query` | POST |

### 空教室查询参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `xnm` | 学年 | 2025 |
| `xqm` | 学期 | 12（第2学期） |
| `week` | 周次 | 13 |
| `day` | 星期几 | 1（周一） |
| `sections` | 节次列表 | [1, 2]（第1-2节） |
| `campus_id` | 校区ID | 1（南区） |

**校区ID对应**：
- 1 = 南区
- 2 = 北区
- 3 = 荣昌校区

---

## ⚠️ 注意事项

1. **验证码识别**：使用 ddddocr 自动识别，准确率约 90%，失败时会重试
2. **会话保持**：登录后会话有效期约 30 分钟
3. **请求频率**：建议每次查询间隔 1-2 秒，避免被封禁
4. **HTTPS**：所有请求必须使用 HTTPS，HTTP 会返回 400 错误
5. **密码安全**：绑定的教务密码使用 AES-256 加密存储

---

## 🔍 调试信息

- 健康检查：`GET /` 应返回 `{"message": "SWU 教务系统 API", "status": "running"}`
- 登录成功标志：日志中显示 `[OK] 教务系统登录成功`
- 常见错误：
  - HTTP 401：未绑定教务账号或密码错误
  - HTTP 500：服务器内部错误（检查日志）

---

## 📝 更新日志

- **2026-05-29**：完成四大功能整合，所有 API 端点验证通过
  - 课表查询：46 条记录
  - 成绩查询：40 条记录（所有学期）
  - 考试查询：6 条记录
  - 空教室查询：110 间空教室
- **2026-05-29**：新增 FastAPI 后端服务器，支持 Railway 部署

---

**作者**：Sisyphus  
**日期**：2026-05-29  
**版本**：2.0
