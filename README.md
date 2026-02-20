# 115离线下载文件整理系统 (MediaBridge)

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
- 60到80秒随机间隔轮询
- 任务完成自动触发文件整理
- 任务失败记录到数据库
- 具备优雅关闭机制

### 文件整理
#### system 类型
- 直接移动到目标目录
- 文件已存在时自动跳过

#### xx-片商 类型
- 移除配置的关键词
- 文件名强制转大写
- 标准化格式（`.` 转换为 `-`）
- 智能处理 CD 编号
- 生成规范目录结构：`{target}/{片商}/{番号}/{番号}.ext`

## 🚀 快速开始

### 1. 环境准备

```bash
# Python 3.14+
python --version

# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，按需配置：

```yaml
p115:
  cookies: "你的115网盘cookies"
  rotation_training_interval_min: 60
  rotation_training_interval_max: 80

media:
  min_transfer_size: 200  # MB
  video_formats: [mp4, mkv, ts]
  libraries:
    - name: "电影"
      download_path: "/115/下载/电影"
      target_path: "/媒体库/电影"
      type: "system"
    - name: "成人片库"
      download_path: "/115/下载/xx"
      target_path: "/媒体库/xx"
      type: "xx-ABC"
  xx:
    remove_keywords: ["hhd800.com@", "_X1080X", "[98t.tv]"]
```

### 4. 启动应用

```bash
uvicorn main:app --reload
```

访问 http://localhost:8000/docs 查看 Swagger UI 文档。

---

## 📚 API 文档

### 统一响应格式

所有接口均遵循以下统一响应结构：

```typescript
interface ApiResponse<T> {
  code: number;    // 0 表示成功，非 0 表示错误（通常对应 HTTP 状态码）
  message: string; // 响应描述信息
  data: T | null;  // 实际业务数据
}
```

### 错误响应说明

系统使用标准 HTTP 状态码表示错误：

| HTTP 状态码 | code 值 | 场景描述 |
|------------|---------|----------|
| 200 | 0 | 操作成功 |
| 404 | 404 | 请求的资源不存在 |
| 422 | 422 | 请求参数验证失败 |
| 500 | 500 | 服务器内部逻辑错误 |

**422 参数验证错误示例：**
```json
{
  "code": 422,
  "message": "请求参数验证失败",
  "data": {
    "errors": [
      {
        "loc": ["body", "magnet"],
        "msg": "Field required",
        "type": "missing"
      }
    ]
  }
}
```

---

### 接口详情

#### 1. 服务根路径
- **方法**: `GET`
- **路径**: `/`
- **说明**: 检查后端服务是否可以访问。
- **成功响应**:
```json
{
  "code": 0,
  "message": "服务运行中",
  "data": {
    "message": "115 离线任务管理器 API",
    "version": "1.0.0"
  }
}
```

#### 2. 健康检查
- **方法**: `GET`
- **路径**: `/health`
- **说明**: 检查系统健康状态。
- **成功响应**:
```json
{
  "code": 0,
  "message": "健康检查通过",
  "data": {
    "status": "healthy"
  }
}
```

#### 3. 添加离线下载任务
- **方法**: `POST`
- **路径**: `/api/tasks`
- **说明**: 向 115 网盘添加磁力链接下载任务。
- **请求参数 (Body)**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `magnet` | string | 是 | 磁力链接 |
| `library_name` | string | 是 | 媒体库名称（对应配置中的库名） |
| `name` | string | 否 | 自定义任务名称 |

- **请求示例**:
```json
{
  "magnet": "magnet:?xt=urn:btih:abc123...",
  "library_name": "电影"
}
```

- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "task_id": "12345",
    "message": "任务添加成功"
  }
}
```

- **错误响应**:
  - `404` - 指定的媒体库不存在
  - `500` - 下载目录ID获取失败 / 115 API 调用失败

#### 4. 获取离线任务列表
- **方法**: `GET`
- **路径**: `/api/tasks`
- **说明**: 获取当前所有监控中的任务。
- **`status` 枚举值**: `0`=进行中, `1`=失败, `2`=完成
- **错误响应**: `500` - 获取任务列表失败
- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "total": 2,
    "tasks": [
      {
        "task_id": "12345",
        "name": "example.mkv",
        "status": 0,
        "progress": 45,
        "add_time": "2026-02-18T00:00:00"
      },
      {
        "task_id": "12346",
        "name": "movie.mp4",
        "status": 2,
        "progress": 100,
        "add_time": "2026-02-17T12:00:00"
      }
    ]
  }
}
```

#### 5. 获取任务详情
- **方法**: `GET`
- **路径**: `/api/tasks/{task_id}`
- **说明**: 根据 ID 查询任务的具体状态和路径。
- **路径参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `task_id` | string | 是 | 任务唯一标识 |

- **错误响应**: `404` - 任务不存在
- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "task_id": "12345",
    "name": "example.mkv",
    "status": 2,
    "progress": 100,
    "add_time": "2026-02-18T00:00:00",
    "file_id": "67890",
    "path": "/115/下载/电影/example.mkv"
  }
}
```

#### 6. 删除任务
- **方法**: `DELETE`
- **路径**: `/api/tasks/{task_id}`
- **说明**: 从数据库和监控列表中删除任务。
- **路径参数**: `task_id` (string, 必填)
- **错误响应**: `500` - 删除失败
- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "message": "任务删除成功"
  }
}
```

#### 7. 获取文件整理记录
- **方法**: `GET`
- **路径**: `/api/organize/records`
- **说明**: 分页查询已完成的文件整理历史。
- **查询参数**:
| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `page` | int | 1 | 页码，不小于 1 |
| `page_size` | int | 20 | 每页数量，1 到 100 |
| `status` | string | - | 状态过滤（如 completed） |

- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "total": 50,
    "records": [
      {
        "id": 1,
        "file_name": "ABC-123.mp4",
        "source_path": "/115/下载/xx/abc-123.mp4",
        "target_path": "/媒体库/xx/ABC/ABC-123/ABC-123.mp4",
        "status": "completed",
        "created_at": "2026-02-18T00:00:00"
      }
    ]
  }
}
```

#### 8. 获取系统配置
- **方法**: `GET`
- **路径**: `/api/config`
- **说明**: 读取当前运行的配置。
- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "p115": {
      "rotation_training_interval_min": 60,
      "rotation_training_interval_max": 80
    },
    "media": {
      "min_transfer_size": 200,
      "video_formats": ["mp4", "mkv", "ts"],
      "libraries": [
        {
          "name": "电影",
          "download_path": "/115/下载/电影",
          "target_path": "/媒体库/电影",
          "type": "system",
          "min_transfer_size": 0
        }
      ],
      "xx": {
        "remove_keywords": ["hhd800.com@"]
      }
    }
  }
}
```

#### 9. 修改系统配置
- **方法**: `PUT`
- **路径**: `/api/config`
- **说明**: 部分更新系统参数，仅传需要修改的字段即可。
- **请求参数 (Body)**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `p115` | object | 否 | 115 相关配置 |
| `p115.rotation_training_interval_min` | int | 否 | 轮询最小间隔（秒） |
| `p115.rotation_training_interval_max` | int | 否 | 轮询最大间隔（秒） |
| `media` | object | 否 | 媒体相关配置 |
| `media.min_transfer_size` | int | 否 | 最小传输大小（MB） |

- **请求示例**:
```json
{
  "p115": {
    "rotation_training_interval_min": 30,
    "rotation_training_interval_max": 60
  }
}
```
- **成功响应**:
```json
{
  "code": 0,
  "message": "配置更新成功",
  "data": {
    "message": "配置更新成功"
  }
}
```

#### 10. 获取媒体库列表
- **方法**: `GET`
- **路径**: `/api/libraries`
- **说明**: 获取所有已定义的媒体库。
- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "libraries": [
      {
        "name": "电影",
        "download_path": "/115/下载/电影",
        "target_path": "/媒体库/电影",
        "type": "system",
        "min_transfer_size": 200
      }
    ]
  }
}
```

#### 11. 获取系统状态
- **方法**: `GET`
- **路径**: `/api/status`
- **说明**: 获取后台监控状态和任务统计。
- **成功响应**:
```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "monitor_running": true,
    "active_tasks": 3,
    "last_check_time": "2026-02-18T00:49:14"
  }
}
```

---

## ⌨️ TypeScript 类型定义

前端可直接使用以下接口定义：

```typescript
// 统一基础响应
interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T | null;
}

// 任务管理
interface AddTaskRequest { 
  magnet: string; 
  library_name: string; 
  name?: string; 
}
interface AddTaskResponse { 
  task_id: string; 
  message: string; 
}
interface TaskItem { 
  task_id: string; 
  name: string; 
  status: 0 | 1 | 2; // 0=进行中, 1=失败, 2=完成
  progress: number; 
  add_time: string; 
}
interface TaskListResponse { 
  total: number; 
  tasks: TaskItem[]; 
}
interface TaskDetailResponse extends TaskItem { 
  file_id?: string; 
  path?: string; 
}
interface DeleteTaskResponse { 
  message: string; 
}

// 整理记录
interface OrganizeRecordItem { 
  id: number; 
  file_name: string; 
  source_path: string; 
  target_path: string; 
  status: string; 
  created_at: string; 
}
interface OrganizeRecordsResponse { 
  total: number; 
  records: OrganizeRecordItem[]; 
}

// 系统配置
interface P115Config { 
  rotation_training_interval_min: number; 
  rotation_training_interval_max: number; 
}
interface LibraryItem { 
  name: string; 
  download_path: string; 
  target_path: string; 
  type: string; 
  min_transfer_size: number; 
}
interface XXConfig { 
  remove_keywords: string[]; 
}
interface MediaConfig { 
  min_transfer_size: number; 
  video_formats: string[]; 
  libraries: LibraryItem[]; 
  xx: XXConfig; 
}
interface ConfigResponse { 
  p115: P115Config; 
  media: MediaConfig; 
}
interface UpdateConfigRequest { 
  p115?: Partial<P115Config>; 
  media?: { 
    min_transfer_size?: number 
  }; 
}
interface UpdateConfigResponse { 
  message: string; 
}
interface LibrariesResponse { 
  libraries: LibraryItem[]; 
}

// 系统运行状态
interface StatusResponse { 
  monitor_running: boolean; 
  active_tasks: number; 
  last_check_time?: string; 
}
```

---

## 🏗️ 项目结构

```
backend/
├── main.py                     # FastAPI 应用入口
├── config.yaml                 # 配置文件
├── requirements.txt            # 依赖列表
├── app/
│   ├── api/                    # 路由定义
│   ├── core/                   # 核心逻辑 (115 客户端、配置加载)
│   ├── models/                 # 数据库模型
│   ├── schemas/                # Pydantic 校验模型
│   ├── services/               # 业务逻辑服务
│   └── tasks/                  # 后台监控任务
└── tests/                      # 测试用例
```

## 🔧 技术栈

- **Web 框架**: FastAPI (异步)
- **数据库**: SQLite + SQLAlchemy Async
- **115 客户端**: p115client
- **配置校验**: Pydantic
- **日志**: loguru
- **测试**: pytest

## 🧪 测试

使用以下命令运行单元测试和集成测试：

```bash
# 运行所有测试
pytest tests/ -v

# 查看覆盖率报告
pytest tests/ --cov=app --cov-report=html
```

## 🐛 故障排查

1. **无法连接 115**: 请确保 `config.yaml` 中的 cookies 有效。
2. **监控未运行**: 检查 `/api/status` 确认 `monitor_running` 是否为 true。
3. **日志位置**: 应用日志记录在 `logs/app.log`。

## 📄 许可证

MIT License
