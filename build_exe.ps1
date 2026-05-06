# 用途：将当前 PyQt6 桌面程序打包为单文件 Windows exe。
# 输出：dist\winTool.exe
# 说明：build/、dist/ 和 winTool.spec 是本地打包产物，不应提交到 Git。
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name winTool --icon "app.ico" --add-data "app.ico;." "main.py"
