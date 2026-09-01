#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import customtkinter as ctk
import shutil
import datetime
import re
import json

# ================== 主题设置 ==================
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ================== 配置 ==================
IGNORE_FILE = ".gitignore"
SELF_FILENAME = os.path.basename(__file__)
BUILD_SCRIPT = "build.py"
CONFIG_FILE = "git_commit_config.json"

LOGS_DIR = "logs"
BACKUP_DIR = "backup"

BACKUP_EXCLUDE = {".git", "logs", "backup", "dist", "build", "__pycache__", ".idea", ".vscode", SELF_FILENAME}

os.makedirs(LOGS_DIR, exist_ok=True)


# ================== 工具函数 ==================
def run_git(args, cwd=None):
    try:
        proc = subprocess.Popen(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd or os.getcwd()
        )
        out, err = proc.communicate()
        return out.strip(), err.strip(), proc.returncode
    except Exception as e:
        return "", str(e), -1


def run_build(cwd=None):
    build_path = os.path.join(cwd or os.getcwd(), BUILD_SCRIPT)
    if not os.path.exists(build_path):
        return None, "构建脚本不存在", -1
    try:
        proc = subprocess.Popen(
            ["python", build_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd or os.getcwd()
        )
        out, err = proc.communicate()
        return out.strip(), err.strip(), proc.returncode
    except Exception as e:
        return "", str(e), -1


def ensure_self_ignored():
    """确保自身、配置文件和日志/备份目录被 .gitignore 忽略"""
    if not os.path.exists(IGNORE_FILE):
        with open(IGNORE_FILE, "w", encoding="utf-8") as f:
            f.write(f"# 本地工具，不提交\n{SELF_FILENAME}\n")
            f.write(f"# 本地配置文件（含路径信息）\n{CONFIG_FILE}\n")
            f.write(f"# 日志和备份目录\n{LOGS_DIR}/\n{BACKUP_DIR}/\n")
        return True

    with open(IGNORE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if SELF_FILENAME not in content:
        with open(IGNORE_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n# 本地工具，不提交\n{SELF_FILENAME}\n")

    if CONFIG_FILE not in content:
        with open(IGNORE_FILE, "a", encoding="utf-8") as f:
            f.write(f"# 本地配置文件（含路径信息）\n{CONFIG_FILE}\n")

    if f"{LOGS_DIR}/" not in content:
        with open(IGNORE_FILE, "a", encoding="utf-8") as f:
            f.write(f"# 日志和备份目录\n{LOGS_DIR}/\n{BACKUP_DIR}/\n")

    return True


def get_current_time_str():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def get_log_file():
    return os.path.join(LOGS_DIR, f"git_commit_{datetime.datetime.now().strftime('%Y%m%d')}.log")


def write_log(msg, level="INFO"):
    log_path = get_log_file()
    time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{time_str}] [{level}] {msg}\n")


def backup_project(src_dir):
    timestamp = get_current_time_str()
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)

    excluded = set(BACKUP_EXCLUDE)
    ignore_patterns = []
    gitignore_path = os.path.join(src_dir, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ignore_patterns.append(line)

    def should_exclude(name, rel_path):
        if name in excluded:
            return True
        for pat in ignore_patterns:
            if pat.endswith("/"):
                if rel_path.startswith(pat.rstrip("/")):
                    return True
            elif pat.startswith("*."):
                if name.endswith(pat[1:]):
                    return True
            elif pat == name:
                return True
        return False

    for root, dirs, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        if rel_root == ".":
            rel_root = ""
        if rel_root:
            dir_name = os.path.basename(root)
            if dir_name in excluded:
                dirs[:] = []
                continue
            if rel_root in ignore_patterns or any(rel_root.startswith(p.rstrip("/") + "/") for p in ignore_patterns if p.endswith("/")):
                dirs[:] = []
                continue

        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.join(rel_root, file) if rel_root else file
            if should_exclude(file, rel_path):
                continue
            dest_path = os.path.join(backup_path, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(file_path, dest_path)

    return backup_path


def load_recent_repos():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("recent_repos", [])
        except:
            pass
    return []


def save_recent_repos(repos):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"recent_repos": repos}, f, ensure_ascii=False, indent=2)
    except:
        pass


# ================== GUI 主类 ==================
class GitCommitGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("📦 Git 提交助手 · 完整版")
        self.geometry("960x900")
        self.resizable(True, True)

        self.recent_repos = load_recent_repos()
        self.repo_path = ctk.StringVar(value="")
        self.commit_msg = ctk.StringVar()
        self.tag_name = ctk.StringVar()
        self.tag_msg = ctk.StringVar()
        self.remote_url = ctk.StringVar(value="")  # 新增：远程地址
        self.files_var = {}
        self.loading = False

        self.create_widgets()
        self.after(300, self.initial_setup)

    # ---------- 界面构建 ----------
    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(pady=15, padx=20, fill="both", expand=True)

        # 标题
        ctk.CTkLabel(
            main_frame,
            text="📦 Git 提交助手 · 完整版",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        # ----- 行1：仓库路径 -----
        path_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        path_frame.pack(fill="x", pady=3)

        ctk.CTkLabel(path_frame, text="仓库路径：", font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkEntry(
            path_frame,
            textvariable=self.repo_path,
            placeholder_text="请选择或输入 Git 仓库目录",
            height=32
        ).pack(side="left", fill="x", expand=True, padx=(10, 8))

        ctk.CTkButton(path_frame, text="📂 选择仓库", command=self.choose_repo, width=90, height=32,
                      fg_color="#0078d4", hover_color="#005a9e").pack(side="left", padx=(0, 5))

        if self.recent_repos:
            ctk.CTkButton(path_frame, text="📋 最近", command=self.show_recent_menu, width=70, height=32,
                          fg_color="#6c757d", hover_color="#5a6268").pack(side="left", padx=(0, 5))

        ctk.CTkButton(path_frame, text="🔄 刷新", command=self.refresh_status, width=70, height=32,
                      fg_color="#2e8b57", hover_color="#3cb371").pack(side="left")

        # ----- 行2：远程地址（新增） -----
        remote_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        remote_frame.pack(fill="x", pady=3)

        ctk.CTkLabel(remote_frame, text="远程地址：", font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkEntry(
            remote_frame,
            textvariable=self.remote_url,
            placeholder_text="https://github.com/用户名/仓库名.git",
            height=32
        ).pack(side="left", fill="x", expand=True, padx=(10, 8))

        ctk.CTkButton(remote_frame, text="🔗 设置远程", command=self.set_remote, width=90, height=32,
                      fg_color="#fd7e14", hover_color="#e06b0a").pack(side="left", padx=(0, 5))

        ctk.CTkButton(remote_frame, text="🚀 推送 (首次)", command=self.push_first_time, width=100, height=32,
                      fg_color="#28a745", hover_color="#218838").pack(side="left", padx=(0, 5))

        # ----- 行3：分支/标签状态 -----
        status_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=(5, 0))
        self.branch_label = ctk.CTkLabel(status_frame, text="🌿 分支: --", font=ctk.CTkFont(size=12))
        self.branch_label.pack(side="left", padx=(0, 15))
        self.tag_label = ctk.CTkLabel(status_frame, text="🏷️ 标签: --", font=ctk.CTkFont(size=12))
        self.tag_label.pack(side="left", padx=(0, 15))
        self.remote_label = ctk.CTkLabel(status_frame, text="📡 远程: --", font=ctk.CTkFont(size=12))
        self.remote_label.pack(side="left")

        # ----- 文件列表 -----
        list_frame = ctk.CTkFrame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=(10, 5))

        header_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=(5, 0))
        ctk.CTkLabel(header_frame, text="暂存", width=50, font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(header_frame, text="状态", width=60, font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(header_frame, text="文件名", anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", fill="x", expand=True)

        scroll_frame = ctk.CTkFrame(list_frame)
        scroll_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.canvas = tk.Canvas(scroll_frame, highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(scroll_frame, orientation="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.files_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.canvas.create_window((0, 0), window=self.files_frame, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.files_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ----- 操作区 -----
        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.pack(fill="x", pady=(8, 0))

        # 提交信息
        msg_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        msg_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(msg_frame, text="提交信息：", font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkEntry(msg_frame, textvariable=self.commit_msg, placeholder_text="请输入提交说明...", height=30).pack(
            side="left", fill="x", expand=True, padx=(10, 0)
        )

        # 按钮行1
        btn_row1 = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row1.pack(fill="x", pady=(5, 2))

        ctk.CTkButton(btn_row1, text="✅ 提交", command=self.do_commit, height=32,
                      fg_color="#2e8b57").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row1, text="🚀 推送", command=self.do_push, height=32,
                      fg_color="#0078d4").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row1, text="📥 拉取", command=self.do_pull, height=32,
                      fg_color="#6f42c1").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row1, text="📡 远程信息", command=self.show_remote_info, height=32,
                      fg_color="#17a2b8").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row1, text="⏹ 取消暂存", command=self.unstage_selected, height=32,
                      fg_color="#d45a5a").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row1, text="📋 复制状态", command=self.copy_status, height=32,
                      fg_color="#6c757d").pack(side="left")

        # 按钮行2
        btn_row2 = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row2.pack(fill="x", pady=(5, 2))

        ctk.CTkLabel(btn_row2, text="标签名：", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkEntry(btn_row2, textvariable=self.tag_name, placeholder_text="v1.0.0", width=100, height=28).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(btn_row2, text="标签信息：", font=ctk.CTkFont(size=12)).pack(side="left")
        ctk.CTkEntry(btn_row2, textvariable=self.tag_msg, placeholder_text="版本说明", width=120, height=28).pack(side="left", padx=(0, 5))

        ctk.CTkButton(btn_row2, text="🏷️ 创建标签", command=self.create_tag, height=30,
                      fg_color="#fd7e14").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row2, text="🔄 切换标签", command=self.switch_tag, height=30,
                      fg_color="#20c997").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row2, text="🗑️ 删除标签", command=self.delete_tag, height=30,
                      fg_color="#dc3545").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row2, text="🔨 构建项目", command=self.build_project, height=30,
                      fg_color="#6c757d").pack(side="left", padx=(15, 0))
        ctk.CTkButton(btn_row2, text="💾 备份项目", command=self.backup_project_manual, height=30,
                      fg_color="#28a745").pack(side="left", padx=(6, 0))

        # 标签快速选择
        tag_btn_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        tag_btn_frame.pack(fill="x", pady=(3, 0))
        ctk.CTkLabel(tag_btn_frame, text="📋 已有标签：", font=ctk.CTkFont(size=12)).pack(side="left")
        self.tag_list_label = ctk.CTkLabel(tag_btn_frame, text="", font=ctk.CTkFont(size=12), text_color="#6c757d")
        self.tag_list_label.pack(side="left", padx=(5, 0))
        self.tag_btns_frame = ctk.CTkFrame(tag_btn_frame, fg_color="transparent")
        self.tag_btns_frame.pack(side="left", padx=(10, 0))

        # 日志
        log_frame = ctk.CTkFrame(main_frame)
        log_frame.pack(fill="both", expand=True, pady=(5, 0))

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=5, pady=(5, 0))
        ctk.CTkLabel(log_header, text="📋 执行日志", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(log_header, text="🗑️ 清空日志", command=self.clear_log, height=24, width=80,
                      fg_color="#dc3545").pack(side="right")

        self.log_text = ctk.CTkTextbox(log_frame, height=140, wrap="word", font=ctk.CTkFont(size=12))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text.configure(state="disabled")

        # 状态栏
        status_frame2 = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_frame2.pack(fill="x", pady=(3, 0))
        self.status_label = ctk.CTkLabel(status_frame2, text="就绪", font=ctk.CTkFont(size=12), anchor="w")
        self.status_label.pack(side="left")

    # ---------- 仓库选择 ----------
    def initial_setup(self):
        if self.recent_repos:
            for repo in self.recent_repos:
                if os.path.exists(repo) and os.path.exists(os.path.join(repo, ".git")):
                    self.repo_path.set(repo)
                    self.log(f"📂 自动加载最近仓库: {repo}")
                    self.refresh_status()
                    self.load_remote_info()
                    return
        self.show_repo_chooser()

    def show_repo_chooser(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("选择 Git 仓库")
        dialog.geometry("500x250")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(pady=30, padx=30, fill="both", expand=True)

        ctk.CTkLabel(frame, text="📂 请选择 Git 仓库目录", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 15))
        ctk.CTkLabel(frame, text="选择一个包含 .git 文件夹的项目目录，\n或选择普通文件夹后自动初始化 Git 仓库。",
                     font=ctk.CTkFont(size=13), justify="center").pack(pady=(0, 20))

        if self.recent_repos:
            ctk.CTkLabel(frame, text="最近打开的仓库：", font=ctk.CTkFont(size=12)).pack(anchor="w", pady=(0, 5))
            recent_frame = ctk.CTkFrame(frame, fg_color="transparent")
            recent_frame.pack(fill="x", pady=(0, 10))
            for repo in self.recent_repos[:5]:
                if os.path.exists(repo):
                    btn = ctk.CTkButton(
                        recent_frame,
                        text=os.path.basename(repo),
                        command=lambda r=repo: self.set_repo_and_close(r, dialog),
                        height=28,
                        fg_color="#e9ecef",
                        text_color="#212529",
                        hover_color="#dee2e6"
                    )
                    btn.pack(side="left", padx=3, pady=2)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))

        def choose_and_close():
            path = ctk.filedialog.askdirectory(title="选择 Git 仓库目录")
            if path:
                dialog.destroy()
                self.repo_path.set(path)
                self.add_recent_repo(path)
                if os.path.exists(os.path.join(path, ".git")):
                    self.log(f"📂 已选择仓库: {path}")
                    self.refresh_status()
                    self.load_remote_info()
                else:
                    if messagebox.askyesno("初始化 Git", f"目录 {path} 不是 Git 仓库，是否执行 `git init` 初始化？"):
                        self.init_repo()
                    else:
                        self.status_label.configure(text="非 Git 仓库，部分功能不可用")
                        self.log(f"📂 已选择目录: {path}（非 Git 仓库）")

        ctk.CTkButton(btn_frame, text="📂 浏览选择", command=choose_and_close, height=35,
                      fg_color="#0078d4").pack(side="left", padx=(0, 10))

        def skip():
            dialog.destroy()
            current = os.getcwd()
            self.repo_path.set(current)
            self.add_recent_repo(current)
            if os.path.exists(os.path.join(current, ".git")):
                self.log(f"📂 使用当前目录: {current}")
                self.refresh_status()
                self.load_remote_info()
            else:
                self.status_label.configure(text="非 Git 仓库，部分功能不可用")
                self.log(f"📂 当前目录: {current}（非 Git 仓库）")

        ctk.CTkButton(btn_frame, text="使用当前目录", command=skip, height=35,
                      fg_color="#6c757d").pack(side="left")

    def set_repo_and_close(self, repo, dialog):
        dialog.destroy()
        self.repo_path.set(repo)
        self.add_recent_repo(repo)
        self.log(f"📂 切换至最近仓库: {repo}")
        if os.path.exists(os.path.join(repo, ".git")):
            self.refresh_status()
            self.load_remote_info()
        else:
            self.status_label.configure(text="目录已损坏或非 Git 仓库")
            if messagebox.askyesno("初始化 Git", f"目录 {repo} 不是 Git 仓库，是否初始化？"):
                self.init_repo()

    def add_recent_repo(self, path):
        if path in self.recent_repos:
            self.recent_repos.remove(path)
        self.recent_repos.insert(0, path)
        self.recent_repos = self.recent_repos[:10]
        save_recent_repos(self.recent_repos)

    def show_recent_menu(self):
        if not self.recent_repos:
            messagebox.showinfo("提示", "暂无最近打开的仓库")
            return
        menu = tk.Menu(self, tearoff=0)
        for repo in self.recent_repos[:10]:
            if os.path.exists(repo):
                menu.add_command(
                    label=os.path.basename(repo) + "  (" + repo[:40] + "...)",
                    command=lambda r=repo: self.switch_repo(r)
                )
        menu.add_separator()
        menu.add_command(label="📂 浏览选择", command=self.choose_repo)
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def switch_repo(self, repo):
        self.repo_path.set(repo)
        self.add_recent_repo(repo)
        self.log(f"📂 切换至: {repo}")
        if os.path.exists(os.path.join(repo, ".git")):
            self.refresh_status()
            self.load_remote_info()
        else:
            self.status_label.configure(text="非 Git 仓库")
            if messagebox.askyesno("初始化 Git", f"目录 {repo} 不是 Git 仓库，是否初始化？"):
                self.init_repo()

    def choose_repo(self):
        path = ctk.filedialog.askdirectory(title="选择 Git 仓库目录")
        if path:
            self.repo_path.set(path)
            self.add_recent_repo(path)
            if os.path.exists(os.path.join(path, ".git")):
                self.log(f"📂 已选择仓库: {path}")
                self.refresh_status()
                self.load_remote_info()
            else:
                if messagebox.askyesno("初始化 Git", f"目录 {path} 不是 Git 仓库，是否执行 `git init` 初始化？"):
                    self.init_repo()
                else:
                    self.status_label.configure(text="非 Git 仓库，部分功能不可用")
                    self.log(f"📂 已选择目录: {path}（非 Git 仓库）")

    # ---------- 远程地址管理（新增） ----------
    def load_remote_info(self):
        """加载当前远程地址并显示在输入框中"""
        repo = self.repo_path.get()
        if not repo:
            return
        out, _, code = run_git(["remote", "-v"], cwd=repo)
        if code == 0 and out:
            for line in out.splitlines():
                if "(fetch)" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        self.remote_url.set(parts[1])
                        self.remote_label.configure(text=f"📡 远程: {parts[1][:40]}...")
                        return
        self.remote_url.set("")
        self.remote_label.configure(text="📡 远程: 无")

    def set_remote(self):
        """设置远程仓库地址（origin）"""
        repo = self.repo_path.get()
        url = self.remote_url.get().strip()
        if not repo:
            messagebox.showwarning("提示", "请先选择仓库目录")
            return
        if not url:
            messagebox.showwarning("提示", "请输入远程仓库地址")
            return

        # 检查是否已有 origin
        out, _, _ = run_git(["remote", "get-url", "origin"], cwd=repo)
        if out:
            # 已存在，询问是否修改
            if not messagebox.askyesno("确认修改", f"已存在远程仓库 origin，是否替换为 {url}？"):
                return
            # 删除旧的 origin
            run_git(["remote", "remove", "origin"], cwd=repo)

        out, err, code = run_git(["remote", "add", "origin", url], cwd=repo)
        if code == 0:
            self.log(f"✅ 远程仓库 origin 已设置为: {url}")
            self.remote_label.configure(text=f"📡 远程: {url[:40]}...")
            # 更新远程信息
            self.update_remote_info()
        else:
            self.log(f"❌ 设置远程失败：{err}")
            messagebox.showerror("错误", f"设置远程失败：{err}")

    def push_first_time(self):
        """首次推送：git push -u origin main"""
        repo = self.repo_path.get()
        if not repo:
            messagebox.showwarning("提示", "请先选择仓库目录")
            return

        # 检查是否有远程仓库
        out, _, _ = run_git(["remote", "-v"], cwd=repo)
        if not out:
            # 没有远程，先让用户设置
            messagebox.showwarning("提示", "请先在“远程地址”输入框中设置远程仓库地址，再点击推送")
            return

        self.log("🚀 准备首次推送...")
        self.status_label.configure(text="正在首次推送...")
        self.update_idletasks()

        def task():
            # 确保分支名正确
            branch_out, _, _ = run_git(["branch", "--show-current"], cwd=repo)
            branch = branch_out or "main"

            # 执行首次推送
            out, err, code = run_git(["push", "-u", "origin", branch], cwd=repo)
            if code == 0:
                self.after(0, lambda: self.log(f"✅ 首次推送成功！分支: {branch}"))
                self.after(0, lambda: self.status_label.configure(text="首次推送完成"))
            else:
                self.after(0, lambda: self.log(f"❌ 首次推送失败：{err}"))
                self.after(0, lambda: self.status_label.configure(text="首次推送失败"))
                self.after(0, lambda: messagebox.showerror("错误", f"首次推送失败：{err}"))

        threading.Thread(target=task, daemon=True).start()

    # ---------- Git 操作 ----------
    def init_repo(self):
        repo = self.repo_path.get()
        self.log(f"🔧 正在初始化 Git 仓库: {repo}")
        self.status_label.configure(text="正在初始化...")
        self.update_idletasks()

        def task():
            out, err, code = run_git(["init"], cwd=repo)
            if code == 0:
                self.after(0, lambda: self.log("✅ Git 仓库初始化成功"))
                self.after(0, lambda: self.status_label.configure(text="Git 仓库已初始化"))
                self.after(0, self.refresh_status)
            else:
                self.after(0, lambda: self.log(f"❌ 初始化失败：{err}"))
                self.after(0, lambda: self.status_label.configure(text="初始化失败"))

        threading.Thread(target=task, daemon=True).start()

    def refresh_status(self):
        if self.loading:
            return
        if not self.repo_path.get():
            self.status_label.configure(text="请先选择仓库")
            return

        self.loading = True
        self.status_label.configure(text="正在刷新...")
        self.update_idletasks()

        def task():
            repo = self.repo_path.get()
            out, err, code = run_git(["status", "--porcelain"], cwd=repo)
            if code != 0:
                if "not a git repository" in err.lower() or "fatal" in err.lower():
                    if not os.path.exists(os.path.join(repo, ".git")):
                        self.after(0, self.ask_init_repo)
                    else:
                        self.after(0, lambda: self.log(f"❌ Git 命令执行失败：{err}"))
                        self.after(0, lambda: self.status_label.configure(text="错误"))
                else:
                    self.after(0, lambda: self.log(f"❌ Git 命令执行失败：{err}"))
                    self.after(0, lambda: self.status_label.configure(text="错误"))
                self.loading = False
                return

            branch_out, _, _ = run_git(["branch", "--show-current"], cwd=repo)
            branch = branch_out or "detached"
            tag_out, _, _ = run_git(["describe", "--tags", "--exact-match"], cwd=repo)
            tag = tag_out or "无"

            lines = out.splitlines() if out else []
            files = []
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                files.append((parts[1], parts[0]))

            self.after(0, lambda: self.update_file_list(files))
            self.after(0, lambda: self.branch_label.configure(text=f"🌿 分支: {branch}"))
            self.after(0, lambda: self.tag_label.configure(text=f"🏷️ 标签: {tag}"))
            self.after(0, lambda: self.status_label.configure(text=f"已刷新，共 {len(files)} 个文件变更"))
            self.after(0, lambda: self.load_tags())
            self.after(0, lambda: self.update_remote_info())
            self.loading = False

        threading.Thread(target=task, daemon=True).start()

    def ask_init_repo(self):
        if messagebox.askyesno("初始化 Git 仓库", f"当前目录 {self.repo_path.get()} 不是 Git 仓库，是否执行 `git init` 初始化？"):
            self.init_repo()
        else:
            self.status_label.configure(text="非 Git 仓库，部分功能不可用")
            self.log("⏭️ 用户选择跳过 Git 初始化")

    def update_remote_info(self):
        repo = self.repo_path.get()
        out, _, code = run_git(["remote", "-v"], cwd=repo)
        if code == 0 and out:
            lines = out.splitlines()
            if lines:
                match = re.search(r"(\S+)\s+\(fetch\)", lines[0])
                if match:
                    self.remote_url.set(match.group(1))
                    self.remote_label.configure(text=f"📡 远程: {match.group(1)[:40]}...")
                    return
        self.remote_url.set("")
        self.remote_label.configure(text="📡 远程: 无")

    # ---------- 文件列表 ----------
    def update_file_list(self, files):
        for widget in self.files_frame.winfo_children():
            widget.destroy()
        self.files_var.clear()

        if not files:
            ctk.CTkLabel(self.files_frame, text="✨ 没有文件变更，工作区干净",
                         font=ctk.CTkFont(size=13), text_color="#6c757d").pack(pady=20)
            return

        for fname, status in files:
            var = tk.BooleanVar(value=False)
            self.files_var[fname] = var

            row = ctk.CTkFrame(self.files_frame, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=1)

            cb = ctk.CTkCheckBox(row, variable=var, text="", width=30)
            cb.pack(side="left", padx=(0, 5))

            if "M" in status:
                color = "#d4880f"
            elif "A" in status:
                color = "#2e8b57"
            elif "D" in status:
                color = "#b22222"
            else:
                color = "#6c757d"

            ctk.CTkLabel(row, text=status, width=40, text_color=color).pack(side="left")
            name_label = ctk.CTkLabel(row, text=fname, anchor="w", font=ctk.CTkFont(size=12))
            name_label.pack(side="left", fill="x", expand=True, padx=(5, 0))

            def on_double_click(e, fn=fname):
                self.toggle_stage(fn)
            row.bind("<Double-Button-1>", on_double_click)
            name_label.bind("<Double-Button-1>", on_double_click)

    # ---------- 暂存操作 ----------
    def toggle_stage(self, fname):
        if fname not in self.files_var:
            return
        repo = self.repo_path.get()
        out, _, _ = run_git(["status", "--porcelain", fname], cwd=repo)
        if out:
            status = out[:2]
            if status[1] == " ":
                self.stage_files([fname])
            else:
                self.unstage_files([fname])

    def stage_files(self, files):
        if not files:
            return
        repo = self.repo_path.get()
        _, err, code = run_git(["add"] + files, cwd=repo)
        if code == 0:
            self.log(f"✅ 已暂存 {len(files)} 个文件")
        else:
            _, err2, code2 = run_git(["add", "--"] + files, cwd=repo)
            if code2 == 0:
                self.log(f"✅ 已暂存 {len(files)} 个文件（使用 -- 方式）")
            else:
                self.log(f"❌ 暂存失败：{err}")
        self.refresh_status()

    def unstage_files(self, files):
        if not files:
            return
        repo = self.repo_path.get()
        _, err, code = run_git(["reset", "HEAD"] + files, cwd=repo)
        if code == 0:
            self.log(f"✅ 已取消暂存 {len(files)} 个文件")
        else:
            self.log(f"❌ 取消暂存失败：{err}")
        self.refresh_status()

    def unstage_selected(self):
        selected = [f for f, v in self.files_var.items() if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请先勾选要取消暂存的文件")
            return
        self.unstage_files(selected)

    def get_selected_files(self):
        return [f for f, v in self.files_var.items() if v.get()]

    # ---------- 提交 / 推送 / 拉取 ----------
    def do_commit(self):
        msg = self.commit_msg.get().strip()
        if not msg:
            messagebox.showwarning("提示", "请输入提交信息")
            return
        selected = self.get_selected_files()
        if not selected:
            out, _, _ = run_git(["diff", "--cached", "--name-only"], cwd=self.repo_path.get())
            if not out.strip():
                messagebox.showinfo("提示", "没有要提交的变更，请先勾选文件或暂存变更")
                return
            self.commit_only(msg)
        else:
            self.stage_and_commit(selected, msg)

    def stage_and_commit(self, files, msg):
        repo = self.repo_path.get()
        _, err, code = run_git(["add"] + files, cwd=repo)
        if code != 0:
            self.log(f"❌ 暂存失败：{err}")
            return
        self.commit_only(msg)

    def commit_only(self, msg):
        repo = self.repo_path.get()
        out, err, code = run_git(["commit", "-m", msg], cwd=repo)
        if code == 0:
            self.log("✅ 提交成功")
            self.commit_msg.set("")
            self.refresh_status()
            self.auto_backup()
        else:
            self.log(f"❌ 提交失败：{err}")

    def do_push(self):
        self.log("⏳ 正在推送...")
        out, err, code = run_git(["push"], cwd=self.repo_path.get())
        if code == 0:
            self.log("✅ 推送成功")
            self.refresh_status()
        else:
            self.log(f"❌ 推送失败：{err}")

    def do_pull(self):
        self.log("⏳ 正在拉取...")
        out, err, code = run_git(["pull"], cwd=self.repo_path.get())
        if code == 0:
            self.log("✅ 拉取成功")
            self.refresh_status()
            self.load_tags()
        else:
            self.log(f"❌ 拉取失败：{err}")

    # ---------- 远程信息 ----------
    def show_remote_info(self):
        repo = self.repo_path.get()
        self.log("📡 获取远程信息...")
        run_git(["fetch"], cwd=repo)
        out_b, _, _ = run_git(["branch", "-r"], cwd=repo)
        out_diff, _, _ = run_git(["log", "HEAD..origin/HEAD", "--oneline"], cwd=repo)
        out_diff2, _, _ = run_git(["log", "origin/HEAD..HEAD", "--oneline"], cwd=repo)

        msg = f"📡 远程分支:\n{out_b if out_b else '  无'}\n\n"
        msg += f"⬆️ 本地落后远程的提交:\n{out_diff if out_diff else '  无'}\n\n"
        msg += f"⬇️ 本地领先远程的提交:\n{out_diff2 if out_diff2 else '  无'}"
        messagebox.showinfo("远程信息", msg)
        self.log("✅ 远程信息已显示")

    # ---------- 标签管理 ----------
    def load_tags(self):
        repo = self.repo_path.get()
        out, _, code = run_git(["tag", "-l"], cwd=repo)
        if code == 0 and out:
            tags = out.splitlines()
            self.tag_list_label.configure(text=" ".join(tags))
            for widget in self.tag_btns_frame.winfo_children():
                widget.destroy()
            for tag in tags[:8]:
                ctk.CTkButton(
                    self.tag_btns_frame,
                    text=tag,
                    command=lambda t=tag: self.tag_name.set(t),
                    height=24,
                    width=80,
                    fg_color="#e9ecef",
                    text_color="#212529",
                    hover_color="#dee2e6"
                ).pack(side="left", padx=2, pady=2)
        else:
            self.tag_list_label.configure(text="(无标签)")
            for widget in self.tag_btns_frame.winfo_children():
                widget.destroy()

    def create_tag(self):
        tag = self.tag_name.get().strip()
        msg = self.tag_msg.get().strip() or f"版本 {tag}"
        if not tag:
            messagebox.showwarning("提示", "请输入标签名（如 v1.0.0）")
            return
        repo = self.repo_path.get()
        out, err, code = run_git(["tag", "-a", tag, "-m", msg], cwd=repo)
        if code == 0:
            self.log(f"✅ 标签 {tag} 创建成功")
            self.tag_name.set("")
            self.tag_msg.set("")
            self.load_tags()
            if messagebox.askyesno("推送标签", f"是否推送标签 {tag} 到远程？"):
                code2 = run_git(["push", "origin", tag], cwd=repo)[2]
                if code2 == 0:
                    self.log(f"✅ 标签 {tag} 已推送到远程")
                else:
                    self.log("❌ 推送标签失败")
        else:
            self.log(f"❌ 创建标签失败：{err}")
            messagebox.showerror("错误", f"创建标签失败：{err}")

    def switch_tag(self):
        tag = self.tag_name.get().strip()
        if not tag:
            messagebox.showwarning("提示", "请输入要切换到的标签名")
            return
        repo = self.repo_path.get()
        out, err, code = run_git(["checkout", tag], cwd=repo)
        if code == 0:
            self.log(f"✅ 已切换到标签 {tag}")
            self.refresh_status()
        else:
            self.log(f"❌ 切换标签失败：{err}")
            messagebox.showerror("错误", f"切换标签失败：{err}")

    def delete_tag(self):
        tag = self.tag_name.get().strip()
        if not tag:
            messagebox.showwarning("提示", "请输入要删除的标签名")
            return
        if not messagebox.askyesno("确认删除", f"确定要删除标签 {tag} 吗？\n（本地和远程都会删除）"):
            return
        repo = self.repo_path.get()
        code1 = run_git(["tag", "-d", tag], cwd=repo)[2]
        if code1 != 0:
            self.log("❌ 删除本地标签失败")
            return
        code2 = run_git(["push", "origin", "--delete", tag], cwd=repo)[2]
        if code2 == 0:
            self.log(f"✅ 标签 {tag} 已删除（本地 + 远程）")
        else:
            self.log("⚠️ 本地已删除，但远程删除失败")
        self.tag_name.set("")
        self.load_tags()
        self.refresh_status()

    # ---------- 构建 ----------
    def build_project(self):
        self.log("🔨 开始构建项目...")
        self.status_label.configure(text="正在构建...")
        self.update_idletasks()

        def task():
            out, err, code = run_build(self.repo_path.get())
            self.after(0, lambda: self.log(f"构建输出：{out}" if out else "无输出"))
            if code == 0:
                self.after(0, lambda: self.log("✅ 构建成功！"))
                self.after(0, lambda: self.status_label.configure(text="构建完成"))
            else:
                self.after(0, lambda: self.log(f"❌ 构建失败：{err}"))
                self.after(0, lambda: self.status_label.configure(text="构建失败"))
        threading.Thread(target=task, daemon=True).start()

    # ---------- 备份 ----------
    def auto_backup(self):
        self.log("💾 自动备份项目...")
        self.status_label.configure(text="正在备份...")
        self.update_idletasks()

        def task():
            try:
                path = backup_project(self.repo_path.get())
                self.after(0, lambda: self.log(f"✅ 项目已备份到: {path}"))
                self.after(0, lambda: self.status_label.configure(text="备份完成"))
            except Exception as e:
                self.after(0, lambda: self.log(f"❌ 备份失败：{e}"))
                self.after(0, lambda: self.status_label.configure(text="备份失败"))
        threading.Thread(target=task, daemon=True).start()

    def backup_project_manual(self):
        if messagebox.askyesno("确认备份", "确定要备份整个项目吗？\n（会排除 .git、logs、backup 等目录）"):
            self.auto_backup()

    # ---------- 日志 ----------
    def log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update_idletasks()
        write_log(msg, "INFO")

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.log("🗑️ 日志已清空（仅界面）")

    def copy_status(self):
        out, _, _ = run_git(["status"], cwd=self.repo_path.get())
        if out:
            self.clipboard_clear()
            self.clipboard_append(out)
            self.log("📋 状态已复制到剪贴板")
        else:
            self.log("❌ 无法获取状态")


# ================== 主程序入口 ==================
if __name__ == "__main__":
    ensure_self_ignored()
    app = GitCommitGUI()
    app.mainloop()