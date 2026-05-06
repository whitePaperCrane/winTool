# AGENTS.md

## 项目定位

这是一个 Windows 桌面系统工具，主程序是 `main.py`，应用名为“北北-Windows 系统优化工具”。项目用于查看系统信息，并通过图形界面执行一组常见 Windows 系统设置。

项目已经舍弃 PyQt5，只使用 PyQt6。不要再加入 PyQt5 兼容层，也不要让新代码依赖 PyQt5 API。

## 技术栈

- Python 3
- PyQt6
- psutil
- PowerShell / WMI / CIM
- Windows 注册表
- PyInstaller

## 重要文件

- `main.py`：主程序，包含 UI、后台线程、系统命令、注册表操作和入口逻辑。
- `app.ico`：程序图标，运行和打包时都会使用。
- `requirements.txt`：依赖列表，当前包含 `PyQt6` 和 `psutil`。
- `README.md`：给用户看的运行和打包说明。
- `build_exe.ps1`：打包脚本，用于生成单文件 Windows exe。
- `.gitignore`：忽略虚拟环境、构建产物、日志和临时文件。

## 当前 UI 设计

界面已重构为深色侧边栏 + 明亮内容区的桌面控制台风格：

- 左侧为深色导航栏。
- 右侧为内容工作区。
- 每个页面顶部有标题和说明。
- 功能区使用 `QGroupBox` 分组。
- 慢查询通过 `WorkerThread` 放到后台线程，减少界面假死。
- 页面内容通过 `QScrollArea` 包裹，适配较小窗口和打包后的固定窗口体验。

后续 UI 修改应保持“工具控制台”的风格，不要回到简单控件堆叠。界面文字应简洁，按钮含义要明确。

## 功能模块

- `VirtualMemoryTab`：查看和修改虚拟内存分页文件。当前逻辑只更新所选磁盘，保留其他磁盘已有分页文件配置。
- `SystemInfoTab`：查看系统、CPU、主板、内存、显卡、磁盘和本机 IP。默认不调用第三方公网 IP API。
- `SecurityWarnTab`：管理安全警告相关注册表项。降低安全提示前必须二次确认，并提供恢复入口。
- `PowerPlanTab`：查看电源计划、启用卓越性能、开启/关闭休眠。命令结果必须检查返回码。
- `SystemSettingsTab`：修改计算机名和任务栏设置。任务栏设置会重启 Explorer。
- `SystemOptimizer`：主窗口、侧边栏、页面标题、状态栏和页面容器。

## 高风险操作

本项目会修改 Windows 系统状态，维护时必须谨慎：

- 注册表写入和删除。
- 管理员权限命令。
- PowerShell / WMI / CIM 系统配置。
- `powercfg` 电源计划命令。
- `taskkill /f /im explorer.exe`。
- 虚拟内存和计算机名修改。

新增或修改这些能力时必须满足：

- 高风险动作要有二次确认。
- 失败时不能显示成功。
- 外部命令必须检查返回码。
- 尽量提供恢复入口。
- 不要静默覆盖用户已有系统配置。

## 运行

```powershell
.\.venv\Scripts\python.exe main.py
```

## 依赖安装

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

当前环境应能通过：

```powershell
.\.venv\Scripts\python.exe -c "import PyQt6; print('PyQt6 ok')"
```

同时应确认 PyQt5 不再存在：

```powershell
.\.venv\Scripts\python.exe -c "import importlib.util; print(importlib.util.find_spec('PyQt5'))"
```

预期输出为 `None`。

## 打包

打包脚本可以保留在仓库中，方便用户后续自行生成 exe：

```powershell
.\build_exe.ps1
```

脚本中的完整命令为：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name winTool --icon "app.ico" --add-data "app.ico;." "main.py"
```

输出文件：

```text
dist\winTool.exe
```

`build_exe.ps1` 可以提交；`build/`、`dist/` 和 `*.spec` 当前被 `.gitignore` 忽略，不应提交到仓库。

## Git 信息

- 当前主分支：`main`
- 远程仓库：`https://github.com/whitePaperCrane/winTool.git`
- 本机 Git 可能需要代理：`http://127.0.0.1:7897`

## 验证建议

修改代码后至少执行：

```powershell
.\.venv\Scripts\python.exe -Wall -c "from pathlib import Path; compile(Path('main.py').read_text(encoding='utf-8'), 'main.py', 'exec'); print('syntax ok')"
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python.exe -c "from PyQt6.QtWidgets import QApplication; import main; app=QApplication([]); w=main.SystemOptimizer(); print(w.windowTitle()); print(w.pages.count())"
```

不要在没有用户明确同意的情况下实际点击会修改系统状态的按钮。

## 删除约束

禁止批量删除文件或目录。

不要使用：

- `del /s`
- `rd /s`
- `rmdir /s`
- `Remove-Item -Recurse`
- `rm -rf`

需要删除文件时，只能一次删除一个明确路径的文件，例如：

```powershell
Remove-Item "C:\path\to\file.txt"
```

如果需要批量删除文件，应停止操作并询问用户，让用户手动删除。
