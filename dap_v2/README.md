# DAP v2.0 - 审计底稿与合并报表系统

## 项目结构

```
dap_v2/
├── backend/              # 后端服务 (FastAPI)
│   ├── api/             # API路由
│   ├── models/          # 数据模型 (SQLAlchemy)
│   ├── services/        # 业务逻辑
│   └── utils/           # 工具函数
├── frontend/            # 前端应用 (Vue 3)
│   ├── src/            # 源代码
│   ├── public/         # 静态资源
│   └── dist/           # 构建输出
├── database/            # 数据库管理
│   ├── migrations/     # 数据库迁移脚本
│   ├── seeds/          # 测试数据
│   └── schemas/        # 数据库架构设计
├── tests/              # 测试套件
│   ├── unit/          # 单元测试
│   ├── integration/   # 集成测试
│   └── e2e/           # 端到端测试
├── config/             # 配置文件
└── docs/              # 项目文档
```

## 开发原则

**小步快走**: 开发一个功能 → 验证没问题 → 继续下一步

## 技术栈

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy / PostgreSQL
- **前端**: Vue 3 / TypeScript / Element Plus
- **数据库**: PostgreSQL 14+ / Redis 7.0

## 当前进度

✅ 项目目录结构创建
⏳ 数据库架构设计
⏳ 后续功能开发...
