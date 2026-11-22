@echo off
chcp 65001 >nul
echo 正在注册计划任务「ModelScope魔粒每日互动」（每天 09:30 运行）...
schtasks /Create /F /TN "ModelScope魔粒每日互动" /SC DAILY /ST 09:30 /TR "\"%~dp0run_daily.bat\""
if %errorlevel%==0 (
  echo.
  echo 注册成功！每天 09:30 将自动运行一次脚本。
  echo 想改时间：编辑本文件里的 09:30 后重新双击运行即可（会自动覆盖）。
) else (
  echo.
  echo 自动注册失败，请改用图形界面：
  echo   1. 开始菜单搜索“任务计划程序”并打开
  echo   2. 创建基本任务 → 名称随意（如 ModelScope魔粒）→ 每天 → 设个时间
  echo   3. 操作选“启动程序”，程序/脚本填：%~dp0run_daily.bat
  echo   4. 如果你的 python 不在 PATH 里，请先编辑 run_daily.bat，
  echo      把 python 换成 python.exe 的完整路径（如 C:\Python313\python.exe）
)
echo.
pause
