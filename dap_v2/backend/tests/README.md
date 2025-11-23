# DAP v2.0 Backend Tests

## 测试结构

```
tests/
├── conftest.py              # 测试配置和Fixtures
├── test_evidence_api.py     # Evidence API测试
├── test_ai_services.py      # AI服务测试
└── test_evidence_models.py  # Evidence模型测试
```

## 运行测试

### 安装测试依赖
```bash
pip install pytest pytest-cov pytest-asyncio
```

### 运行所有测试
```bash
cd dap_v2/backend
pytest tests/ -v
```

### 运行特定测试
```bash
# API测试
pytest tests/test_evidence_api.py -v

# AI服务测试
pytest tests/test_ai_services.py -v

# 模型测试
pytest tests/test_evidence_models.py -v
```

### 生成覆盖率报告
```bash
pytest tests/ --cov=. --cov-report=html
# 报告在 htmlcov/index.html
```

## 测试覆盖

### API测试 (test_evidence_api.py)
- [x] 健康检查
- [x] 创建证据
- [x] 获取证据列表
- [x] 证据统计

### AI服务测试 (test_ai_services.py)
- [x] 关键词相似度计算
- [x] 金额匹配检测
- [x] 时间接近度计算
- [x] 查找相关证据
- [x] 构建证据图谱
- [x] OCR服务初始化
- [x] 关键词提取
- [x] 学习管理器初始化
- [x] 指标获取

### 模型测试 (test_evidence_models.py)
- [x] 证据类型枚举
- [x] 证据来源枚举
- [x] 证据状态枚举
- [x] 创建证据实例

## 测试数据

测试使用独立的SQLite数据库 `test_dap_v2.db`,与生产数据完全隔离。

## CI/CD集成

可以集成到GitHub Actions或GitLab CI:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```
