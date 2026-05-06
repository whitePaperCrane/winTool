import sys
import os
import subprocess
import winreg
import platform
import psutil
import re
import socket
import logging
import ctypes
import json
from datetime import datetime
from typing import Optional, Union, List, Any, NamedTuple

# ✅ 优先使用 PyQt6；当前虚拟环境只有 PyQt5 时自动进入兼容模式
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QLineEdit, QPushButton, QMessageBox, QTextEdit, QGroupBox,
        QProgressBar, QStatusBar, QFrame, QSizePolicy, QListWidget, QListWidgetItem, QStackedWidget, QSpacerItem
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QIcon, QFont

    QT_API = "PyQt6"
    SIZE_EXPANDING = QSizePolicy.Policy.Expanding
    SIZE_MINIMUM = QSizePolicy.Policy.Minimum
    MSG_YES = QMessageBox.StandardButton.Yes
    MSG_NO = QMessageBox.StandardButton.No
    FRAME_VLINE = QFrame.Shape.VLine
    FRAME_SUNKEN = QFrame.Shadow.Sunken
except ModuleNotFoundError as exc:
    if exc.name != "PyQt6":
        raise
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QLineEdit, QPushButton, QMessageBox, QTextEdit, QGroupBox,
        QProgressBar, QStatusBar, QFrame, QSizePolicy, QListWidget, QListWidgetItem, QStackedWidget, QSpacerItem
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal
    from PyQt5.QtGui import QIcon, QFont

    QT_API = "PyQt5"
    SIZE_EXPANDING = QSizePolicy.Expanding
    SIZE_MINIMUM = QSizePolicy.Minimum
    MSG_YES = QMessageBox.Yes
    MSG_NO = QMessageBox.No
    FRAME_VLINE = QFrame.VLine
    FRAME_SUNKEN = QFrame.Sunken


# ----------------------------
# 配置与样式
# ----------------------------
class AppConfig:
    APP_NAME = "北北-Windows 系统优化工具"
    VERSION = "3.5"
    COMPANY = "北北科技"
    ICON_PATH = "app.ico"
    STYLE_SHEET = """
        * { font-family: 'Segoe UI', 'Microsoft YaHei'; }
        QMainWindow { background-color: #F5F7FA; }
        QGroupBox {
            font-weight: 600; border: 1px solid #E5E9F2; border-radius: 8px; margin-top: 18px; padding: 12px;
            background: #FFFFFF;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #556070; }
        QPushButton {
            background-color: #4A90E2; color: #FFFFFF; border: none; border-radius: 6px; padding: 9px 16px; font-weight: 600;
        }
        QPushButton:hover { background-color: #3A7BCC; }
        QPushButton:disabled { background-color: #A0B4D9; }
        QLineEdit, QComboBox, QTextEdit {
            border: 1px solid #D0D7E1; border-radius: 6px; padding: 8px; background: #FFFFFF;
        }
        QLabel { color: #2F3746; }
        QProgressBar {
            border: 1px solid #D0D7E1; border-radius: 6px; text-align: center; background: #FFFFFF; height: 16px;
        }
        QProgressBar::chunk { background-color: #4A90E2; border-radius: 6px; }
        QStatusBar {
            background: #F0F2F5; border-top: 1px solid #E5E9F2; color: #6C757D;
        }
        QListWidget {
            background: #FFFFFF; border: 1px solid #E5E9F2; border-radius: 8px; padding: 6px;
        }
        QListWidget::item { padding: 10px 12px; margin: 4px; border-radius: 6px; }
        QListWidget::item:selected { background: #4A90E2; color: #FFFFFF; }
    """


class CommandResult(NamedTuple):
    ok: bool
    stdout: str
    stderr: str
    returncode: int


# ----------------------------
# 通用工具
# ----------------------------
def resource_path(relative_path: str) -> str:
    """获取资源绝对路径，兼容 PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    path = os.path.join(base_path, relative_path)
    if not os.path.exists(path):
        for ext in ("", ".ico", ".png", ".bmp"):
            alt = path + ext
            if os.path.exists(alt):
                return alt
    return path


def is_admin() -> bool:
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin(command: List[str]) -> Optional[bool]:
    """
    以管理员权限运行命令（同步）。
    - 若当前已是管理员，直接运行并返回 True/False
    - 若不是管理员，将尝试提升本程序为管理员并返回 None（提示用户到新窗口重新操作）
    """
    if is_admin():
        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            logging.info(f"命令执行成功: {' '.join(command)}\nstdout: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"命令执行失败: {' '.join(command)}\nstderr: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"命令执行异常: {' '.join(command)}\nerr: {e}")
            return False
    else:
        try:
            params = " ".join(f'"{arg}"' if " " in arg else arg for arg in sys.argv)
            rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            if rc <= 32:
                logging.error(f"尝试提权失败，ShellExecuteW 返回码: {rc}")
                return False
            return None
        except Exception as e:
            logging.error(f"尝试提权失败: {e}")
            return False


def run_command(command: List[str], capture_output: bool = True) -> Optional[str]:
    """运行外部命令并返回 stdout（失败返回 None）"""
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            return (result.stdout or "").strip()
        logging.error(f"命令失败: {' '.join(command)}\ncode={result.returncode}\nstderr={result.stderr}")
        return None
    except Exception as e:
        logging.error(f"运行命令异常: {' '.join(command)}\nerr: {e}")
        return None


def run_command_result(command: List[str], capture_output: bool = True) -> CommandResult:
    """运行外部命令并返回完整结果，供需要校验成功/失败的操作使用"""
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0:
            logging.error(f"命令失败: {' '.join(command)}\ncode={result.returncode}\nstderr={stderr}")
        return CommandResult(result.returncode == 0, stdout, stderr, result.returncode)
    except Exception as e:
        logging.error(f"运行命令异常: {' '.join(command)}\nerr: {e}")
        return CommandResult(False, "", str(e), -1)


def set_registry_value(key, subkey: str, value_name: str, value_type, value) -> bool:
    """设置注册表值"""
    try:
        with winreg.CreateKey(key, subkey) as reg_key:
            winreg.SetValueEx(reg_key, value_name, 0, value_type, value)
        return True
    except Exception as e:
        logging.error(f"设置注册表失败: {subkey}\\{value_name}\nerr: {e}")
        return False


def delete_registry_value(key, subkey: str, value_name: str) -> bool:
    """删除单个注册表值；不存在时视为已恢复"""
    try:
        with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.DeleteValue(reg_key, value_name)
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        logging.error(f"删除注册表值失败: {subkey}\\{value_name}\nerr: {e}")
        return False


def read_reg(hive, path: str, name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        with winreg.OpenKey(hive, path) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return str(v)
    except Exception:
        return default


def mb_to_gb(mb: Union[int, float]) -> float:
    try:
        return float(mb) / 1024.0
    except Exception:
        return 0.0


def bytes_to_gb(n: Union[int, float]) -> float:
    try:
        return float(n) / (1024 ** 3)
    except Exception:
        return 0.0


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


# ----------------------------
# PowerShell JSON 辅助（避免空管道/本地化干扰）
# ----------------------------
def ps_to_json(ps_script: str, depth: int = 5) -> Any:
    """
    通过子进程执行 PowerShell，将脚本块输出统一经 ConvertTo-Json。
    使用 & { <script> } 包裹脚本块，再整体管道到 ConvertTo-Json，避免空管道元素。
    并对输出进行主体截取，容错本地化信息/提示。
    """
    command = f"$ErrorActionPreference='Stop'; & {{ {ps_script} }} | ConvertTo-Json -Depth {depth}"
    out = run_command(["powershell", "-NoProfile", "-Command", command])
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        first_obj = out.find("{")
        first_arr = out.find("[")
        first = min([x for x in [first_obj, first_arr] if x != -1], default=-1)
        last_obj = out.rfind("}")
        last_arr = out.rfind("]")
        last = max(last_obj, last_arr)
        if first != -1 and last != -1 and last > first:
            core = out[first:last + 1]
            return json.loads(core)
        return None


# ----------------------------
# 线程封装
# ----------------------------
class WorkerThread(QThread):
    finished = pyqtSignal(object)
    progress = pyqtSignal(int)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(e)


# ----------------------------
# 功能页：虚拟内存
# ----------------------------
class VirtualMemoryTab(QWidget):
    """虚拟内存设置 + 当前方案显示"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def query_pagefile_scheme(self) -> dict:
        ps_script = r'''
$sys = Get-CimInstance Win32_ComputerSystem
$auto = $sys.AutomaticManagedPagefile
$settings = @( Get-CimInstance Win32_PageFileSetting | Select-Object Name, InitialSize, MaximumSize )
$usage    = @( Get-CimInstance Win32_PageFileUsage  | Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage )
[pscustomobject]@{
  AutomaticManagedPagefile = $auto
  Settings = $settings
  Usage    = $usage
}
'''.strip()
        data = ps_to_json(ps_script, depth=5)
        if not data:
            raise RuntimeError("PowerShell 查询虚拟内存方案失败（无输出）")
        if data.get("Settings") is None:
            data["Settings"] = []
        if data.get("Usage") is None:
            data["Usage"] = []
        return data

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(14, 14, 14, 14)

        scheme_group = QGroupBox("当前虚拟内存方案")
        scheme_layout = QVBoxLayout()
        scheme_layout.setSpacing(8)

        self.scheme_overview_label = QLabel("管理方式: 正在检测...")
        self.scheme_overview_label.setStyleSheet("font-weight: 600; color: #4A90E2;")
        self.scheme_text = QTextEdit()
        self.scheme_text.setReadOnly(True)
        self.scheme_text.setMinimumHeight(170)
        self.scheme_text.setSizePolicy(SIZE_EXPANDING, SIZE_EXPANDING)

        refresh_btn = QPushButton("刷新当前方案")
        refresh_btn.clicked.connect(self.display_current_scheme)

        scheme_layout.addWidget(self.scheme_overview_label)
        scheme_layout.addWidget(self.scheme_text)
        scheme_layout.addWidget(refresh_btn)
        scheme_group.setLayout(scheme_layout)

        disk_group = QGroupBox("磁盘设置")
        disk_layout = QVBoxLayout()
        disk_layout.setSpacing(8)
        disk_layout.addWidget(QLabel("选择磁盘:"))
        self.disk_combo = QComboBox()
        self._populate_disk_combo()
        disk_layout.addWidget(self.disk_combo)
        disk_group.setLayout(disk_layout)

        mem_group = QGroupBox("虚拟内存设置 (GB)")
        mem_layout = QVBoxLayout()
        mem_layout.setSpacing(8)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("最小内存:"))
        self.min_mem_edit = QLineEdit("64")
        row1.addWidget(self.min_mem_edit)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("最大内存:"))
        self.max_mem_edit = QLineEdit("128")
        row2.addWidget(self.max_mem_edit)
        mem_layout.addLayout(row1)
        mem_layout.addLayout(row2)
        mem_group.setLayout(mem_layout)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("应用虚拟内存设置")
        self.apply_btn.clicked.connect(self.apply_virtual_memory)

        self.perf_btn = QPushButton("优化视觉效果")
        self.perf_btn.clicked.connect(self.optimize_performance)

        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.perf_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)

        layout.addWidget(scheme_group)
        layout.addWidget(disk_group)
        layout.addWidget(mem_group)
        layout.addLayout(btn_row)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

        self.display_current_scheme()

    def _populate_disk_combo(self):
        self.disk_combo.clear()
        disks = []
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts.lower() or not part.device:
                continue
            if part.fstype == "":
                continue
            disks.append(part.device[:2])
        disks = sorted(set(disks), key=lambda x: (x.upper() != "C:", x))
        self.disk_combo.addItems(disks)
        idx = self.disk_combo.findText("D:")
        if idx >= 0:
            self.disk_combo.setCurrentIndex(idx)

    def display_current_scheme(self):
        if getattr(self, "query_worker", None) and self.query_worker.isRunning():
            return
        self.scheme_overview_label.setText("管理方式: 正在检测...")
        self.scheme_text.setPlainText("正在查询当前虚拟内存方案...")
        self.query_worker = WorkerThread(self.query_pagefile_scheme)
        self.query_worker.finished.connect(self._on_query_pagefile_finished)
        self.query_worker.start()

    def _on_query_pagefile_finished(self, result):
        if isinstance(result, Exception):
            self.scheme_overview_label.setText("管理方式: 查询失败")
            self.scheme_text.setPlainText(f"查询当前虚拟内存方案失败：{result}")
            return
        self.render_pagefile_scheme(result)

    def render_pagefile_scheme(self, data: dict):
        auto = data.get("AutomaticManagedPagefile", False)
        settings = data.get("Settings", [])
        usage = data.get("Usage", [])

        overview = "系统自动管理" if auto else "自定义（手动设置）"
        self.scheme_overview_label.setText(f"管理方式: {overview}    （刷新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")

        html_lines = []
        if settings:
            html_lines.append("<b>配置（Win32_PageFileSetting）:</b><br>")
            for s in settings:
                name = s.get("Name", "")
                ini = s.get("InitialSize", 0)
                mx = s.get("MaximumSize", 0)
                html_lines.append(f"&nbsp;&nbsp;• {name}  —  初始: {mb_to_gb(ini):.2f} GB，最大: {mb_to_gb(mx):.2f} GB")
            html_lines.append("<br>")

        if usage:
            html_lines.append("<b>使用情况（Win32_PageFileUsage）:</b><br>")
            for u in usage:
                name = u.get("Name", "")
                alloc = u.get("AllocatedBaseSize", 0)
                cur = u.get("CurrentUsage", 0)
                peak = u.get("PeakUsage", 0)
                html_lines.append(
                    f"&nbsp;&nbsp;• {name}  —  已分配: {mb_to_gb(alloc):.2f} GB，当前: {mb_to_gb(cur):.2f} GB，峰值: {mb_to_gb(peak):.2f} GB"
                )

        if not html_lines:
            html_lines.append("未查询到分页文件配置或使用信息（可能为纯自动管理且当前无使用数据）。")

        self.scheme_text.setHtml("<div style='line-height:1.55;'>" + "<br>".join(html_lines) + "</div>")

    def apply_virtual_memory(self):
        """
        修复：Win32_PageFileSetting 创建时 “属性 InitialSize 的类型不匹配” 导致失败。
        方案：
          1) 使用 WMI 静态方法 Create(Name, [UInt32]InitialSize, [UInt32]MaximumSize)
          2) 若 WMI 方法失败，回退到注册表 PagingFiles（重启后生效）
        """
        disk = self.disk_combo.currentText()[:1]
        min_mem = self.min_mem_edit.text().strip()
        max_mem = self.max_mem_edit.text().strip()

        try:
            min_mb = int(float(min_mem) * 1024)
            max_mb = int(float(max_mem) * 1024)

            if min_mb <= 0 or max_mb <= 0:
                QMessageBox.warning(self, "警告", "内存值必须大于 0")
                return
            if min_mb > max_mb:
                QMessageBox.warning(self, "警告", "最小内存不能大于最大内存")
                return

            reply = QMessageBox.question(
                self, "确认操作",
                f"确定要设置虚拟内存吗？\n磁盘: {disk}:\n最小: {min_mem} GB\n最大: {max_mem} GB\n\n将只修改所选磁盘的分页文件配置，保留其他磁盘现有配置。",
                MSG_YES | MSG_NO,
                MSG_NO
            )
            if reply != MSG_YES:
                return

            # --- 构建健壮的 PowerShell 脚本（WMI 首选 + 注册表兜底） ---
            ps_script = f'''
$ErrorActionPreference = 'Stop'
$drive = '{disk}'
$min = [uint32]{min_mb}
$max = [uint32]{max_mb}
$target = "$drive`:\\pagefile.sys"

function Set-Pagefile-With-WMI {{
  try {{
    # 关闭自动管理（使用 WMI 以启用所需权限）
    $sys = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges
    $sys.AutomaticManagedPagefile = $False
    $null = $sys.Put()

    # 只更新目标分页文件，保留其他磁盘现有配置
    $matches = @(Get-WmiObject Win32_PageFileSetting | Where-Object {{ $_.Name -ieq $target }})
    $existing = if ($matches.Count -gt 0) {{ $matches[0] }} else {{ $null }}
    if ($existing) {{
      $existing.InitialSize = $min
      $existing.MaximumSize = $max
      $null = $existing.Put()
    }} else {{
      $cls = [WMIClass]'Win32_PageFileSetting'
      $rc = $cls.Create($target, $min, $max)
      if ($rc.ReturnValue -ne 0) {{
        throw "WMI Create 返回码: $($rc.ReturnValue)"
      }}
    }}
    return $true
  }} catch {{
    Write-Verbose ("WMI 路径失败：" + $_.Exception.Message)
    return $false
  }}
}}

function Set-Pagefile-Registry-Fallback {{
  try {{
    $mm = 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management'
    if (-not (Test-Path $mm)) {{ New-Item -Path $mm -Force | Out-Null }}

    $currentPaging = @()
    try {{
      $rawPaging = (Get-ItemProperty -Path $mm -Name 'PagingFiles' -ErrorAction Stop).PagingFiles
      if ($rawPaging) {{ $currentPaging = @($rawPaging) }}
    }} catch {{}}

    $pagingEntries = @()
    foreach ($item in $currentPaging) {{
      $text = [string]$item
      if ([string]::IsNullOrWhiteSpace($text)) {{ continue }}
      $path = ($text -split '\\s+')[0]
      if ($path -ieq $target) {{ continue }}
      $pagingEntries += $text
    }}
    $pagingEntries += "$target $min $max"
    Set-ItemProperty -Path $mm -Name 'PagingFiles' -Type MultiString -Value $pagingEntries

    $currentExisting = @()
    try {{
      $rawExisting = (Get-ItemProperty -Path $mm -Name 'ExistingPageFiles' -ErrorAction Stop).ExistingPageFiles
      if ($rawExisting) {{ $currentExisting = @($rawExisting) }}
    }} catch {{}}

    $existingEntries = @()
    foreach ($item in $currentExisting) {{
      $text = [string]$item
      if ([string]::IsNullOrWhiteSpace($text)) {{ continue }}
      if ($text -ieq $target) {{ continue }}
      $existingEntries += $text
    }}
    $existingEntries += $target
    Set-ItemProperty -Path $mm -Name 'ExistingPageFiles' -Type MultiString -Value $existingEntries

    Set-ItemProperty -Path $mm -Name 'TempPageFile' -Type DWord -Value 0
    Set-ItemProperty -Path $mm -Name 'AutomaticManagedPagefile' -Type DWord -Value 0
    return $true
  }} catch {{
    Write-Verbose ("注册表兜底失败：" + $_.Exception.Message)
    return $false
  }}
}}

$ok = Set-Pagefile-With-WMI
if (-not $ok) {{
  $ok = Set-Pagefile-Registry-Fallback
}}
if (-not $ok) {{
  throw "设置虚拟内存失败（WMI 与注册表均失败）"
}}
'''.strip()

            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(30)

            self.worker = WorkerThread(run_as_admin, ["powershell", "-NoProfile", "-Command", ps_script])
            self.worker.finished.connect(self._on_set_vm_finished)
            self.worker.start()

        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的数字")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"设置虚拟内存失败: {e}")
            self.progress_bar.setVisible(False)

    def _on_set_vm_finished(self, result):
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        if result is True:
            QMessageBox.information(self, "成功", "虚拟内存设置已更新（部分系统需重启后完全生效）")
            self.display_current_scheme()
        elif result is None:
            QMessageBox.information(self, "需要管理员权限", "已打开管理员权限的新窗口，请在新窗口中重新执行该操作。")
        elif result is False:
            QMessageBox.warning(self, "警告", "设置虚拟内存失败，请确认已允许管理员权限并检查系统日志。")
        elif isinstance(result, Exception):
            QMessageBox.critical(self, "错误", f"设置虚拟内存失败: {result}")

    def optimize_performance(self):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
            ok = set_registry_value(winreg.HKEY_CURRENT_USER, reg_path, "VisualFXSetting", winreg.REG_DWORD, 2)
            if ok:
                QMessageBox.information(self, "成功", "视觉效果已设置为最佳性能！建议重启电脑以确保设置生效。")
            else:
                QMessageBox.warning(self, "警告", "优化性能失败，请检查权限")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"优化性能失败: {e}")


# ----------------------------
# 功能页：系统信息（含 IP、显卡过滤）
# ----------------------------
class SystemInfoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(14, 14, 14, 14)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("font-family: 'Microsoft YaHei', 'Segoe UI', 'Consolas'; font-size: 14px;")

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新信息")
        self.refresh_btn.clicked.connect(self.display_system_info)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addItem(QSpacerItem(10, 10, SIZE_EXPANDING, SIZE_MINIMUM))

        layout.addWidget(self.info_text)
        layout.addLayout(btn_row)
        self.setLayout(layout)
        self.display_system_info()

    def get_os_info(self) -> str:
        ps = r'''
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, OSArchitecture
$cv = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion"
[pscustomobject]@{
  Caption=$os.Caption
  Arch=$os.OSArchitecture
  DisplayVersion=$cv.DisplayVersion
  EditionID=$cv.EditionID
}
'''
        data = ps_to_json(ps)
        caption = ""
        arch = ""
        disp = ""
        edition = ""
        if isinstance(data, dict):
            caption = str(data.get("Caption") or "")
            arch = str(data.get("Arch") or "")
            disp = str(data.get("DisplayVersion") or "")
            edition = str(data.get("EditionID") or "")
        if not caption:
            caption = f"{platform.system()} {platform.release()}"
        name = caption.replace("Microsoft ", "").strip()
        if "Windows 11" in name:
            name = name.replace("Windows 11", "Win11")
        elif "Windows 10" in name:
            name = name.replace("Windows 10", "Win10")
        ed_map = {
            "Professional": "Pro", "Enterprise": "Enterprise", "Education": "Education",
            "Core": "Home", "CoreSingleLanguage": "Home SL", "ProfessionalWorkstation": "Pro WS",
            "ProfessionalEducation": "Pro Edu"
        }
        ed = ed_map.get(edition, edition or "")
        if ed and ed not in name:
            name = f"{name} {ed}"
        if disp:
            name = f"{name} {disp}"
        arch_cn = "64位" if ("64" in arch or sys.maxsize > 2**32) else "32位"
        return f"{name} {arch_cn}".strip()

    def get_cpu_info(self) -> str:
        ps = r"Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores"
        data = ps_to_json(ps)
        if isinstance(data, list) and data:
            cpu = data[0]
        elif isinstance(data, dict):
            cpu = data
        else:
            cpu = {}
        name_raw = (cpu.get("Name") or platform.processor() or "").strip()
        cores = safe_int(cpu.get("NumberOfCores"), psutil.cpu_count(logical=False) or 0)

        brand = "英特尔" if ("Intel" in name_raw or "Core" in name_raw) else ("AMD" if ("AMD" in name_raw or "Ryzen" in name_raw) else "")
        m = re.search(r'(\d+)(?:st|nd|rd|th)\s+Gen.*?\b(Core).*?\b([iI]\d[- ][0-9A-Za-z]+)', name_raw)
        if m:
            num = safe_int(m.group(1), 0)
            zh_map = {10: "第十", 11: "第十一", 12: "第十二", 13: "第十三", 14: "第十四"}
            gen_cn = zh_map.get(num, f"第{num}代")
            model = m.group(3).replace(" ", "")
            series_cn = "酷睿"
            cpu_name = f"{brand} {gen_cn}{series_cn} {model}".strip()
        else:
            m2 = re.search(r'(Core).*?\b([iI]\d[- ][0-9A-Za-z]+)', name_raw)
            if m2:
                model = m2.group(2).replace(" ", "")
                cpu_name = f"{brand} 酷睿 {model}".strip()
            else:
                cpu_name = f"{brand} {name_raw}".strip()
        cn_map = {2: "双", 4: "四", 6: "六", 8: "八", 10: "十", 12: "十二", 16: "十六"}
        core_cn = f"{cn_map.get(cores, str(cores))}核" if cores else ""
        return (cpu_name + (f" {core_cn}" if core_cn else "")).strip()

    def get_mainboard_info(self) -> str:
        ps = r'''
$bb = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product, Version
[pscustomobject]@{ Manufacturer=$bb.Manufacturer; Product=$bb.Product; Version=$bb.Version }
'''
        data = ps_to_json(ps)
        if not isinstance(data, dict):
            return "主板信息获取失败"
        manu = (data.get("Manufacturer") or "").strip()
        prod = (data.get("Product") or "").strip()
        ver = (data.get("Version") or "").strip()

        manu_cn = (manu
                   .replace("Micro-Star International Co., Ltd.", "微星")
                   .replace("Micro-Star International", "微星")
                   .replace("ASUSTeK COMPUTER INC.", "华硕")
                   .replace("ASUSTeK COMPUTER", "华硕")
                   .replace("Gigabyte Technology Co., Ltd.", "技嘉")
                   .replace("GIGABYTE", "技嘉")
                   .replace("ASRock", "华擎")
                   .replace("Dell Inc.", "戴尔"))
        board_code = ""
        m_code = re.search(r'\((MS-\w+)\)', prod)
        if m_code:
            board_code = m_code.group(1)
        elif ver and ver.upper().startswith("MS-"):
            board_code = ver

        m_chip = re.search(r'\b([HZBQM]\d{3}|X\d{3})\b', prod.upper())
        chip = m_chip.group(1) if m_chip else ""
        chip_brand = "英特尔" if chip and chip[0] in "HBQZ" else ("AMD" if chip and chip[0] in "MX" else "")
        chip_text = f"（{chip_brand}{chip}芯片组）" if chip else ""

        text = f"{manu_cn} {prod}".strip()
        if board_code:
            text += f"（{board_code}）"
        if chip_text:
            text += f" {chip_text}"
        return text

    def get_memory_info(self) -> str:
        ps = r'''
$mems = Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, SMBIOSMemoryType
$mems
'''
        data = ps_to_json(ps)
        if not data:
            vm = psutil.virtual_memory()
            return f"{vm.total / (1024**3):.0f}GB"
        modules = data if isinstance(data, list) else [data]
        sizes = []
        total = 0
        speeds = []
        ddr_type = None
        ddr_map = {24: "DDR3", 26: "DDR4", 27: "LPDDR4", 34: "DDR5", 35: "LPDDR5", 0: ""}
        for m in modules:
            cap = safe_int(m.get("Capacity"), 0)
            spd = safe_int(m.get("Speed"), 0)
            smt = m.get("SMBIOSMemoryType")
            if cap > 0:
                total += cap
                sizes.append(f"{bytes_to_gb(cap):.0f}GB")
            if spd > 0:
                speeds.append(spd)
            if isinstance(smt, int) and smt in ddr_map and not ddr_type:
                ddr_type = ddr_map[smt] or None
        total_str = f"{bytes_to_gb(total):.0f}GB" if total else ""
        speed_str = f"{min(speeds)}MHz" if speeds else ""
        if not ddr_type and speeds:
            s = min(speeds)
            if s <= 2133:
                ddr_type = "DDR3"
            elif s <= 4266:
                ddr_type = "DDR4"
            else:
                ddr_type = "DDR5"
        combo = " + ".join(sizes) if sizes else ""
        out = total_str
        if ddr_type:
            out += f" {ddr_type}"
        if speed_str:
            out += f" {speed_str}"
        if combo:
            out += f" （{combo}）"
        return out.strip()

    def get_gpu_info(self) -> str:
        ps = r"Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, PNPDeviceID"
        data = ps_to_json(ps)
        if not data:
            return "显卡信息获取失败"
        raw = data if isinstance(data, list) else [data]

        def is_vendor_match(name: str, pnp: str) -> Optional[str]:
            low = (name or "").lower()
            p = (pnp or "").upper()
            if "nvidia" in low or "VEN_10DE" in p:
                return "NVIDIA"
            if "amd" in low or "radeon" in low or "VEN_1002" in p:
                return "AMD"
            return None

        def is_virtual_adapter(name: str) -> bool:
            low = (name or "").lower()
            virtual_keywords = [
                "basic render", "microsoft basic", "idd", "remotedisplay", "remote", "rdp",
                "vmware", "virtual", "parallels", "qxl", "xen", "displaylink", "asklinkidddriver"
            ]
            return any(k in low for k in virtual_keywords)

        gpus = []
        for g in raw:
            name = (g.get("Name") or "").strip()
            pnp = g.get("PNPDeviceID") or ""
            brand = is_vendor_match(name, pnp)
            if not brand:
                continue
            if is_virtual_adapter(name):
                continue
            ram_b = safe_int(g.get("AdapterRAM"), 0)
            vram_gb = bytes_to_gb(ram_b)
            vram_str = f"{vram_gb:.0f}GB" if vram_gb > 0.1 else ""

            partner = ""
            m = re.search(r"SUBSYS_([0-9A-Fa-f]{8})", pnp)
            if m:
                ven = m.group(1)[4:8].upper()
                vendor_map = {
                    "1043": "华硕", "1462": "微星", "1458": "技嘉", "3842": "EVGA", "19DA": "索泰",
                    "196E": "映众", "1ACC": "七彩虹", "1042": "华擎", "10B0": "耕升", "1B4C": "影驰/Palit", "1569": "影驰"
                }
                partner = vendor_map.get(ven, "")

            display_name = name
            if brand == "NVIDIA" and not name.lower().startswith("nvidia"):
                display_name = f"NVIDIA {name}"
            if brand == "AMD" and not (name.lower().startswith("amd") or "radeon" in name.lower()):
                display_name = f"AMD {name}"

            suffix = ""
            if vram_str and partner:
                suffix = f"（{vram_str} /{partner}）"
            elif vram_str:
                suffix = f"（{vram_str}）"
            elif partner:
                suffix = f"（/{partner}）"

            gpus.append(display_name + suffix)

        if not gpus:
            return "未发现 NVIDIA/AMD 显卡（可能当前会话启用了远程/虚拟显示适配器）"
        return "；".join(gpus)

    def get_disk_info(self) -> str:
        ps = r"Get-CimInstance Win32_DiskDrive | Select-Object Index, Model, Size | Sort-Object Index"
        data = ps_to_json(ps)
        if not data:
            return "磁盘信息获取失败"
        disks = data if isinstance(data, list) else [data]
        d0 = disks[0]
        model = (d0.get("Model") or "").strip()
        size_b = safe_int(d0.get("Size"), 0)
        size_gb = bytes_to_gb(size_b)
        sz = f"{size_gb:.0f}GB" if size_gb > 0 else ""
        return f"{model}（{sz}）" if model and sz else (model or "磁盘")

    def get_local_ip_info(self) -> str:
        try:
            hostname = socket.gethostname()
            ips = []
            for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ipaddr = item[4][0]
                if ipaddr.startswith("127.") or ipaddr.startswith("169.254."):
                    continue
                if ipaddr not in ips:
                    ips.append(ipaddr)
            if ips:
                return " / ".join(ips)
        except Exception as e:
            logging.warning(f"本机 IP 获取失败: {e}")

        try:
            hostname = socket.gethostname()
            ipaddr = socket.gethostbyname(hostname)
            return ipaddr
        except Exception:
            return "获取失败"

    def collect_system_info(self) -> str:
        os_line = f"系统信息：{self.get_os_info()}"
        cpu_line = f"处理器：{self.get_cpu_info()}"
        mb_line = f"主板：{self.get_mainboard_info()}"
        mem_line = f"内存：{self.get_memory_info()}"
        gpu_line = f"显卡：{self.get_gpu_info()}"
        disk_line = f"磁盘：{self.get_disk_info()}"
        ip_line = f"本机 IP：{self.get_local_ip_info()}"

        lines = [os_line, cpu_line, mb_line, mem_line, gpu_line, disk_line, ip_line]
        return "<br>".join(lines)

    def display_system_info(self):
        if getattr(self, "worker", None) and self.worker.isRunning():
            return
        self.refresh_btn.setEnabled(False)
        self.info_text.setPlainText("正在获取系统信息...")
        self.worker = WorkerThread(self.collect_system_info)
        self.worker.finished.connect(self._on_system_info_finished)
        self.worker.start()

    def _on_system_info_finished(self, result):
        self.refresh_btn.setEnabled(True)
        if isinstance(result, Exception):
            QMessageBox.critical(self, "错误", f"获取系统信息失败: {result}")
            self.info_text.setPlainText(f"获取系统信息失败：{result}")
            return
        self.info_text.setHtml(f"<div style='line-height:1.6;'>{result}</div>")


# ----------------------------
# 功能页：安全警告
# ----------------------------
class SecurityWarnTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(14, 14, 14, 14)

        reg_group = QGroupBox("通过注册表禁用安全警告")
        reg_layout = QVBoxLayout()
        reg_layout.setSpacing(8)
        reg_label = QLabel("修改注册表，禁用“无法验证发布者”的安全警告。")
        reg_label.setWordWrap(True)
        self.disable_reg_btn = QPushButton("禁用安全警告（注册表方式）")
        self.disable_reg_btn.clicked.connect(self.disable_security_warning)
        self.restore_reg_btn = QPushButton("恢复安全警告（注册表方式）")
        self.restore_reg_btn.clicked.connect(self.restore_security_warning)
        reg_layout.addWidget(reg_label)
        reg_layout.addWidget(self.disable_reg_btn)
        reg_layout.addWidget(self.restore_reg_btn)
        reg_group.setLayout(reg_layout)

        ie_group = QGroupBox("通过 Internet 选项禁用安全警告")
        ie_layout = QVBoxLayout()
        ie_layout.setSpacing(8)
        ie_label = QLabel("将 Internet 安全项 “加载应用程序和不安全文件” 设置为启用（可能降低安全性）。")
        ie_label.setWordWrap(True)
        self.disable_ie_btn = QPushButton("禁用安全警告（Internet 选项）")
        self.disable_ie_btn.clicked.connect(self.disable_ie_security_warning)
        self.restore_ie_btn = QPushButton("恢复安全警告（Internet 选项）")
        self.restore_ie_btn.clicked.connect(self.restore_ie_security_warning)
        ie_layout.addWidget(ie_label)
        ie_layout.addWidget(self.disable_ie_btn)
        ie_layout.addWidget(self.restore_ie_btn)
        ie_group.setLayout(ie_layout)

        layout.addWidget(reg_group)
        layout.addWidget(ie_group)
        self.setLayout(layout)

    def disable_security_warning(self):
        reply = QMessageBox.question(
            self, "确认降低安全提示",
            "这会把 .exe、.bat、.cmd、.vbs 加入低风险文件类型，可能降低 Windows 对下载文件和脚本的保护。\n\n确定继续吗？",
            MSG_YES | MSG_NO,
            MSG_NO
        )
        if reply != MSG_YES:
            return
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\Associations"
            if set_registry_value(winreg.HKEY_CURRENT_USER, reg_path, "LowRiskFileTypes", winreg.REG_SZ, ".exe;.bat;.cmd;.vbs"):
                QMessageBox.information(self, "成功", "已通过注册表禁用安全警告！建议重启电脑。")
            else:
                QMessageBox.warning(self, "警告", "操作失败，请检查权限")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"禁用安全警告失败: {e}")

    def restore_security_warning(self):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\Associations"
            if delete_registry_value(winreg.HKEY_CURRENT_USER, reg_path, "LowRiskFileTypes"):
                QMessageBox.information(self, "成功", "已恢复注册表方式的安全警告设置。")
            else:
                QMessageBox.warning(self, "警告", "恢复失败，请检查权限")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"恢复安全警告失败: {e}")

    def disable_ie_security_warning(self):
        reply = QMessageBox.question(
            self, "确认降低 Internet 安全级别",
            "这会启用 Internet 区域的“加载应用程序和不安全文件”选项，可能降低系统安全性。\n\n确定继续吗？",
            MSG_YES | MSG_NO,
            MSG_NO
        )
        if reply != MSG_YES:
            return
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3"
            if set_registry_value(winreg.HKEY_CURRENT_USER, reg_path, "1001", winreg.REG_DWORD, 0):
                QMessageBox.information(self, "成功", "已通过 Internet 选项禁用安全警告！可能需重启浏览器。")
            else:
                QMessageBox.warning(self, "警告", "操作失败，请检查权限")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改 Internet 选项失败: {e}")

    def restore_ie_security_warning(self):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3"
            if set_registry_value(winreg.HKEY_CURRENT_USER, reg_path, "1001", winreg.REG_DWORD, 3):
                QMessageBox.information(self, "成功", "已恢复 Internet 区域的不安全文件加载保护。")
            else:
                QMessageBox.warning(self, "警告", "恢复失败，请检查权限")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"恢复 Internet 选项失败: {e}")


# ----------------------------
# 功能页：电源选项
# ----------------------------
class PowerPlanTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.update_power_plan_status()
        self.update_hibernate_status()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(14, 14, 14, 14)

        plan_group = QGroupBox("电源计划设置")
        plan_layout = QVBoxLayout()
        plan_layout.setSpacing(8)

        info_label = QLabel("添加并启用 “卓越性能 (Ultimate Performance)” 电源计划")
        self.current_plan_label = QLabel("当前电源计划: 正在检测...")
        self.current_plan_label.setStyleSheet("font-weight: 600; color: #4A90E2;")

        self.refresh_power_btn = QPushButton("刷新电源计划状态")
        self.refresh_power_btn.clicked.connect(self.update_power_plan_status)

        self.add_power_btn = QPushButton("启用卓越性能")
        self.add_power_btn.setToolTip("添加并启用卓越性能电源计划")
        self.add_power_btn.clicked.connect(self.enable_ultimate_performance)

        plan_layout.addWidget(info_label)
        plan_layout.addWidget(self.current_plan_label)
        plan_layout.addWidget(self.refresh_power_btn)
        plan_layout.addWidget(self.add_power_btn)
        plan_group.setLayout(plan_layout)

        hibernate_group = QGroupBox("休眠设置")
        hibernate_layout = QVBoxLayout()
        hibernate_layout.setSpacing(8)

        self.hibernate_status_label = QLabel("休眠状态: 正在检测...")
        self.hibernate_status_label.setStyleSheet("font-weight: 600;")

        self.disable_hibernate_btn = QPushButton("关闭系统休眠")
        self.disable_hibernate_btn.setToolTip("关闭休眠功能以释放硬盘空间")
        self.disable_hibernate_btn.clicked.connect(self.disable_hibernate)

        self.enable_hibernate_btn = QPushButton("启用系统休眠")
        self.enable_hibernate_btn.setToolTip("启用系统休眠功能")
        self.enable_hibernate_btn.clicked.connect(self.enable_hibernate)

        hibernate_layout.addWidget(self.hibernate_status_label)
        hibernate_layout.addWidget(self.disable_hibernate_btn)
        hibernate_layout.addWidget(self.enable_hibernate_btn)
        hibernate_group.setLayout(hibernate_layout)

        layout.addWidget(plan_group)
        layout.addWidget(hibernate_group)
        self.setLayout(layout)

    def update_power_plan_status(self):
        try:
            result = run_command(["powercfg", "/getactivescheme"])
            if result:
                m = re.search(r"\((.*?)\)", result)
                if m:
                    self.current_plan_label.setText(f"当前电源计划: {m.group(1)}")
                else:
                    self.current_plan_label.setText("当前电源计划: 未知")
            else:
                self.current_plan_label.setText("获取电源计划失败")
        except Exception as e:
            self.current_plan_label.setText(f"错误: {e}")

    def update_hibernate_status(self):
        try:
            result = run_command(["powercfg", "/a"])
            if result:
                if ("Hibernation has been enabled" in result) or ("休眠已启用" in result):
                    self.hibernate_status_label.setText("休眠状态: 已启用")
                    self.hibernate_status_label.setStyleSheet("color: #5CB85C; font-weight: 600;")
                elif ("Hibernation has not been enabled" in result) or ("休眠未启用" in result):
                    self.hibernate_status_label.setText("休眠状态: 已禁用")
                    self.hibernate_status_label.setStyleSheet("color: #D9534F; font-weight: 600;")
                else:
                    if os.path.exists(r"C:\hiberfil.sys"):
                        self.hibernate_status_label.setText("休眠状态: 已启用")
                        self.hibernate_status_label.setStyleSheet("color: #5CB85C; font-weight: 600;")
                    else:
                        self.hibernate_status_label.setText("休眠状态: 已禁用")
                        self.hibernate_status_label.setStyleSheet("color: #D9534F; font-weight: 600;")
            else:
                self.hibernate_status_label.setText("休眠状态: 检测失败")
        except Exception as e:
            self.hibernate_status_label.setText(f"休眠状态: 检测失败 - {e}")
            self.hibernate_status_label.setStyleSheet("color: #D9534F; font-weight: 600;")

    def disable_hibernate(self):
        reply = QMessageBox.question(
            self, "确认操作",
            "确定要关闭系统休眠吗？这可释放硬盘空间但会禁用休眠功能。",
            MSG_YES | MSG_NO,
            MSG_NO
        )
        if reply != MSG_YES:
            return
        try:
            result = run_as_admin(["powercfg", "/hibernate", "off"])
            if result is True:
                QMessageBox.information(self, "成功", "系统休眠已关闭！")
                self.update_hibernate_status()
            elif result is None:
                QMessageBox.information(self, "需要管理员权限", "已打开管理员权限的新窗口，请在新窗口中重新执行该操作。")
            else:
                QMessageBox.warning(self, "警告", "关闭休眠失败，请确认已允许管理员权限。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"关闭休眠失败: {e}")

    def enable_hibernate(self):
        try:
            result = run_as_admin(["powercfg", "/hibernate", "on"])
            if result is True:
                QMessageBox.information(self, "成功", "系统休眠已启用！")
                self.update_hibernate_status()
            elif result is None:
                QMessageBox.information(self, "需要管理员权限", "已打开管理员权限的新窗口，请在新窗口中重新执行该操作。")
            else:
                QMessageBox.warning(self, "警告", "启用休眠失败，请确认已允许管理员权限。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启用休眠失败: {e}")

    def parse_power_schemes(self, text: str) -> List[tuple]:
        guid_pat = r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
        schemes = []
        for line in (text or "").splitlines():
            m = re.search(guid_pat, line)
            if not m:
                continue
            name_match = re.search(r"\((.*?)\)", line)
            name = name_match.group(1).strip() if name_match else ""
            schemes.append((m.group(1), name, line.strip()))
        return schemes

    def find_ultimate_scheme(self, text: str) -> Optional[str]:
        target_guid = "e9a42b02-d5df-448d-aa00-03f14749eb61"
        for guid, name, line in self.parse_power_schemes(text):
            haystack = f"{name} {line}"
            if guid.lower() == target_guid or "卓越性能" in haystack or "Ultimate Performance" in haystack:
                return guid
        return None

    def set_active_power_scheme(self, guid: str) -> bool:
        result = run_command_result(["powercfg", "/setactive", guid])
        if not result.ok:
            QMessageBox.warning(self, "警告", f"启用电源计划失败：{result.stderr or result.stdout or result.returncode}")
            return False
        return True

    def enable_ultimate_performance(self):
        reply = QMessageBox.question(
            self, "确认操作",
            "确定要启用卓越性能电源计划吗？这可能会增加功耗但提升系统性能。",
            MSG_YES | MSG_NO,
            MSG_NO
        )
        if reply != MSG_YES:
            return

        try:
            result = run_command(["powercfg", "/L"])
            if not result:
                QMessageBox.warning(self, "警告", "无法获取电源计划列表")
                return

            target_guid = "e9a42b02-d5df-448d-aa00-03f14749eb61"

            guid = self.find_ultimate_scheme(result)
            if guid:
                if not self.set_active_power_scheme(guid):
                    return
                QMessageBox.information(self, "成功", "已启用卓越性能电源计划！")
                self.update_power_plan_status()
                return

            duplicate = run_command_result(["powercfg", "/duplicatescheme", target_guid])
            if not duplicate.ok:
                QMessageBox.warning(self, "警告", f"添加卓越性能电源计划失败：{duplicate.stderr or duplicate.stdout or duplicate.returncode}")
                return

            guid_pat = r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
            new_guid_match = re.search(guid_pat, duplicate.stdout)
            if new_guid_match:
                new_guid = new_guid_match.group(1)
                if not self.set_active_power_scheme(new_guid):
                    return
                QMessageBox.information(self, "成功", "已启用卓越性能电源计划！")
                self.update_power_plan_status()
                return

            result2 = run_command(["powercfg", "/L"]) or ""
            new_guid = self.find_ultimate_scheme(result2)
            if not new_guid:
                QMessageBox.warning(self, "警告", "已尝试添加卓越性能电源计划，但未能在电源计划列表中确认。")
                return

            if not self.set_active_power_scheme(new_guid):
                return
            QMessageBox.information(self, "成功", "已添加并启用卓越性能电源计划！")
            self.update_power_plan_status()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"启用卓越性能失败: {e}")


# ----------------------------
# 功能页：系统设置
# ----------------------------
class SystemSettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(14, 14, 14, 14)

        computer_name_group = QGroupBox("修改计算机名")
        name_layout = QVBoxLayout()
        name_layout.setSpacing(8)

        self.computer_name_edit = QLineEdit()
        self.computer_name_edit.setPlaceholderText("输入新计算机名（字母/数字/连字符）")

        name_layout.addWidget(QLabel("新计算机名:"))
        name_layout.addWidget(self.computer_name_edit)

        self.change_name_btn = QPushButton("修改计算机名")
        self.change_name_btn.setToolTip("需要管理员权限，重启后生效")
        self.change_name_btn.clicked.connect(self.change_computer_name)

        name_layout.addWidget(self.change_name_btn)
        computer_name_group.setLayout(name_layout)

        taskbar_group = QGroupBox("任务栏设置")
        taskbar_layout = QVBoxLayout()
        taskbar_layout.setSpacing(8)

        self.small_taskbar_btn = QPushButton("启用小任务栏按钮")
        self.small_taskbar_btn.clicked.connect(lambda: self.set_taskbar_setting("TaskbarSmallIcons", 1))
        self.small_taskbar_btn.setToolTip("设置任务栏使用小图标")

        self.taskbar_combine_btn = QPushButton("任务栏按钮从不合并")
        self.taskbar_combine_btn.clicked.connect(lambda: self.set_taskbar_setting("TaskbarGlomLevel", 2))
        self.taskbar_combine_btn.setToolTip("设置任务栏按钮从不合并")

        self.default_combine_btn = QPushButton("恢复默认合并方式")
        self.default_combine_btn.clicked.connect(lambda: self.set_taskbar_setting("TaskbarGlomLevel", 1))
        self.default_combine_btn.setToolTip("恢复任务栏按钮默认合并方式")

        taskbar_layout.addWidget(self.small_taskbar_btn)
        taskbar_layout.addWidget(self.taskbar_combine_btn)
        taskbar_layout.addWidget(self.default_combine_btn)
        taskbar_group.setLayout(taskbar_layout)

        layout.addWidget(computer_name_group)
        layout.addWidget(taskbar_group)
        self.setLayout(layout)

    def change_computer_name(self):
        new_name = self.computer_name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "警告", "请输入计算机名")
            return
        if not re.match(r"^[a-zA-Z0-9\-]+$", new_name):
            QMessageBox.warning(self, "警告", "计算机名只能包含字母、数字和连字符(-)")
            return

        reply = QMessageBox.question(
            self, "确认操作",
            f"确定将计算机名修改为 “{new_name}” 吗？（重启后生效）",
            MSG_YES | MSG_NO,
            MSG_NO
        )
        if reply != MSG_YES:
            return

        try:
            ps_script = f'Rename-Computer -NewName "{new_name}" -Force'
            result = run_as_admin(["powershell", "-NoProfile", "-Command", ps_script])
            if result is True:
                QMessageBox.information(self, "成功", f"计算机名已修改为 {new_name}，请重启。")
            elif result is None:
                QMessageBox.information(self, "需要管理员权限", "已打开管理员权限的新窗口，请在新窗口中重新执行该操作。")
            else:
                QMessageBox.warning(self, "警告", "修改计算机名失败，请确认已允许管理员权限。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改计算机名失败: {e}")

    def set_taskbar_setting(self, key: str, value: int):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
            if set_registry_value(winreg.HKEY_CURRENT_USER, reg_path, key, winreg.REG_DWORD, value):
                subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.Popen("explorer.exe", creationflags=subprocess.CREATE_NO_WINDOW)
                QMessageBox.information(self, "成功", "任务栏设置已应用！")
            else:
                QMessageBox.warning(self, "警告", "操作失败，请检查权限")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"修改任务栏设置失败: {e}")


# ----------------------------
# 主窗口（左侧列表导航）
# ----------------------------
class SystemOptimizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = AppConfig()
        self.setWindowTitle(f"{self.config.APP_NAME} v{self.config.VERSION}")

        icon_path = resource_path(self.config.ICON_PATH)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            logging.warning(f"图标文件未找到: {icon_path}")

        self.resize(1000, 700)
        self.setStyleSheet(self.config.STYLE_SHEET)

        root = QWidget()
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self.nav = QListWidget()
        self.nav.setFixedWidth(180)
        for name in ("虚拟内存", "系统信息", "安全警告", "电源选项", "系统设置"):
            self.nav.addItem(QListWidgetItem(name))
        self.nav.setCurrentRow(0)

        self.pages = QStackedWidget()
        self.tab_virtual_mem = VirtualMemoryTab()
        self.tab_system_info = SystemInfoTab()
        self.tab_security_warn = SecurityWarnTab()
        self.tab_power_plan = PowerPlanTab()
        self.tab_system_settings = SystemSettingsTab()

        self.pages.addWidget(self.tab_virtual_mem)
        self.pages.addWidget(self.tab_system_info)
        self.pages.addWidget(self.tab_security_warn)
        self.pages.addWidget(self.tab_power_plan)
        self.pages.addWidget(self.tab_system_settings)

        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)

        root_layout.addWidget(self.nav)
        root_layout.addWidget(self.pages)
        root.setLayout(root_layout)
        self.setCentralWidget(root)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(f"{self.config.APP_NAME} v{self.config.VERSION} | {QT_API} | © {self.config.COMPANY}")

        admin_status = "管理员模式" if is_admin() else "普通用户模式"
        admin_label = QLabel(f"权限: {admin_status}")
        admin_label.setStyleSheet("color: #5CB85C;" if is_admin() else "color: #D9534F;")
        self.status_bar.addPermanentWidget(admin_label)

        separator = QFrame()
        separator.setFrameShape(FRAME_VLINE)
        separator.setFrameShadow(FRAME_SUNKEN)
        self.status_bar.addPermanentWidget(separator)

        restart_label = QLabel("部分设置需重启生效")
        restart_label.setStyleSheet("color: #F0AD4E; font-weight: 700;")
        self.status_bar.addPermanentWidget(restart_label)


# ----------------------------
# 入口
# ----------------------------
if __name__ == "__main__":
    logging.basicConfig(
        filename="system_optimizer.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )
    logging.info("应用程序启动（PyQt6）")

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = SystemOptimizer()
    window.show()
    exec_func = app.exec if hasattr(app, "exec") else app.exec_
    sys.exit(exec_func())
