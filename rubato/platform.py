"""
跨平台助手 —— 消除 Windows 三大隐患:程序名解析、UTF-8 编码、subprocess 封装。

为什么需要这个模块(三个坑,都在 Linux 沙盒里不可见、到 Windows 才炸):
  1. subprocess 裸程序名依赖 PATH,且 Windows 程序名带 .exe / 平台相关(MuseScore4.exe vs mscore)
  2. pathlib.read_text() / open() 在 Windows 默认用系统编码(cp1252/GBK)而非 UTF-8,
     乐谱文本、作曲家名、音乐符号会乱码或崩溃
  3. subprocess 在 Windows 需要 shell=False + 列表参数(本项目已遵守)

执行者铁律:项目内一切文本 IO 走本模块的 read_text/write_text/read_jsonl/write_jsonl,
一切外部程序调用走 run()。禁止裸 open() 和裸 subprocess.run([程序名, ...])。
"""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path


# ---------------------------------------------------------------- 程序路径解析

_BIN_CACHE: dict[str, str] = {}


def load_binaries(project_yaml: str | Path = "configs/project.yaml") -> dict:
    """从 project.yaml 读 binaries 段;缓存。"""
    import yaml
    cfg = yaml.safe_load(Path(project_yaml).read_text(encoding="utf-8"))
    return cfg.get("binaries", {})


def resolve_exe(name: str, binaries: dict | None = None) -> str:
    """
    解析外部程序的可执行路径。
    binaries[name] 为绝对路径 → 直接用(校验存在);为裸名或缺失 → 在 PATH 查(shutil.which)。
    找不到即 FileNotFoundError,带清晰指引(不静默失败到运行时诡异报错)。
    """
    if name in _BIN_CACHE:
        return _BIN_CACHE[name]
    binaries = binaries if binaries is not None else load_binaries()
    configured = binaries.get(name)

    candidate = configured or name
    p = Path(candidate)
    if p.is_absolute():
        if not p.exists():
            raise FileNotFoundError(
                f"[{name}] 配置的绝对路径不存在: {candidate}\n"
                f"  → 修正 configs/project.yaml 的 binaries.{name}")
        resolved = str(p)
    else:
        found = shutil.which(candidate)
        # Windows 便利:未带扩展名时再试 .exe
        if not found and not candidate.lower().endswith((".exe", ".bat", ".cmd")):
            found = shutil.which(candidate + ".exe")
        if not found:
            raise FileNotFoundError(
                f"[{name}] 在 PATH 中未找到 '{candidate}'\n"
                f"  → 要么把它加入 PATH,要么在 configs/project.yaml 的 binaries.{name} 填绝对路径")
        resolved = found
    _BIN_CACHE[name] = resolved
    return resolved


def run(name: str, args: list[str], binaries: dict | None = None,
        check: bool = True, capture: bool = True, timeout: float | None = None,
        cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    """
    调用外部程序。name 经 resolve_exe 解析;args 为其余参数(纯列表,永不 shell=True)。
    stdout/stderr 以 UTF-8 解码(errors='replace' 防解码崩溃)。
    """
    exe = resolve_exe(name, binaries)
    return subprocess.run(
        [exe, *args],
        check=check,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


# ---------------------------------------------------------------- UTF-8 文件 IO

def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # newline='\n' 保证跨平台一致的换行(不被 Windows 改成 \r\n)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_jsonl(path: str | Path):
    """逐行 yield dict。跳过空行。"""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: str | Path, rows) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str | Path, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # 自检:UTF-8 往返(含音乐符号与中文作曲家名)+ 程序解析
    import tempfile, os
    d = tempfile.mkdtemp()
    payload = [{"composer": "德彪西", "sym": "A♭3 · 3/4 k-4", "midi": 60},
               {"composer": "Rachmaninoff", "sym": "F##4", "midi": 66}]
    fp = os.path.join(d, "t.jsonl")
    write_jsonl(fp, payload)
    back = list(read_jsonl(fp))
    assert back == payload, back
    print("UTF-8 jsonl 往返(含 ♭/中文/双升号): OK")
    # 程序解析:python 一定在 PATH
    try:
        exe = resolve_exe("python", {"python": "python"})
        print("resolve_exe('python'):", "OK")
    except FileNotFoundError:
        exe = resolve_exe("python3", {"python3": "python3"})
        print("resolve_exe fallback python3: OK")
    # 缺失程序给清晰错误
    try:
        resolve_exe("no_such_prog_xyz", {})
        print("FAIL: 应抛 FileNotFoundError")
    except FileNotFoundError as e:
        print("缺失程序清晰报错: OK")
