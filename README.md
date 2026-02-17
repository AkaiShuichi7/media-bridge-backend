# 115离线下载文件整理系统

基于 FastAPI 的异步 115 网盘离线下载文件自动整理系统，支持智能番号解析和多种媒体库类型。

## ✨ 核心特性

- 🚀 **异步高性能**: 基于 FastAPI + SQLAlchemy Async
- 🔄 **自动监控**: 后台任务自动监控离线下载状态
- 🎯 **智能整理**: 支持 system 和 xx-片商 两种整理模式
- 📝 **番号解析**: 智能提取番号、处理 CD 编号、自动标准化
- 🔧 **配置驱动**: 支持在线配置管理和环境变量覆盖
- ✅ **测试驱动**: 132 个测试保证代码质量

## 📋 功能列表

### 离线下载管理
- 根据媒体库名称添加离线任务
- 查询任务列表和详情
- 删除任务

### 后台监控
- 60-80秒随机间隔轮询
- 任务完成自动触发文件整理
- 任务失败记录到数据库
- 优雅关闭机制

### 文件整理
#### system 类型
- 直接移动到目标目录
- 文件已存在时跳过

#### xx-片商 类型
- 移除关键词（可配置）
- 文件名转大写
- 标准化格式（`.` → `-`）
- 智能 CD 编号处理
- 生成规范目录结构：`{target}/{片商}/{番号}/{番号}.ext`

### 配置管理
- 在线查询和修改配置
- 环境变量覆盖（`P115_COOKIES`）
- Pydantic 验证

## 🚀 快速开始

### 1. 环境准备

```bash
# Python 3.14+
python --version

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，配置以下内容：

```yaml
p115:
  cookies: "你的115网盘cookies"
  rotation_training_interval_min: 60
  rotation_training_interval_max: 80

media:
  min_transfer_size: 200  # MB
  video_formats:
    - mp4
    - mkv
    - ts
    # ... 更多格式
  libraries:
    - name: "电影"
      download_path: "/115/下载/电影"
      target_path: "/媒体库/电影"
      type: "system"
    - name: "成人片库"
      download_path: "/115/下载/xx"
      target_path: "/媒体库/xx"
      type: "xx-ABC"  # ABC 为片商名称
  xx:
    remove_keywords:
      - "hhd800.com@"
      - "_X1080X"
      - "[98t.tv]"
```

### 4. 运行测试

```bash
pytest tests/ -v
```

### 5. 启动应用

```bash
uvicorn main:app --reload
```

访问 http://localhost:8000/docs 查看 API 文档

## 📚 API 文档

### 任务管理

#### 添加离线任务
```http
POST /api/tasks
Content-Type: application/json

{
  "magnet": "magnet:?xt=urn:btih:...",
  "library_name": "电影"
}
```

#### 查询任务列表
```http
GET /api/tasks
```

#### 查询任务详情
```http
GET /api/tasks/{task_id}
```

#### 删除任务
```http
DELETE /api/tasks/{task_id}
```

### 整理记录

#### 查询整理记录
```http
GET /api/organize/records?limit=10&offset=0
```

### 配置管理

#### 查询配置
```http
GET /api/config
```

#### 修改配置
```http
PUT /api/config
Content-Type: application/json

{
  "p115": {
    "cookies": "新的cookies"
  }
}
```

#### 查询媒体库列表
```http
GET /api/libraries
```

### 系统状态

#### 查询系统状态
```http
GET /api/status
```

## 🏗️ 项目结构

```
backend/
├── main.py                     # FastAPI 应用入口
├── config.yaml                 # 配置文件
├── requirements.txt            # 依赖列表
├── app/
│   ├── api/                    # API 路由
│   ├── core/                   # 核心模块
│   ├── models/                 # 数据库模型
│   ├── schemas/                # Pydantic 模型
│   ├── services/               # 业务服务
│   └── tasks/                  # 后台任务
└── tests/                      # 测试套件
```

## 🔧 技术栈

- **Web 框架**: FastAPI (异步)
- **数据库**: SQLite + SQLAlchemy Async
- **115 客户端**: p115client
- **配置管理**: Pydantic + PyYAML
- **日志**: loguru
- **测试**: pytest + pytest-asyncio

## 📝 配置说明

### p115 配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `cookies` | string | 115 网盘 cookies（必填） |
| `rotation_training_interval_min` | int | 监控轮询最小间隔（秒） |
| `rotation_training_interval_max` | int | 监控轮询最大间隔（秒） |

### media 配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `min_transfer_size` | int | 最小传输大小（MB） |
| `video_formats` | list | 支持的视频格式 |
| `libraries` | list | 媒体库列表 |
| `xx.remove_keywords` | list | xx 类型移除关键词 |

### 媒体库配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 媒体库名称 |
| `download_path` | string | 115 下载目录 |
| `target_path` | string | 整理目标目录 |
| `min_transfer_size` | int | 覆盖默认最小大小（可选） |
| `type` | string | 类型：`system` 或 `xx-片商名` |

## 🧪 测试

### 运行所有测试
```bash
pytest tests/ -v
```

### 运行特定测试
```bash
pytest tests/test_fanhao_parser.py -v
```

### 查看测试覆盖
```bash
pytest tests/ --cov=app --cov-report=html
```

## 🐛 故障排查

### 启动失败

1. **配置文件不存在**
   - 确认 `config.yaml` 存在
   - 从 `config.example.yaml` 复制

2. **Cookies 无效**
   - 检查 `config.yaml` 中的 cookies
   - 使用环境变量：`export P115_COOKIES="your_cookies"`

3. **数据库错误**
   - 删除 `data.db` 重新初始化

### 任务不自动整理

1. 检查监控任务状态
   ```bash
   curl http://localhost:8000/api/status
   ```

2. 查看日志
   ```bash
   tail -f logs/app.log
   ```

## 📄 许可证

MIT License

## 🙏 致谢

- [p115client](https://github.com/chenyanggao/p115client) - 115 网盘客户端
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM

## 📮 联系方式

如有问题或建议，请提交 Issue。
