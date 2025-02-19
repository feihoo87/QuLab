import subprocess
import sys


def run_detached_with_terminal(executable_path):
    """
    启动可执行文件并在新终端窗口中保持运行，Python退出后进程仍存在。
    适用于Windows、Linux和macOS。
    """
    try:
        if sys.platform == 'win32':
            # Windows：使用start命令启动新cmd窗口
            cmd = f'start cmd /k "{executable_path}"'
            subprocess.Popen(cmd, shell=True)
        elif sys.platform == 'darwin':
            # macOS：通过AppleScript在Terminal中执行命令
            escaped_path = executable_path.replace('"', r'\"')
            script = f'tell application "Terminal" to do script "{escaped_path}"'
            subprocess.Popen(['osascript', '-e', script],
                             start_new_session=True)
        else:
            # Linux：尝试gnome-terminal或xterm
            try:
                subprocess.Popen(['gnome-terminal', '--', executable_path],
                                 start_new_session=True)
            except FileNotFoundError:
                subprocess.Popen(['xterm', '-e', executable_path],
                                 start_new_session=True)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)
