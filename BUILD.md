# 打包指南(BUILD.md)

> 本文档面向 AI 编码代理 / 工程师,说明如何把本仓库打包为 Windows 可执行发布包
> (`HouseholdLoadForecast-release.zip`)。按步骤执行即可复现成功打包。

---

## 1. 打包目标

- **输出形态:** PyInstaller **onedir** 模式(`dist\HouseholdLoadForecast\` 下含 exe + `_internal\` 依赖树)
- **入口:** `main.py` → PyQt5 登录窗口 → 主窗口
- **分发包:** `HouseholdLoadForecast-release.zip`(整个 `dist\HouseholdLoadForecast\` 目录压缩)
- **目标平台:** Windows 10/11 x64,接收方无需安装 Python / PyTorch
- **典型产物大小:** zip ~250 MB,解压后 ~580 MB

---

## 2. 环境要求

| 项 | 要求 | 验证 |
|---|---|---|
| 操作系统 | Windows 10/11 x64 | PyInstaller 不支持跨平台打包 |
| Python | **3.12.x**(已验证 3.12.10) | `python --version` |
| Shell | PowerShell(本文命令基于此) | - |
| 可用磁盘 | 至少 **3 GB** | 下载依赖 + `.venv` + `build/` + `dist/` 临时占用 |
| 网络 | 能访问 PyPI(首次装依赖需下载 ~250 MB) | - |
| 仓库完整性 | `resources\checkpoints\*.pth` 必须存在 12 个,合计 ~70 MB | 本仓库用 Git LFS 托管 |

**不推荐** Python 3.13+(部分 torch/PyQt5 wheel 尚未齐全)。

---

## 3. 依赖版本锁定(关键)

### 运行依赖(`requirements.txt`)

```
pandas>=2.0.0
PyQt5>=5.15.0
numpy>=1.24.0
torch>=2.0.0
matplotlib>=3.7.0
```

### 打包时必须进一步约束

| 依赖 | 打包期必用版本 | 原因 |
|------|--------------|------|
| **torch** | **`torch==2.5.1+cpu`** | torch 2.6+ 在 Windows + PyInstaller 6.x 下扫描 `torch._inductor` / `torch.distributed` DLL 时会触发 isolated subprocess 死锁,产物永远构不出来(观测到 ≥12 分钟 0 进展后需手动 kill) |
| **numpy** | **`numpy<2`**(建议 1.26.4) | torch 2.5.x 对 numpy 2.x 兼容不稳,PyInstaller hook 扫描时会抛 UserWarning 并可能漏打 numpy 子模块 |
| **PyInstaller** | `>=6.0.0`(本文验证 6.20.0) | 由 `build.ps1` 自动安装 |

安装命令:

```powershell
pip install -r requirements.txt
pip install "torch==2.5.1+cpu" "numpy<2" --upgrade
```

> ⚠️ 不要升级 `requirements.txt` 里的 torch 下限。保留 `>=2.0.0` 的宽松约束只是给"从源码跑"的人用;打包时必须手动锁死 2.5.1。

---

## 4. PyInstaller Spec 关键点

`pyinstaller.spec` 已经调试完毕,**不要回退以下三点修复**:

### 4.1 不得排除 torch 内部子模块

**错误做法(会导致运行时 `ModuleNotFoundError`)**:

```python
excludes = ['torch.distributions', 'torch._inductor', 'torch._dynamo',
            'torch.distributed', 'torch.onnx', 'torchgen', ...]
```

**为什么**:`inference_engine/runner.py` 里 `import torch` 延迟到方法体内,
PyInstaller 静态分析看不到完整调用链。运行时点击"预测"才 `import torch.nn`
→ `torch.utils._python_dispatch` → `import torchgen`;任何一个被 excludes
的子模块都会使 `nn.Module` 前向推理直接崩溃。

**正确做法**:只 exclude 本项目根本没装的外部框架:

```python
_UNUSED_FRAMEWORK_EXCLUDES = [
    'tensorflow', 'jax', 'jaxlib', 'sklearn',
    'IPython', 'jupyter', 'notebook', 'pytest',
    'torch.utils.tensorboard',  # 未装 tensorboard,确定无依赖
]
```

### 4.2 `torchgen` 必须整目录作为 data 打入

`torchgen/__init__.py` 是**空文件**(0 字节),所以:

- `hiddenimports=['torchgen']` → PyInstaller 只分析空 `__init__.py` → 一个 `.py` 都不打
- `collect_submodules('torchgen')` → 尝试 import 每个子文件,很多需要 `PyYAML`(torch 非运行时依赖,默认不装)→ 静默 drop

**唯一可靠的做法**:把整个 torchgen 源码目录以 data 形式整体复制:

```python
import os, torchgen
_TORCHGEN_DIR = os.path.dirname(torchgen.__file__)

a = Analysis(
    ...,
    datas=[
        ('resources', 'resources'),
        (_TORCHGEN_DIR, 'torchgen'),    # ← 关键
    ],
    hiddenimports=[
        'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
        'torchgen',
    ],
    ...,
)
```

### 4.3 `resources\checkpoints\*.pth` 必须随包走

这是 `datas=[('resources', 'resources'), ...]` 在起作用。**打包前务必检查**
12 个 `.pth` 都在位,否则预测会找不到模型:

```powershell
$ck = Get-ChildItem resources\checkpoints\*.pth
if ($ck.Count -ne 12) { throw "缺少模型权重!期望 12 个 .pth,实得 $($ck.Count)" }
```

### 4.4 Post-build:把用户手册复制到 exe 同目录

`pyinstaller.spec` 在 `COLLECT` 末尾追加了一段 `shutil.copy`,把仓库根的
`USER_GUIDE.md` 与 `README.md` 复制到 `dist\HouseholdLoadForecast\` 顶层,
让用户解压后无需翻 `_internal\` 就能看到说明。这段**不可删**:

```python
import shutil as _shutil
_DIST_ROOT = os.path.join(DISTPATH, 'HouseholdLoadForecast')
for _doc in ('USER_GUIDE.md', 'README.md'):
    _src = os.path.join(os.path.dirname(os.path.abspath(SPEC)), _doc)
    if os.path.isfile(_src) and os.path.isdir(_DIST_ROOT):
        _shutil.copy2(_src, os.path.join(_DIST_ROOT, _doc))
```

---

## 5. 打包步骤(复制即用)

> **不要用 `build.ps1` 直接执行打包**。
> 原因:`build.ps1` 设置了 `$ErrorActionPreference = 'Stop'`,PyInstaller 把进度信息
> 写到 stderr 会被 PowerShell 当作错误抛出,脚本未等 PyInstaller 实际启动就会终止。
> 改为直接调用 `.venv\Scripts\python.exe -u -m PyInstaller`。

### 5.1 预检(可选但推荐)

```powershell
cd <REPO_ROOT>  # 例如 E:\temp\HouseholdLoadForecastSystem\HouseholdLoadForecastSystem

# 检查 checkpoint
$ck = Get-ChildItem resources\checkpoints\*.pth
Write-Host "checkpoints count: $($ck.Count)  (expect 12)"

# 检查 python
python --version  # expect 3.12.x

# 检查磁盘
Get-PSDrive (Get-Location).Drive.Name | Select-Object Free
```

### 5.2 建立干净虚拟环境

```powershell
# 清掉旧环境(可能是别的 Python 版本下建的)
Remove-Item -Recurse -Force .venv, build, dist, dist.zip, HouseholdLoadForecast-release.zip -ErrorAction SilentlyContinue

# 重建
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

### 5.3 装依赖(含版本锁)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install "torch==2.5.1+cpu" "numpy<2" --upgrade

# 装 PyInstaller
.\.venv\Scripts\python.exe -m pip install "pyinstaller>=6.0.0"
```

### 5.4 运行 PyInstaller

```powershell
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -u -m PyInstaller --noconfirm --log-level=WARN pyinstaller.spec
```

**典型耗时:** 90–150 秒(在 SSD + 16GB 内存的机器上)。

**典型输出末尾:**

```
INFO: Building COLLECT HouseholdLoadForecast completed successfully.
```

PowerShell 会回到提示符,`$LASTEXITCODE` 应为 `0`。

### 5.5 验证产物

```powershell
# 1. 12 个 checkpoint 都进了 _internal
(Get-ChildItem dist\HouseholdLoadForecast\_internal\resources\checkpoints\*.pth).Count  # 期望 12

# 2. torchgen 目录完整(不是只有 packaged/)
Test-Path dist\HouseholdLoadForecast\_internal\torchgen\__init__.py  # 期望 True
Test-Path dist\HouseholdLoadForecast\_internal\torchgen\gen.py       # 期望 True

# 3. 用户手册在 exe 同目录
Test-Path dist\HouseholdLoadForecast\USER_GUIDE.md   # 期望 True
Test-Path dist\HouseholdLoadForecast\README.md       # 期望 True

# 4. 产物尺寸合理
$all = Get-ChildItem dist\HouseholdLoadForecast -Recurse -File
Write-Host ("files: {0}, total: {1:N1} MB" -f $all.Count, (($all | Measure-Object Length -Sum).Sum/1MB))
# 期望:~3000 文件,~580 MB
```

### 5.6 冒烟测试(三层)

#### 层 1:.venv 端到端推理(不依赖 exe)

```powershell
.\.venv\Scripts\python.exe -c @"
import numpy as np, pandas as pd
from services.forecast_service import ForecastService
idx = pd.date_range('2024-01-01', periods=512, freq='h')
vals = pd.Series(np.sin(np.linspace(0, 40, 512)) * 5 + 20, index=idx, name='WHE')
svc = ForecastService()
for mid in ['patchtst_ampds', 'timexer_londonb0', 'dc_itransformer_ampds']:
    for h in ['1d', '7d']:
        out = svc.run_forecast(mid, h, vals)
        print(f'{mid:30s} {h}  pred={len(out.prediction)} mean={out.prediction.mean():.3f}')
print('ALL OK')
"@
```

期望输出含 `ALL OK`,并看到 6 行成功行(3 模型 × 2 horizon)。

#### 层 2:pytest 打包约束

```powershell
.\.venv\Scripts\python.exe -m pip install "pytest>=8.0.0"
.\.venv\Scripts\python.exe -m pytest -v
```

期望 **4/4 passed**。

#### 层 3:exe 冷启动

```powershell
$exe = "dist\HouseholdLoadForecast\HouseholdLoadForecast.exe"
$proc = Start-Process $exe -PassThru
Start-Sleep 10
$p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
if ($p) {
    Write-Host ("exe OK: Title={0}, Mem={1}MB" -f $p.MainWindowTitle, [math]::Round($p.WorkingSet64/1MB))
    Stop-Process -Id $proc.Id -Force
} else {
    throw "exe 启动后 10 秒内崩溃"
}
```

期望 `Title=登录, Mem=160MB 左右`。

### 5.7 打 release zip

```powershell
Compress-Archive `
    -Path dist\HouseholdLoadForecast `
    -DestinationPath HouseholdLoadForecast-release.zip `
    -CompressionLevel Optimal

# 生成 SHA256 便于分发校验
Get-FileHash HouseholdLoadForecast-release.zip -Algorithm SHA256 | Format-List
```

期望 zip 约 **240–260 MB**。

---

## 6. 已知踩坑与规避

| 现象 | 根因 | 规避 |
|------|------|------|
| `build.ps1` 启动后立刻报 NativeCommandError,PyInstaller 未真正运行 | `$ErrorActionPreference = 'Stop'` + PyInstaller 写 stderr | 不用 `build.ps1`,直接 `python -m PyInstaller` |
| PyInstaller 卡在 "Looking for dynamic libraries" ≥10 分钟 CPU 0,进程不死 | `torch>=2.6` 的 `_inductor`/`distributed` DLL 扫描与 isolated subprocess 死锁 | 锁 `torch==2.5.1+cpu` |
| 打包完 exe 启动 OK,点预测报 `ModuleNotFoundError: torchgen` | `torchgen` 被错误 excludes,或只打了空 `__init__.py` | 见 §4.1 / §4.2 |
| 产物里 `_internal\resources\checkpoints\` 缺 .pth | 打包前 Git LFS 未拉取模型文件 | 打包前 `git lfs pull` 并检查 12 个 .pth 都在 |
| exe 启动闪退、没有窗口 | `_internal\torchgen\` 缺文件 / PyQt5 hidden import 丢失 | 按 §5.5 的 4 项检查逐条确认 |
| 对方电脑 SmartScreen 拦 exe | 未签名 | 对方右键 exe → 属性 → 勾选"解除锁定" |
| 预测结果与源码直接跑不一致 | 通常是输入长度不够,模型训练时 seq_len=256/512 | 输入至少 256 个小时点 |

---

## 7. 交付清单

完成打包后应产出(位于仓库根):

1. `dist\HouseholdLoadForecast\` — 完整 onedir 目录(开发调试用)
2. `dist\HouseholdLoadForecast\HouseholdLoadForecast.exe` — 主入口
3. `dist\HouseholdLoadForecast\USER_GUIDE.md` — 终端用户使用手册
4. `dist\HouseholdLoadForecast\README.md` — 开发者说明
5. **`HouseholdLoadForecast-release.zip`** — 最终分发物
6. zip 的 SHA256 校验值(随分发附上)

---

## 8. 给对方的使用说明模板

连同 zip 一起发出去:

```
解压 HouseholdLoadForecast-release.zip 到任意目录(路径避免中文空格以外的特殊字符)。
进入 HouseholdLoadForecast\ 文件夹,双击 HouseholdLoadForecast.exe。

首次启动会在 exe 同目录自动创建 data\、runtime\ 两个文件夹。
账号与历史记录仅保存在本机。

详细用法见同目录 USER_GUIDE.md。

系统要求:Windows 10/11 x64,无需安装 Python / PyTorch。
SmartScreen 拦截时:右键 exe → 属性 → 勾选"解除锁定"。

SHA256: <随附>
```

---

## 9. 关键文件索引

| 文件 | 作用 |
|------|------|
| `pyinstaller.spec` | PyInstaller 配置,含 excludes / torchgen 处理 / post-build 复制 |
| `requirements.txt` | 运行依赖(宽松下限) |
| `requirements-dev.txt` | pytest 等测试依赖 |
| `build.ps1` | 已存在但**不推荐直接调用**(见 §5) |
| `main.py` | GUI 入口 |
| `tests/test_packaging.py` | 打包约束测试(checkpoint 路径、spec 完整性) |
| `resources\configs\models.json` | 模型注册表,决定哪个 checkpoint 匹配哪个 model_id × horizon |
| `USER_GUIDE.md` | 面向终端用户的使用手册 |

---

## 10. 最近一次成功打包的指标(参考)

- Python 3.12.10 + torch 2.5.1+cpu + numpy 1.26.4 + PyInstaller 6.20.0
- 打包耗时 ≈ 90 秒
- `dist\HouseholdLoadForecast\` ≈ 580 MB / 3197 个文件
- `HouseholdLoadForecast-release.zip` ≈ 251.6 MB
- exe 冷启动内存 ≈ 164 MB,首次点预测约 1–3 秒出结果
- pytest 4/4 通过
