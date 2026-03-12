#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live2D 模型文件夹重命名脚本
将包含中文和特殊符号的文件夹和文件重命名为纯英文
"""

import os
import shutil
from pathlib import Path

# 定义重命名映射关系
RENAME_MAP = {
    # 文件夹重命名映射
    '修女': 'nun',
    '承': 'cheng',
    '白发雪女vts': 'snow_lady_vts',
    '西域舞女': 'xiyu_dancer',
    '白发清冷御姐': 'white_sister',
    '狐仙': 'fox_spirit',
    '灵蝶之狐': 'butterfly_fox',
    '时冰': 'ice',
    '希斯提亚': 'hestia',
    '小fa': 'xiaofa',
    '夜蛊': 'night_poison',
    '夜翎': 'night_ling',
    '988小fa': 'xiaofa_988',
}

# 子文件夹重命名映射（在父文件夹内）
SUBFOLDER_RENAME_MAP = {
    # 修女文件夹内
    '修女.8192': 'nun.8192',

    # 承文件夹内
    '承': 'cheng',

    # 白发雪女vts文件夹内
    '白发雪女vts': 'snow_lady_vts',

    # 西域舞女文件夹内
    '西域舞女': 'xiyu_dancer',

    # 白发清冷御姐文件夹内
    '御姐完整版': 'sister_full',

    # 小fa文件夹内
    '小fa量贩·漫漫': 'xiaofa_manman',
}

# 文件重命名映射（针对特定文件）
FILE_RENAME_MAP = {
    # 修女文件夹内
    '修女.cdi3.json': 'nun.cdi3.json',
    '修女.moc3': 'nun.moc3',
    '修女.model3.json': 'nun.model3.json',
    '修女.physics3.json': 'nun.physics3.json',
    '修女.vtube.json': 'nun.vtube.json',
    'cc-修女.cfg': 'cc-nun.cfg',

    # 承文件夹内
    '承欢2024.model3.json': 'cheng_huan_2024.model3.json',
    '承欢2024.4.11（合并版）.cdi3.json': 'cheng_huan_2024_411.cdi3.json',
    '承欢2024.4.11（合并版）.moc3': 'cheng_huan_2024_411.moc3',
    '承欢2024.4.11（合并版）.physics3.json': 'cheng_huan_2024_411.physics3.json',
    '承欢2024.4.11（合并版）.vtube.json': 'cheng_huan_2024_411.vtube.json',
    '承欢2024.4.11（合并版）.4096': 'cheng_huan_2024_411.4096',

    # 白发雪女vts文件夹内
    '白发雪女.cdi3.json': 'snow_lady.cdi3.json',
    '白发雪女.moc3': 'snow_lady.moc3',
    '白发雪女.model3.json': 'snow_lady.model3.json',
    '白发雪女.physics3.json': 'snow_lady.physics3.json',
    '白发雪女.vtube.json': 'snow_lady.vtube.json',
    '白发雪女.4096': 'snow_lady.4096',

    # 西域舞女文件夹内
    'Xiyu.model3.json': 'Xiyu.model3.json',
    'Xiyu.cdi3.json': 'Xiyu.cdi3.json',
    'Xiyu.moc3': 'Xiyu.moc3',
    'Xiyu.physics3.json': 'Xiyu.physics3.json',
    'Xiyu.vtube.json': 'Xiyu.vtube.json',
    'Xiyu.4096': 'Xiyu.4096',
}


def rename_item(old_path: Path, new_name: str, item_type: str):
    """重命名文件或文件夹"""
    new_path = old_path.parent / new_name

    if new_path.exists():
        print(f"  ⚠️  跳过（已存在）: {old_path.name} -> {new_name}")
        return False

    try:
        shutil.move(str(old_path), str(new_path))
        print(f"  ✅ 重命名{item_type}: {old_path.name} -> {new_name}")
        return True
    except Exception as e:
        print(f"  ❌ 重命名失败: {old_path.name} -> {new_name}")
        print(f"     错误: {e}")
        return False


def process_directory(base_path: Path, is_base=True):
    """处理目录重命名"""
    print(f"\n{'='*60}")
    print(f"处理目录: {base_path}")
    print(f"{'='*60}")

    renamed_items = []

    # 获取所有子项
    try:
        items = list(base_path.iterdir())
    except Exception as e:
        print(f"❌ 无法读取目录: {e}")
        return renamed_items

    # 首先处理子文件夹（从深层到浅层）
    for item in sorted(items, key=lambda x: (not x.is_dir(), len(x.parts))):
        if item.is_dir():
            # 递归处理子目录
            renamed_items.extend(process_directory(item, is_base=False))

            # 检查是否需要重命名此子文件夹
            old_name = item.name
            new_name = SUBFOLDER_RENAME_MAP.get(old_name)

            if new_name and item.exists():
                success = rename_item(item, new_name, "文件夹")
                if success:
                    renamed_items.append((item, new_name))

    # 然后处理文件
    for item in sorted(items, key=lambda x: (not x.is_dir(), len(x.parts))):
        if item.is_file():
            old_name = item.name

            # 检查文件重命名映射
            new_name = FILE_RENAME_MAP.get(old_name)

            if new_name and item.exists():
                success = rename_item(item, new_name, "文件")
                if success:
                    renamed_items.append((item, new_name))

    return renamed_items


def rename_base_folders(base_path: Path):
    """重命名顶层文件夹"""
    print(f"\n{'='*60}")
    print(f"重命名顶层文件夹")
    print(f"{'='*60}")

    renamed_folders = []

    for old_name, new_name in RENAME_MAP.items():
        old_path = base_path / old_name

        if old_path.exists() and old_path.is_dir():
            new_path = base_path / new_name

            if new_path.exists():
                print(f"  ⚠️  跳过（已存在）: {old_name} -> {new_name}")
            else:
                try:
                    shutil.move(str(old_path), str(new_path))
                    print(f"  ✅ 重命名文件夹: {old_name} -> {new_name}")
                    renamed_folders.append((old_name, new_name))
                except Exception as e:
                    print(f"  ❌ 重命名失败: {old_name} -> {new_name}")
                    print(f"     错误: {e}")

    return renamed_folders


def main():
    """主函数"""
    # 设置基础路径
    base_path = Path(r'd:\AI_MIYA_Facyory\MIYA\Miya\live2d')

    if not base_path.exists():
        print(f"❌ 路径不存在: {base_path}")
        return

    print("\n" + "="*60)
    print("Live2D 模型文件夹重命名脚本")
    print("="*60)
    print(f"基础路径: {base_path}")

    input("\n按 Enter 开始重命名...")

    # 步骤1：重命名内部文件和子文件夹
    all_renamed = process_directory(base_path)

    # 步骤2：重命名顶层文件夹
    base_renamed = rename_base_folders(base_path)

    # 打印总结
    print("\n" + "="*60)
    print("重命名完成总结")
    print("="*60)
    print(f"内部文件/文件夹重命名: {len(all_renamed)} 项")
    print(f"顶层文件夹重命名: {len(base_renamed)} 项")

    print("\n下一步:")
    print("1. 检查重命名是否正确")
    print("2. 更新 live2dModels.ts 配置文件")
    print("3. 测试模型加载")

    print("\n重命名映射:")
    for old, new in RENAME_MAP.items():
        print(f"  {old} -> {new}")


if __name__ == '__main__':
    main()
