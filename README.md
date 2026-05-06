# 北北-Windows 系统优化工具

一个面向 Windows 的桌面系统设置工具，使用 Qt 界面封装常见优化项和系统信息查看功能。

## 功能

- 查看系统、CPU、主板、内存、显卡、磁盘和本机 IP 信息
- 查看并调整虚拟内存分页文件配置
- 调整 Windows 视觉效果、电源计划、休眠状态和任务栏设置
- 修改计算机名
- 管理部分安全警告相关注册表项，并提供恢复入口

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

源码优先使用 PyQt6；如果本机环境只有 PyQt5，程序会进入兼容模式以便启动。

## 注意

部分功能会修改注册表、电源计划、分页文件或计算机名，建议先以普通用户启动查看信息，需要管理员权限的操作会触发 UAC。修改虚拟内存、计算机名和部分系统策略后，可能需要重启 Windows 才能完全生效。
