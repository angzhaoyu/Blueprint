"""
states_sort.py
对 states.txt 中 page-states 按导航深度排序
深层页面优先检测，起始页最后检测

用法:
    python states_sort.py <states.txt路径> <起始状态>
    python states_sort.py task/states.txt zhuye
"""

import sys
from pathlib import Path
from collections import deque
import os
import re

def sort_states_file(file_path, start_state):
    """
    读取 states.txt，按导航拓扑排序 page-states，原地覆写
    
    Args:
        file_path: states.txt 路径
        start_state: 起始页面英文名（如 "zhuye"）
    
    Returns:
        True 成功, False 失败
    """
    file_path = Path(file_path).resolve()

    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # ========== 1. 定位各节起始行 ==========
    SECTIONS = ('pop-states', 'pop-change', 'page-states', 'page-change')
    section_starts = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('#'):
            tag = stripped.lstrip('#').strip()
            if tag in SECTIONS:
                section_starts[tag] = i

    if 'page-states' not in section_starts:
        print("⚠️ 未找到 #page-states 节")
        return False

    # ========== 2. 确定 page-states 范围 ==========
    ps_start = section_starts['page-states'] + 1
    ps_end = len(lines)
    for name, idx in section_starts.items():
        if idx > section_starts['page-states'] and idx < ps_end:
            ps_end = idx

    # 提取条目（保留原始行格式）
    entries = {}          # key → 原始行
    entry_indices = []    # 条目在 lines 中的下标

    for i in range(ps_start, ps_end):
        clean = lines[i].split('#')[0].strip()
        if clean and '=' in clean:
            key = clean.split('=', 1)[0].strip()
            entries[key] = lines[i]
            entry_indices.append(i)

    all_states = list(entries.keys())

    if not all_states:
        print("⚠️ page-states 无条目")
        return False

    if start_state not in entries:
        print(f"❌ 起始状态 '{start_state}' 不在 page-states 中")
        print(f"   可选: {all_states}")
        return False

    # ========== 3. 从 page-change 构建导航图 ==========
    graph = {}
    if 'page-change' in section_starts:
        pc_start = section_starts['page-change'] + 1
        pc_end = len(lines)
        for name, idx in section_starts.items():
            if idx > section_starts['page-change'] and idx < pc_end:
                pc_end = idx

        for i in range(pc_start, pc_end):
            clean = lines[i].split('#')[0].strip()
            if clean and '=' in clean:
                key = clean.split('=', 1)[0].strip()
                parts = key.split('_')
                if len(parts) >= 3:
                    graph.setdefault(parts[0], set()).add(parts[1])

    # ========== 4. BFS 分层 ==========
    levels = {start_state: 0}
    visited = {start_state}
    queue = deque([(start_state, 0)])

    while queue:
        curr, depth = queue.popleft()
        for ns in graph.get(curr, set()):
            if ns not in visited and ns in set(all_states):
                visited.add(ns)
                levels[ns] = depth + 1
                queue.append((ns, depth + 1))

    # 不可达的页面给最高优先级（最前面）
    max_depth = max(levels.values()) if levels else 0
    for s in all_states:
        if s not in levels:
            levels[s] = max_depth + 1

    # 按深度降序：深的在前，起始页在最后
    sorted_states = sorted(all_states, key=lambda s: -levels[s])

    # ========== 5. 输出信息 ==========
    print(f"📂 文件: {file_path}")
    print(f'🏠 state="{start_state}"')
    print(f"\n📊 排序结果 (上→下 = 优先检测→最后检测):")
    for s in sorted_states:
        d = levels[s]
        marker = " ← 起始页 (最后检测)" if s == start_state else ""
        print(f"   深度[{d}] {s}{marker}")

    # ========== 6. 原地替换 ==========
    sorted_lines = [entries[s] for s in sorted_states]
    for j, file_idx in enumerate(entry_indices):
        lines[file_idx] = sorted_lines[j]

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"\n✅ 已更新: {file_path}")
    return True

def update_states_file(file_path, old_path="tasks/", new_path="tasks/states/"):
    """
    更新 states.txt 文件中的路径
    
    Args:
        file_path: states.txt 文件的路径
        old_path: 要替换的旧路径 (默认: "tasks/")
        new_path: 新路径 (默认: "tasks/states/")
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"错误: 文件 {file_path} 不存在")
            return False
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 检查是否已经完成过此替换（无论是路径增加还是减少）
        if old_path not in content and new_path in content:
            # 旧路径不存在且新路径存在，说明已经完成过替换，避免重复
            print(f"警告: 文件中已不存在路径 '{old_path}' 且已包含路径 '{new_path}'，无需更新")
            print("可能已经运行过此工具，避免重复修改")
            return False
        
        # 替换路径
        updated_content = content.replace(old_path, new_path)
        
        # 检查是否有更改
        if content == updated_content:
            print(f"警告: 文件中没有找到路径 '{old_path}'，无需更新")
            return False
        
        # 写入更新后的内容
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        
        print(f"成功更新文件 {file_path}")
        print(f"已将 '{old_path}' 替换为 '{new_path}'")
        return True
    
    except Exception as e:
        print(f"更新文件时出错: {e}")
        return False

def check_file_status(file_path, old_path="tasks/", new_path="tasks/states/"):
    """
    检查文件的状态，显示当前路径使用情况
    
    Args:
        file_path: states.txt 文件的路径
        old_path: 旧路径 (默认: "tasks/")
        new_path: 新路径 (默认: "tasks/states/")
    """
    try:
        if not os.path.exists(file_path):
            print(f"错误: 文件 {file_path} 不存在")
            return
        
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        old_count = content.count(old_path)
        new_count = content.count(new_path)
        
        print(f"文件状态检查: {file_path}")
        print(f"包含旧路径 '{old_path}': {old_count} 次")
        print(f"包含新路径 '{new_path}': {new_count} 次")
        
        if old_count > 0 and new_count == 0:
            print("状态: 文件需要更新")
        elif old_count == 0 and new_count > 0:
            print("状态: 文件已更新")
        elif old_count > 0 and new_count > 0:
            print("状态: 文件包含混合路径，可能需要手动检查")
        else:
            print("状态: 文件不包含相关路径")
    
    except Exception as e:
        print(f"检查文件状态时出错: {e}")


# ==================== 入口 ====================
if __name__ == '__main__':
    """ if len(sys.argv) < 3:
        print("用法: python states_sort.py <states.txt> <起始状态>")
        print("例:   python states_sort.py tasks/states.txt zhuye")
        sys.exit(1)"""
    txt_path = "XYC2/tasks/states.txt"
    sort_states_file(txt_path, "zhuye")
    update_states_file(txt_path, "tasks/states/", "states/")