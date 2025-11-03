# DAP Web GUI 使用指南

## 概述

DAP Web GUI 是基于 Flask + HTML/JavaScript 的现代化Web界面，提供直观的项目管理和数据分析功能。

## 快速启动

### 方法1：使用批处理脚本（Windows）

```bash
start_web_gui.bat
```

### 方法2：使用Python脚本（跨平台）

```bash
python start_web_gui.py
```

### 方法3：直接运行Flask应用

```bash
cd web_gui
python app.py
```

## 访问地址

启动成功后，在浏览器中访问：

```
http://localhost:5000
```

## 功能模块

### 1. 项目管理

- **创建项目**：填写项目基本信息（名称、客户、行业等）
- **查看项目列表**：显示所有项目，支持筛选和搜索
- **项目详情**：查看项目统计、成员、文件和活动日志
- **更新项目**：修改项目信息
- **删除项目**：软删除或硬删除项目

### 2. 智能查询

- **自然语言查询**：使用自然语言描述查询需求
- **支持的查询类型**：
  - 科目余额查询
  - 交易明细查询
  - 报表生成
  - 准则/税务/法规查询
  - 内控评估
  - IPO评估

### 3. 外部服务

- **服务状态监控**：实时查看5个外部服务的运行状态
- **服务调用**：通过Web界面调用外部知识库和智能体

### 4. 系统信息

- **查看系统版本和组件状态**
- **性能监控**（开发中）

## API端点说明

### 项目管理API

```
GET    /api/projects              # 获取项目列表
POST   /api/projects              # 创建新项目
GET    /api/projects/{id}         # 获取项目详情
PUT    /api/projects/{id}         # 更新项目
DELETE /api/projects/{id}         # 删除项目
GET    /api/projects/{id}/activities  # 获取项目活动日志
```

### 数据处理API

```
POST   /api/data/process          # 处理数据
```

### 查询API

```
POST   /api/query/nl              # 自然语言查询
```

### 外部服务API

```
GET    /api/external/services/status  # 获取服务状态
POST   /api/external/query             # 查询外部服务
```

### 系统API

```
GET    /api/system/info           # 获取系统信息
```

## 请求示例

### 创建项目

```bash
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "2024年度审计",
    "client_name": "示例公司",
    "industry": "制造业"
  }'
```

### 自然语言查询

```bash
curl -X POST http://localhost:5000/api/query/nl \
  -H "Content-Type: application/json" \
  -d '{
    "query": "查询所有资产类科目的余额",
    "project_id": "PRJ_xxxxx"
  }'
```

### 获取外部服务状态

```bash
curl http://localhost:5000/api/external/services/status
```

## 架构说明

```
web_gui/
├── app.py              # Flask应用主文件
├── __init__.py         # 模块初始化
└── static/             # 静态文件目录
    └── index.html      # 前端页面
```

## 技术栈

- **后端**：Flask 3.0+ (Python)
- **前端**：原生 HTML/CSS/JavaScript
- **API风格**：RESTful
- **数据格式**：JSON

## 配置选项

在 `app.py` 中可以配置：

```python
app.run(
    host='0.0.0.0',      # 监听地址
    port=5000,           # 端口号
    debug=True           # 调试模式
)
```

## 开发模式 vs 生产模式

### 开发模式（当前）

- 自动重载代码变更
- 详细的错误信息
- 不适合生产环境

### 生产模式（推荐使用Gunicorn）

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web_gui.app:app
```

## 安全建议

1. **生产环境**请关闭 `debug=True`
2. 使用HTTPS加密通信
3. 添加身份验证和授权机制
4. 限制CORS允许的域名
5. 使用环境变量管理敏感配置

## 故障排查

### 问题1：无法启动

**解决方法**：
```bash
pip install flask flask-cors
python start_web_gui.py
```

### 问题2：端口被占用

**解决方法**：修改 `app.py` 中的端口号
```python
app.run(port=5001)  # 使用其他端口
```

### 问题3：API返回404

**检查**：
- 确认路由路径正确
- 查看Flask日志输出
- 验证请求方法（GET/POST等）

## 后续开发计划

- [ ] 用户认证和授权系统
- [ ] 数据可视化图表
- [ ] 文件上传和管理
- [ ] 实时数据推送（WebSocket）
- [ ] 多语言支持
- [ ] 响应式移动端适配
- [ ] 主题切换（深色/浅色）

## 技术支持

如有问题，请查看：
- `logs/` 目录下的日志文件
- Flask控制台输出
- 浏览器开发者工具的Console

---

**版本**: 2.0.0  
**更新时间**: 2024-10-30
