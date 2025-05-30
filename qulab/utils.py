import os
import shlex
import subprocess
import sys
import time

import click


def combined_env(extra_paths=None):
    env = os.environ.copy()

    # Build a combined PYTHONPATH: current interpreter's sys.path entries + extra_paths
    paths = [p for p in sys.path if p]
    if extra_paths:
        if isinstance(extra_paths, str):
            extra_paths = [extra_paths]
        paths.extend(extra_paths)

    # Prepend to any existing PYTHONPATH in the environment
    existing = env.get('PYTHONPATH', '')
    combined = os.pathsep.join(paths + ([existing] if existing else []))
    env['PYTHONPATH'] = combined
    return env


def run_detached(script, env=None):
    """
    启动可执行文件并完全分离（优先用 tmux/screen），无需额外终端窗口
    支持 Windows、Linux 和 macOS
    """
    if env is None:
        env = combined_env()
    try:
        if sys.platform == 'win32' or not _unix_detach_with_tmux_or_screen(
                script, env):
            # 回退到带终端窗口的方案
            run_detached_with_terminal(script, env)

    except Exception as e:
        click.echo(f"启动失败: {e}")
        sys.exit(1)


def _windows_start(script, env):
    """Windows 弹窗启动方案"""
    subprocess.Popen(f'start cmd /k "{script}"',
                     shell=True,
                     env=env,
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)


def _unix_detach_with_tmux_or_screen(script, env):
    """Unix 后台分离方案（无窗口）"""
    safe_path = shlex.quote(script)
    session_name = f"qulab_{int(time.time())}"

    # 尝试 tmux
    if _check_command_exists("tmux", env):
        command = [
            "tmux",
            "new-session",
            "-d",
            "-s",
            session_name,
            script + " ; tmux wait-for -S finished",  # 等待命令结束
            ";",
            "tmux",
            "wait-for",
            "finished"  # 防止进程立即退出
        ]
        subprocess.Popen(" ".join(command),
                         shell=True,
                         env=env,
                         start_new_session=True)
        click.echo(f"已启动 tmux 会话: {session_name}")
        click.echo(f"你可以使用 `tmux attach -t {session_name}` 来查看输出")
        return True

    # 尝试 screen
    elif _check_command_exists("screen", env):
        command = ["screen", "-dmS", session_name, script]
        subprocess.Popen(command, env=env, start_new_session=True)
        click.echo(f"已启动 screen 会话: {session_name}")
        click.echo(f"你可以使用 `screen -r {session_name}` 来查看输出")
        return True

    return False


def run_detached_with_terminal(script, env=None):
    """回退到带终端窗口的方案"""
    if env is None:
        env = combined_env()

    if sys.platform == 'win32':
        _windows_start(script, env)
    elif sys.platform == 'darwin':
        # script=shlex.quote(script)
        script = f'tell app "Terminal" to do script "{script}"'
        subprocess.Popen(["osascript", "-e", script],
                         env=env,
                         start_new_session=True)
    else:
        try:
            subprocess.Popen(
                ["gnome-terminal", "--", "sh", "-c", script],
                env=env,
                start_new_session=True)
        except FileNotFoundError:
            subprocess.Popen(["xterm", "-e", script],
                             env=env,
                             start_new_session=True)


def _check_command_exists(cmd, env):
    """检查命令行工具是否存在"""
    try:
        subprocess.check_output(["which", cmd],
                                env=env,
                                stderr=subprocess.DEVNULL)
        return True
    except:
        return False


# 示例用法
if __name__ == '__main__':
    run_detached("/path/to/your/program --option1=1 --option2=2 arg1 arg2")
