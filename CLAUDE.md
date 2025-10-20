# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DAP (Data Processing & Auditing Intelligence Agent) is a five-layer intelligent audit data processing system designed specifically for professional auditing. It automatically receives, cleans, stores, classifies, and performs AI-enhanced analysis of financial data from heterogeneous sources (金蝶、用友、SAP、ERP systems), providing high-quality, structured, ready-to-use data foundation and intelligent analysis capabilities for audit professionals and the upper-level "AI Audit Brain".

## Core Philosophy

**"First Principles + KISS + SOLID + AI-Enhanced"**
- **First Principles**: Solve audit data processing from fundamental requirements
- **KISS Principle**: Keep interface simple, one-click drag-and-drop operation
- **SOLID Principles**: Modular, extensible, maintainable code architecture
- **AI-Enhanced**: Self-learning system that improves with usage and data volume

## Architecture

The system follows an optimized five-layer architecture integrating audit intelligence:

```
┌─────────────────────────────────────────────────────────────┐
│               [交互层] - 极简一键操作界面                      │
│        🚀 拖拽导入 + 实时进度 + AI对话 + 结果预览            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            [第一层] 智能数据接入与标准化层                     │
│  📥 多源连接器 → 🧠 格式识别 → 🔧 智能清洗 → 📐 标准映射    │
│  支持：金蝶、用友、SAP、ERP、AIS等所有主流财务系统          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            [第二层] 分层存储与数据管理层                       │
│  💾 数据湖(原始) → 🏛️ 数据仓库(标准) → ⚡ 内存缓存(热点)   │
│  冷热分离 + 智能压缩 + 版本控制 + 血缘追踪                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            [第三层] AI增强的审计规则引擎层                     │
│  📋 规则引擎 → 🚨 异常检测 → 🧠 AI学习 → 📊 智能分析       │
│  自适应科目映射 + 异常模式学习 + 审计知识沉淀               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            [第四层] 多模式分析与输出服务层                     │
│  📈 标准报表 → 🔍 交互分析 → 🤖 AI智能体 → 📤 多格式导出   │
│  审计模板 + 自定义查询 + 自然语言交互 + 智能推荐            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│            [第五层] 外部集成与API服务层                       │
│  🌐 RESTful API → 📡 Agent桥接 → 🔗 第三方集成 → ☁️ 云服务 │
│  为上层AI审计大脑提供标准化数据接口和智能分析服务           │
└─────────────────────────────────────────────────────────────┘
```

### Layer Details:

1. **Layer 1 (layer1/)**: Intelligent Data Ingestion & Standardization
   - `enhanced_data_ingestor.py`: Multi-source connectors for mainstream financial systems
   - `ai_schema_inferrer.py`: AI-powered schema inference with business context
   - `intelligent_data_scrubber.py`: Smart data cleaning with audit-specific rules
   - `hybrid_storage_manager.py`: Hybrid storage with data lake + warehouse + cache

2. **Layer 2 (layer2/)**: Tiered Storage & Data Management
   - `storage_optimizer.py`: Cold-hot data separation and intelligent compression
   - `data_lineage_tracker.py`: Complete data lineage tracking for audit trails
   - `version_controller.py`: Data version control and rollback capabilities
   - `performance_optimizer.py`: Dynamic indexing and query optimization

3. **Layer 3 (layer3/)**: AI-Enhanced Audit Rules Engine
   - `ai_audit_rules_engine.py`: Self-learning audit rules with ML capabilities
   - `adaptive_account_mapper.py`: Intelligent account mapping using NLP
   - `anomaly_detector.py`: ML-powered anomaly detection (unsupervised + supervised)
   - `audit_knowledge_base.py`: Accumulated audit knowledge and patterns

4. **Layer 4 (layer4/)**: Multi-Modal Analysis & Output Services
   - `standard_report_generator.py`: Audit template-based report generation
   - `interactive_analyzer.py`: Drag-and-drop interactive analysis interface
   - `nl_audit_agent.py`: Natural language AI agent for complex audit queries
   - `multi_format_exporter.py`: Export to various formats (Excel, PDF, Word, JSON)

5. **Layer 5 (layer5/)**: External Integration & API Services
   - `enhanced_api_server.py`: RESTful API with audit-specific endpoints
   - `ai_agent_bridge.py`: Communication bridge with external AI systems
   - `third_party_integrator.py`: Integration with external audit tools
   - `cloud_service_connector.py`: Cloud-native deployment and services

## Core Entry Points

- `main_engine.py`: Enhanced core processing engine with AI-powered workflow
- `dap_launcher.py`: Modernized GUI launcher with real-time progress and AI chat
- `ai_audit_agent.py`: Natural language AI agent for audit analysis
- `performance_monitor.py`: Real-time system performance monitoring
- `self_learning_manager.py`: AI self-learning and model management

## Common Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment using the install script
install.bat
```

### Running the Application
```bash
# Start enhanced GUI mode (recommended)
start_gui.bat
# Equivalent to: python dap_launcher.py --enhanced-ui

# Start AI-enhanced API server mode
start_api.bat
# Equivalent to: python -c "from layer5.enhanced_api_server import start_api_server; start_api_server(host='127.0.0.1', port=8000, ai_enabled=True)"

# Start CLI mode with AI assistant
start_cli.bat
# Equivalent to: python main_engine.py --ai-assistant

# Start AI learning mode
start_learning.bat
# Equivalent to: python self_learning_manager.py --train-models

# Start performance monitoring
start_monitor.bat
# Equivalent to: python performance_monitor.py --dashboard
```

### Testing
```bash
# Run comprehensive test suite
python -m pytest tests/ -v --cov=.

# Test AI capabilities
python -m pytest tests/test_ai_capabilities.py -v

# Test performance benchmarks
python -m pytest tests/test_performance.py -v --benchmark

# Test specific modules
python -c "import sys; sys.path.append('.'); from main_engine import EnhancedDAPEngine; print('Enhanced engine imported successfully')"

# Test AI models
python -c "from layer3.ai_audit_rules_engine import AIAuditRulesEngine; engine = AIAuditRulesEngine(); print('AI engine initialized successfully')"

# Test financial system connectors
python layer1/enhanced_data_ingestor.py --test-connectors
```

### Development Tools
```bash
# Code formatting (if configured)
black .
flake8 .

# Install optional development dependencies
pip install pytest black flake8

# Test new features (batch import and AIS support)
python demo_new_features.py

# Test data ingestor with new functionality
python layer1/data_ingestor.py
```

## Database Structure

The system uses a hybrid storage architecture optimized for audit workflows:

### Primary Storage (TiDB/SQLite)
- `raw_input` schema: Original imported data with full lineage
- `cleaned` schema: Standardized and cleaned data
- `normalized` schema: Normalized data following audit standards
- `audit_views` schema: Specialized audit analysis views
- `analytics` schema: Pre-computed analytical results
- `ai_ready` schema: AI-optimized data structures

### Data Lake Storage (MinIO/S3)
- `archives/` directory: Compressed historical data (ZSTD compression)
- `backups/` directory: Original backup files with metadata
- `exports/` directory: Generated reports and exports
- `models/` directory: Trained AI models and versions

### Vector Database (ChromaDB)
- Account mapping vectors for semantic similarity
- Audit pattern embeddings for intelligent matching
- Transaction behavior vectors for anomaly detection

### Cache Layer (Redis)
- Frequently accessed query results
- User session data and preferences
- Real-time monitoring metrics
- AI model predictions cache

## Configuration

### Audit Rules
- Edit `config/audit_rules.yaml` to customize audit rules
- Rules support classification, aggregation, and validation types

### Supported Data Formats

#### Financial System Connectors
- **金蝶 (Kingdee)**: K/3 Cloud, K/3 WISE, KIS系列 (.bak, .sql, .xlsx, API)
- **用友 (UFIDA)**: U8+, NC, YonBIP系列 (.bak, .acc, .xlsx, API)
- **SAP**: ERP, S/4HANA (.csv, .txt, .xlsx, RFC)
- **其他ERP**: 浪潮、博科、速达等 (通用格式)

#### File Formats
- Excel files (.xlsx, .xls) with intelligent sheet detection
- CSV files (.csv) with encoding auto-detection
- Database backups (.bak, .sql) with system-specific parsing
- Database files (.db, .sqlite, .mdb, .accdb) with direct connection
- **Enhanced AIS support** - Advanced parsing for multiple AIS vendors
- Archive files (.zip, .rar, .7z) with recursive extraction
- **Smart folder detection** - Auto-identifies database collections

#### Advanced Capabilities
- **Parallel batch processing** - Up to 100 files simultaneously
- **Incremental import** - Delta detection for updated data
- **Real-time monitoring** - Live data feeds from active systems
- **AI-assisted parsing** - Intelligent format recognition and conversion

## API Endpoints

When enhanced API server is running (port 8000):

### Core Data Operations
- `GET /api/v2/info` - Enhanced system information with AI status
- `GET /api/v2/companies` - List all client companies with statistics
- `GET /api/v2/data/{company_id}/{table_name}` - Get company-specific data
- `POST /api/v2/import` - Import new data with progress tracking
- `POST /api/v2/export/{format}` - Multi-format export with templates

### AI-Enhanced Analysis
- `POST /api/v2/ai/query` - Natural language query processing
- `POST /api/v2/ai/analyze` - AI-powered data analysis
- `POST /api/v2/ai/anomalies` - Anomaly detection with ML
- `GET /api/v2/ai/insights/{company_id}` - Generated audit insights
- `POST /api/v2/ai/feedback` - User feedback for model improvement

### Audit-Specific Operations
- `GET /api/v2/audit/templates` - Available audit report templates
- `POST /api/v2/audit/generate` - Generate audit reports
- `GET /api/v2/audit/rules` - List active audit rules
- `POST /api/v2/audit/validate` - Data validation with audit rules

### System Management
- `GET /api/v2/performance` - Real-time performance metrics
- `GET /api/v2/health` - System health check
- `POST /api/v2/models/retrain` - Trigger AI model retraining
- `GET /api/v2/logs` - System operation logs
- `GET /docs` - Interactive API documentation with examples

## Key Design Principles

1. **First Principles Thinking**: Solve audit data challenges from fundamental requirements
2. **KISS Principle**: One-click drag-and-drop operation with zero configuration
3. **SOLID Architecture**: Modular, extensible, maintainable code structure
4. **Audit-Centric**: Every component optimized for professional audit workflows
5. **AI-Enhanced Intelligence**: Self-learning system with continuous improvement
6. **Hybrid Storage**: Optimal cost-performance with data lake + warehouse architecture
7. **Professional Integration**: Native support for mainstream financial systems
8. **Performance-First**: Sub-second response times with intelligent caching
9. **Security & Compliance**: Audit trail, data lineage, and regulatory compliance
10. **Future-Proof**: Designed for scalability and emerging AI technologies

## Important Notes

- The system is designed for Windows environments primarily (uses .bat scripts)
- Virtual environment is managed in `dap_env/` directory
- Logs are written to `logs/` directory and `dap.log`
- Data is stored in `data/` directory
- Exports go to `exports/` directory
- Temporary files use `temp/` directory (if exists)

## Working with the Codebase

### Architecture Guidelines
- Follow the **five-layer architecture** when adding new features
- **Layer 1**: Universal data ingestion and standardization
- **Layer 2**: Intelligent storage and data management
- **Layer 3**: AI-enhanced audit rules and analysis
- **Layer 4**: Multi-modal analysis and output services
- **Layer 5**: External integration and API services

### Development Principles
- Apply **First Principles** thinking for problem-solving
- Follow **KISS Principle** for implementation simplicity
- Adhere to **SOLID Principles** for code quality
- Implement comprehensive error handling and logging
- Use type hints and comprehensive documentation
- Write unit tests for all new functionality
- Maintain backward compatibility with existing data

### AI/ML Integration
- Store all models in the centralized model registry
- Use vector databases for semantic operations
- Implement proper model versioning and rollback
- Add user feedback loops for continuous learning
- Monitor model performance and drift detection

### Performance Considerations
- Use async/await for I/O operations
- Implement intelligent caching strategies
- Optimize database queries with proper indexing
- Use streaming for large file processing
- Monitor memory usage and implement cleanup

### Security & Compliance
- Implement data encryption at rest and in transit
- Add audit logging for all operations
- Use role-based access control
- Maintain data lineage for compliance
- Regular security audits and updates

## AI-Enhanced Features (Latest Updates)

### Intelligent Financial System Integration
- **Multi-System Support**: Native connectors for 金蝶、用友、SAP、ERP systems
- **AI System Detection**: Automatically identifies source financial system type
- **Smart Data Mapping**: AI-powered account mapping with semantic understanding
- **Real-time Progress**: Live progress tracking for large imports
- **Error Recovery**: Intelligent error handling with auto-retry mechanisms

### AI-Powered Audit Analysis
- **Natural Language Queries**: "分析A公司2023年管理费用异常波动"
- **Anomaly Detection**: ML-based detection of unusual transactions and patterns
- **Account Mapping Learning**: Self-improving account standardization
- **Audit Pattern Recognition**: Learns from audit expert feedback
- **Risk Assessment**: Automated risk scoring for transactions and entities

### Advanced Data Processing
- **Hybrid Storage**: Data lake + warehouse + cache for optimal performance
- **Streaming Processing**: Handle massive datasets without memory issues
- **Intelligent Compression**: ZSTD compression with 70% storage reduction
- **Data Lineage**: Complete audit trail from source to analysis
- **Version Control**: Data versioning with rollback capabilities

### Enhanced Configuration
```yaml
# AI-Enhanced Configuration
ai_capabilities:
  account_mapping:
    model: "sentence-bert-chinese"
    confidence_threshold: 0.85
    auto_learn: true
    fallback_similarity: 0.7

  anomaly_detection:
    algorithms: ["isolation_forest", "autoencoder", "xgboost"]
    ensemble_weights: [0.3, 0.3, 0.4]
    retrain_frequency: "weekly"

  natural_language:
    provider: "openai"
    model: "gpt-4"
    chinese_optimization: true
    audit_context: true

# Performance Optimization
performance:
  parallel_workers: 8
  memory_limit: "8GB"
  cache_strategy: "intelligent"
  compression: "zstd"
  index_optimization: "dynamic"
```

### Enhanced Usage Examples
```python
# Import with AI-enhanced processing
from layer1.enhanced_data_ingestor import EnhancedDataIngestor
ingestor = EnhancedDataIngestor()

# Auto-detect and process financial system backup
result = ingestor.intelligent_import("金蝶K3备份_2024.bak")

# Natural language audit query
from layer4.nl_audit_agent import NLAuditAgent
agent = NLAuditAgent()
response = agent.query("找出本年度所有超过10万元的异常费用支出")

# AI-powered anomaly detection
from layer3.anomaly_detector import AnomalyDetector
detector = AnomalyDetector()
anomalies = detector.detect_with_ai(company_data)

# Adaptive account mapping
from layer3.adaptive_account_mapper import AdaptiveAccountMapper
mapper = AdaptiveAccountMapper()
mappings = mapper.smart_map(source_accounts, feedback_data)
```

### Self-Learning Capabilities
```python
# Continuous learning from user feedback
from self_learning_manager import SelfLearningManager
learning_manager = SelfLearningManager()

# Learn from successful analysis patterns
learning_manager.learn_from_success(user_actions, results, feedback)

# Update models with new data
learning_manager.retrain_models(incremental=True)

# Generate improvement suggestions
suggestions = learning_manager.suggest_optimizations(current_workflow)
```