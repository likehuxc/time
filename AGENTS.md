# AGENTS.md

> 本仓库面向 AI 编码代理的上下文说明。

## 项目简介

**Household Load Forecast System** —— 桌面端家庭负荷预测系统,基于 PyQt5 GUI + PyTorch 推理引擎,从 CSV 历史用电数据预测未来 1 天 / 7 天负荷。

用户在登录后通过界面导入 CSV、选择模型与预测跨度,由本地 `.pth` checkpoint 执行推理,结果持久化到 SQLite。发布形态为 PyInstaller onedir 可执行包。

## 技术栈

- **语言:** Python 3.9+(最低版本受 `Path.is_relative_to()` 约束)
- **GUI:** PyQt5 ≥ 5.15
- **推理:** PyTorch ≥ 2.0(自实现 PatchTST / TimeXer / DC-iTransformer 运行时)
- **数据:** pandas ≥ 2.0、numpy ≥ 1.24
- **可视化:** matplotlib ≥ 3.7
- **持久化:** SQLite(`sqlite3` 标准库)+ JSON 用户表
- **测试:** pytest ≥ 8.0
- **包管理:** `pip` + 项目本地 `.venv`(`requirements.txt` / `requirements-dev.txt`)
- **打包:** PyInstaller ≥ 6.0,onedir 模式

## 目录结构

```
app/                 # 应用级配置:paths(路径常量)、config(JSON 加载)、bootstrap(创建运行期目录)
services/            # 业务服务层
  auth_service.py    # PBKDF2-SHA256 密码哈希 + 注册/登录规则
  user_store.py      # users.json 读写
  data_service.py    # CSV 载入 + 列校验 + 归一化到小时频率
  forecast_service.py# 预测入口:horizon→steps、registry→runner
  record_service.py  # SQLite prediction_records 表读写
inference_engine/    # 模型推理引擎
  runner.py          # ForecastRunner:输入窗口 → 预测向量
  model_registry.py  # 按 model_id + horizon 解析 checkpoint
  patchtst_runtime_model.py / timexer_runtime_model.py / dc_runtime_*.py
  resampler.py       # 重采样到 1h
  schema.py          # CSV 必填列校验
  time_features_hourly.py
ui/                  # PyQt5 界面
  main_window.py / login_window.py / register_dialog.py / change_password_dialog.py / password_field.py
  pages/             # 主窗口内分页:data / forecast / records / user
resources/           # 随包分发的只读资源(会被 PyInstaller 打入 _internal)
  checkpoints/       # 12 个 .pth 权重(3 模型 × 2 数据集 × 2 horizon)
  configs/           # models.json(模型注册表)、template_schema.json(CSV 模板)
  templates/         # household_load_template.csv
data/                # 运行时用户 CSV 目录(由 bootstrap() 创建,当前为空)
runtime/             # 运行时可变数据:forecast.db(SQLite)、users.json
tests/               # pytest 测试(当前仅 test_packaging.py)
main.py              # 入口:bootstrap → QApplication → LoginWindow → MainWindow
build.ps1            # Windows 打包脚本(创建/复用 .venv,安装依赖,调用 pyinstaller.spec)
pyinstaller.spec     # PyInstaller 配置(onedir,resources 作为 data 打入)
pytest.ini           # pythonpath = .
```

## 常用命令

所有命令在 **项目根目录** 的激活 venv 中执行(PowerShell)。

| 任务 | 命令 |
|------|------|
| 创建虚拟环境 | `python -m venv .venv` |
| 激活 venv | `.venv\Scripts\activate` |
| 安装运行依赖 | `pip install -r requirements.txt` |
| 安装开发依赖 | `pip install -r requirements-dev.txt` |
| 启动桌面应用 | `python main.py` |
| 运行全部测试 | `pytest` |
| 运行单个测试 | `pytest tests/test_packaging.py::test_build_ps1_exists` |
| Windows 打包(onedir) | `.\build.ps1` |
| 构建产物路径 | `dist\HouseholdLoadForecast\HouseholdLoadForecast.exe` |

无 lint / format / typecheck 配置,仓库未强制执行。

## 代码约定

- 所有源文件以单行英文 docstring 起首描述模块职责(见 `main.py`、`services/*.py`)。
- `from __future__ import annotations` 默认启用;类型标注大量使用 `Optional` / `Union` / `typing.Final`。
- 数据类统一用 `@dataclass(frozen=True)`(见 `ForecastOutput`、`PreparedCsvResult`)。
- 向用户抛出的异常消息使用中文(例如 `AuthError`、CSV 列校验错误);内部注释多为英文。
- JSON 读写统一 `encoding="utf-8"`。
- 路径统一通过 `app.paths`(`PROJECT_ROOT` / `DATA_DIR` / `RESOURCES_DIR` / `RUNTIME_DIR`)取得,**不要硬编码绝对路径**。
- 模型 checkpoint 相对路径必须以 `resources/checkpoints/` 开头(被 `test_models_registry_uses_project_relative_checkpoint_paths` 强制)。

## 测试

- 框架:pytest,配置见 `pytest.ini`(`pythonpath = .`,允许 `from app...` 风格导入)。
- 位置:`tests/`,当前覆盖打包层(`build.ps1` / `pyinstaller.spec` / checkpoint 路径与存在性)。
- 新增测试:文件名以 `test_` 开头,函数以 `test_` 开头;尽量走 `app.config` / `app.paths` 提供的公开 API,不要直接读文件。

## 注意事项 / 易踩坑

- **Python 最低版本 3.9**,不要使用 3.10+ 独有语法(如 `match`、`X | Y` 作为类型在运行期求值的场景);已有的 `X | Y` 位置均在 `from __future__ import annotations` 的文件里。
- **PyQt5 而非 PyQt6 / PySide6**,API 差异不少;`pyinstaller.spec` 的 `hiddenimports` 锁死 PyQt5 三大模块。
- **`data/` 与 `runtime/` 的职责区分**:`data/` 是用户导入的 CSV(只读为主),`runtime/` 存放应用可写状态(`forecast.db`、`users.json`)。不要把用户数据写进 `data/`。
- **CSV 必须包含 `WHE` 列**(见 `resources/configs/template_schema.json`),可选列:`date`、`OT`、`Wind`、`RH`;目标频率统一为 `1h`。
- **密码哈希**:PBKDF2-SHA256,310,000 轮,16 字节 salt(`services/auth_service.py` 中的 `_ITERATIONS`、`_SALT_BYTES`);修改这些常量会使已注册用户无法登录。
- **打包时 `resources/` 会被复制进 `_internal`**,运行时读取要走 `app.paths.RESOURCES_DIR`(已自动适配开发 / 打包两种形态)。
- **checkpoint 不能用绝对路径**(尤其禁止 `D:/...`),测试会失败。

## 不要修改

- `resources/checkpoints/*.pth` —— 训练好的模型权重,非本项目训练流程产出。
- `runtime/forecast.db`、`runtime/users.json` —— 用户生成数据,改动会影响现有账户与历史记录。
- `build/`、`dist*/`、`.venv/`、`__pycache__/` —— 构建与环境产物。
- `dist.zip` —— 已归档的分发包。
