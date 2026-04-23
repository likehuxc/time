# Household Load Forecast System

桌面负荷预测系统 — 本仓库为独立项目骨架。

## 环境要求

- Python 3.9 或更高版本

说明：测试使用了 `pathlib.Path.is_relative_to()`，因此最低支持版本为 Python 3.9。

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
pip install -r requirements-dev.txt
pytest
```

## 布局

- `data/` — 数据目录（由启动时创建）
- `resources/` — 资源目录
- `runtime/` — 运行时目录

路径常量见 `app.paths`；`main.py` 调用 `bootstrap()` 创建上述目录。

## Windows 打包发布（exe + resources）

思路：使用 PyInstaller **onedir** 模式，生成可执行文件与 `_internal` 目录（内含依赖与打包进镜像的 `resources/`），便于拷贝整份 `dist\HouseholdLoadForecast\` 分发。

1. 在同一 Python 环境中安装运行依赖：`pip install -r requirements.txt`
   如需运行测试，再额外安装：`pip install -r requirements-dev.txt`
2. 在项目根目录执行（PowerShell）：

```powershell
.\build.ps1
```

脚本会（可选）激活 `.venv`，安装 PyInstaller，并执行根目录下的 `pyinstaller.spec`。

3. 构建产物路径：`dist\HouseholdLoadForecast\HouseholdLoadForecast.exe`

说明：`pyinstaller.spec` 以 `main.py` 为入口，并将 `resources` 目录作为数据文件一并打入包内。若需图标、额外隐藏导入或单文件模式，可再扩展该 spec。
