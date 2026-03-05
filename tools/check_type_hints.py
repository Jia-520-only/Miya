"""
类型提示检查脚本
检查弥娅核心模块的类型提示覆盖情况
"""
import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import io
from core.constants import Encoding

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=Encoding.UTF8)


def check_file_type_hints(file_path: Path) -> Dict:
    """
    检查Python文件的类型提示覆盖情况
    
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
    
    total_functions = 0
    functions_with_return_type = 0
    functions_with_param_types = 0
    total_params = 0
    typed_params = 0
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total_functions += 1
            
            # 检查返回类型
            if node.returns is not None:
                functions_with_return_type += 1
            
            # 检查参数类型
            has_param_types = False
            for arg in node.args.args:
                if arg.arg not in ['self', 'cls']:
                    total_params += 1
                    if arg.annotation is not None:
                        typed_params += 1
                        has_param_types = True
            
            if has_param_types:
                functions_with_param_types += 1
    
    return {
        'total_functions': total_functions,
        'functions_with_return_type': functions_with_return_type,
        'functions_with_param_types': functions_with_param_types,
        'total_params': total_params,
        'typed_params': typed_params,
        'return_type_coverage': functions_with_return_type / total_functions * 100 if total_functions > 0 else 0,
        'param_type_coverage': typed_params / total_params * 100 if total_params > 0 else 0
    }


def main():
    """主函数"""
    core_dir = Path(__file__).parent.parent / 'core'
    
    print("=" * 80)
    print("弥娅核心模块类型提示覆盖情况检查")
    print("=" * 80)
    
    all_files = []
    for py_file in sorted(core_dir.glob('*.py')):
        if py_file.name == '__init__.py':
            continue
        all_files.append(py_file)
    
    print(f"\n检查文件数: {len(all_files)}")
    print("\n" + "-" * 80)
    print(f"{'文件名':<35} {'函数数':<8} {'返回类型':<12} {'参数类型':<12}")
    print("-" * 80)
    
    total_functions = 0
    total_return_coverage = 0
    total_param_coverage = 0
    files_checked = 0
    
    for py_file in all_files:
        stats = check_file_type_hints(py_file)
        
        if 'error' in stats:
            print(f"{py_file.name:<35} {'ERROR':<8} {stats['error']}")
            continue
        
        files_checked += 1
        total_functions += stats['total_functions']
        total_return_coverage += stats['return_type_coverage']
        total_param_coverage += stats['param_type_coverage']
        
        return_mark = "✓" if stats['return_type_coverage'] >= 80 else "✗"
        param_mark = "✓" if stats['param_type_coverage'] >= 80 else "✗"
        
        print(f"{py_file.name:<35} {stats['total_functions']:<8} "
              f"{return_mark} {stats['return_type_coverage']:.1f}%{'':<6} "
              f"{param_mark} {stats['param_type_coverage']:.1f}%")
    
    print("\n" + "=" * 80)
    if files_checked > 0:
        avg_return_coverage = total_return_coverage / files_checked
        avg_param_coverage = total_param_coverage / files_checked
        print(f"平均返回类型覆盖率: {avg_return_coverage:.1f}%")
        print(f"平均参数类型覆盖率: {avg_param_coverage:.1f}%")
    print(f"总函数数: {total_functions}")
    print("=" * 80)


if __name__ == '__main__':
    main()
