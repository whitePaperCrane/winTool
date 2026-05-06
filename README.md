# 北北-Windows 系统优化工具

一个面向 Windows 的桌面系统工具，使用 PyQt6 构建界面，封装系统信息查看、虚拟内存、电源计划、安全警告和常用系统设置。

## 功能

- 查看系统、CPU、主板、内存、显卡、磁盘和本机 IP 信息。
- 查看并调整虚拟内存分页文件配置。
- 设置 Windows 视觉效果为最佳性能。
- 管理安全警告相关注册表项，并提供恢复入口。
- 添加并启用“卓越性能”电源计划。
- 开启或关闭系统休眠。
- 修改计算机名。
- 修改部分任务栏设置。

## 环境

项目已舍弃 PyQt5，仅使用 PyQt6。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 运行

```powershell
.\.venv\Scripts\python.exe main.py
```

部分系统修改功能需要管理员权限。普通用户模式下触发这类操作时，程序会通过 UAC 打开管理员权限的新窗口。

## 打包为 exe

完整打包命令已保存到 `build_exe.ps1`：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name winTool --icon "app.ico" --add-data "app.ico;." "main.py"
```

执行打包：

```powershell
.\build_exe.ps1
```

打包产物：

```text
dist\winTool.exe
```

如果重复打包时 PyInstaller 提示输出目录已存在，请先手动处理旧产物，或在确认可以覆盖后自行追加 PyInstaller 参数。

## 注意

本工具会修改注册表、电源计划、分页文件、计算机名和任务栏设置。高风险操作已加入确认提示，但仍建议先了解每个按钮的作用，再执行系统修改。
