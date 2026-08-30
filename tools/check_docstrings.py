"""
Docstring检查脚本
检查弥娅核心模块的docstring覆盖情况
"""
import ast
import sys
from pathlib import Path
from typing import Dict, List
import io
from core.constants import Encoding

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=Encoding.UTF8)


def check_file_docstrings(file_path: Path) -> Dict:
    """
    检查Python文件的docstring覆盖情况
    
    Args:
        file_path: Python文件路径
    
    Returns:
        统计信息字典
    """
    try:
        with open(file_path, 'r', encoding=Encoding.UTF8) as f:
            source = f.read()
    except Exception as e:
        return {'error': str(e)}
    
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {'error': '语法错误'}
    
    total_classes = 0
    classes_with_doc = 0
    total_functions = 0
    functions_with_doc = 0
    
    # 检查模块docstring
    module_doc = ast.get_docstring(tree) is not None
    
    # 检查类和函数
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            total_classes += 1
            if ast.get_docstring(node) is not None:
                classes_with_doc += 1
            
            # 检查类方法
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # 跳过特殊方法
                    if not item.name.startswith('__') or item.name.endswith('__'):
                        total_functions += 1
                        if ast.get_docstring(item) is not None:
                            functions_with_doc += 1
        
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 只统计顶层函数
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    break
            else:
                # 这个函数不在任何类中
                total_functions += 1
                if ast.get_docstring(node) is not None:
                    functions_with_doc += 1
    
    return {
        'module_doc': module_doc,
        'total_classes': total_classes,
        'classes_with_doc': classes_with_doc,
        'total_functions': total_functions,
        'functions_with_doc': functions_with_doc,
        'class_doc_coverage': classes_with_doc / total_classes * 100 if total_classes > 0 else 100,
        'function_doc_coverage': functions_with_doc / total_functions * 100 if total_functions > 0 else 100
    }


def main():
    """主函数"""
    core_dir = Path(__file__).parent.parent / 'core'
    
    print("=" * 80)
    print("弥娅核心模块Docstring覆盖情况检查")
    print("=" * 80)
    
    all_files = []
    for py_file in sorted(core_dir.glob('*.py')):
        if py_file.name == '__init__.py':
            continue
        all_files.append(py_file)
    
    print(f"\n检查文件数: {len(all_files)}")
    print("\n" + "-" * 80)
    print(f"{'文件名':<35} {'模块':<6} {'类':<8} {'函数':<8}")
    print("-" * 80)
    
    total_module_docs = 0
    total_class_coverage = 0
    total_function_coverage = 0
    files_checked = 0
    
    for py_file in all_files:
        stats = check_file_docstrings(py_file)
        
        if 'error' in stats:
            print(f"{py_file.name:<35} {'ERROR':<6} {stats['error']}")
            continue
        
        files_checked += 1
        
        module_mark = "✓" if stats['module_doc'] else "✗"
        class_mark = "✓" if stats['class_doc_coverage'] >= 80 else "✗"
        function_mark = "✓" if stats['function_doc_coverage'] >= 80 else "✗"
        
        if stats['module_doc']:
            total_module_docs += 1
        total_class_coverage += stats['class_doc_coverage']
        total_function_coverage += stats['function_doc_coverage']
        
        print(f"{py_file.name:<35} {module_mark:<6} "
              f"{class_mark} {stats['class_doc_coverage']:.1f}%{'':<4} "
              f"{function_mark} {stats['function_doc_coverage']:.1f}%")
    
    print("\n" + "=" * 80)
    if files_checked > 0:
        avg_class_coverage = total_class_coverage / files_checked
        avg_function_coverage = total_function_coverage / files_checked
        module_doc_coverage = total_module_docs / files_checked * 100
        print(f"模块docstring覆盖率: {module_doc_coverage:.1f}%")
        print(f"平均类docstring覆盖率: {avg_class_coverage:.1f}%")
        print(f"平均函数docstring覆盖率: {avg_function_coverage:.1f}%")
    print("=" * 80)


if __name__ == '__main__':
    main()
