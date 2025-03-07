import shlex
import subprocess
import sys
import time

import click


def run_detached(executable_path):
    """
    启动可执行文件并完全分离（优先用 tmux/screen），无需额外终端窗口
    支持 Windows、Linux 和 macOS
    """
    try:
        if sys.platform == 'win32' or not _unix_detach_with_tmux_or_screen(
                executable_path):
            # 回退到带终端窗口的方案
            run_detached_with_terminal(executable_path)

    except Exception as e:
        click.echo(f"启动失败: {e}")
        sys.exit(1)


def _windows_start(executable_path):
    """Windows 弹窗启动方案"""
    subprocess.Popen(f'start cmd /k "{executable_path}"',
                     shell=True,
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def _unix_detach_with_tmux_or_screen(executable_path):
    """Unix 后台分离方案（无窗口）"""
    safe_path = shlex.quote(executable_path)
    session_name = f"qulab_{int(time.time())}"

    # 尝试 tmux
    if _check_command_exists("tmux"):
        command = [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session_name,
            safe_path + " ; tmux wait-for -S finished",  # 等待命令结束
            ";",
            "tmux",
            "wait-for",
            "finished"  # 防止进程立即退出
        ]
        subprocess.Popen(" ".join(command), shell=True, start_new_session=True)
        click.echo(f"已启动 tmux 会话: {session_name}")
        click.echo(f"你可以使用 `tmux attach -t {session_name}` 来查看输出")
        return True

    # 尝试 screen
    elif _check_command_exists("screen"):
        command = ["screen", "-dmS", session_name, safe_path]
        subprocess.Popen(command, start_new_session=True)
        click.echo(f"已启动 screen 会话: {session_name}")
        click.echo(f"你可以使用 `screen -r {session_name}` 来查看输出")
        return True

    return False


def run_detached_with_terminal(executable_path):
    """回退到带终端窗口的方案"""
    safe_path = shlex.quote(executable_path)
    if sys.platform == 'win32':
        _windows_start(executable_path)
    elif sys.platform == 'darwin':
        script = f'tell app "Terminal" to do script "{safe_path}"'
        subprocess.Popen(["osascript", "-e", script], start_new_session=True)
    else:
        try:
            subprocess.Popen(["gnome-terminal", "--", "sh", "-c", safe_path],
                             start_new_session=True)
        except FileNotFoundError:
            subprocess.Popen(["xterm", "-e", safe_path],
                             start_new_session=True)


def _check_command_exists(cmd):
    """检查命令行工具是否存在"""
    try:
        subprocess.check_output(["which", cmd], stderr=subprocess.DEVNULL)
        return True
    except:
        return False


# 示例用法
if __name__ == '__main__':
    run_detached("/path/to/your/program")
