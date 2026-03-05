"""
类型提示添加脚本
为弥娅核心模块添加完整的类型提示
"""
import ast
import re
import sys
from pathlib import Path
from typing import Set, List, Tuple, Dict
from core.constants import Encoding

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=Encoding.UTF8)

# 需要添加类型提示的函数/方法签名模式
FUNCTION_PATTERNS = [
    r'def\s+(\w+)\s*\([^)]*\)\s*(->)?\s*:',  # 无返回类型的函数
]

# 需要添加类型提示的参数名
PARAMETER_NAMES_TO_TYPE = {
    'self': None,  # self不需要类型提示
    'cls': None,  # cls不需要类型提示
    'args': 'tuple',
    'kwargs': 'dict',
    'value': 'Any',
    'key': 'str',
    'data': 'Dict[str, Any]',
    'result': 'str',
    'response': 'str',
    'message': 'str',
    'config': 'Dict[str, Any]',
    'options': 'List[Dict[str, Any]]',
    'context': 'Dict[str, Any]',
    'content': 'str',
    'prompt': 'str',
    'tool_name': 'str',
    'tool_args': 'Dict[str, Any]',
    'messages': 'List[Dict[str, str]]',
    'tools': 'Optional[List[Dict[str, Any]]]',
    'api_key': 'str',
    'model': 'str',
    'temperature': 'float',
    'max_tokens': 'int',
    'user_id': 'int',
    'group_id': 'int',
    'session_id': 'str',
    'memory_id': 'str',
    'vector': 'np.ndarray',
    'vectors': 'Dict[str, float]',
    'form': 'str',
    'title': 'str',
    'emotion': 'str',
    'emotion_state': 'str',
}

# 常见返回类型
RETURN_TYPES = {
    'get_': 'str',  # get_*方法通常返回str
    'set_': 'bool',  # set_*方法通常返回bool
    'is_': 'bool',  # is_*方法通常返回bool
    'has_': 'bool',  # has_*方法通常返回bool
    'load_': 'bool',  # load_*方法通常返回bool
    'save_': 'bool',  # save_*方法通常返回bool
    'create_': 'str',  # create_*方法通常返回str
    'delete_': 'bool',  # delete_*方法通常返回bool
    'update_': 'bool',  # update_*方法通常返回bool
    'find_': 'Optional[Dict[str, Any]]',  # find_*方法通常返回Optional[Dict]
    'search_': 'List[Dict[str, Any]]',  # search_*方法通常返回List[Dict]
    'list_': 'List[Dict[str, Any]]',  # list_*方法通常返回List[Dict]
    'execute': 'str',  # execute方法通常返回str
    'run': 'str',  # run方法通常返回str
    'process': 'str',  # process方法通常返回str
    'handle': 'str',  # handle方法通常返回str
    'calculate': 'float',  # calculate方法通常返回float
    'compute': 'float',  # compute方法通常返回float
    'parse': 'Dict[str, Any]',  # parse方法通常返回Dict
    'format': 'str',  # format方法通常返回str
    'convert': 'Any',  # convert方法返回值不确定
    'validate': 'Tuple[bool, Optional[str]]',  # validate方法通常返回Tuple[bool, Optional[str]]
    'check': 'bool',  # check方法通常返回bool
    'test': 'bool',  # test方法通常返回bool
    'init': 'None',  # init方法通常返回None
    'setup': 'bool',  # setup方法通常返回bool
    'cleanup': 'bool',  # cleanup方法通常返回bool
    'reset': 'bool',  # reset方法通常返回bool
}


def infer_parameter_type(param_name: str, default_value=None) -> str:
    """
    推断参数类型
    
    Args:
        param_name: 参数名
        default_value: 默认值（可选）
    
    Returns:
        类型字符串
    """
    # 从已知映射中查找
    if param_name in PARAMETER_NAMES_TO_TYPE and PARAMETER_NAMES_TO_TYPE[param_name]:
        return PARAMETER_NAMES_TO_TYPE[param_name]
    
    # 从默认值推断
    if default_value is not None:
        if default_value is True or default_value is False:
            return 'bool'
        elif isinstance(default_value, int):
            return 'int'
        elif isinstance(default_value, float):
            return 'float'
        elif isinstance(default_value, str):
            return 'str'
        elif isinstance(default_value, list):
            return 'List'
        elif isinstance(default_value, dict):
            return 'Dict'
        elif default_value is None:
            return 'Any'
    
    # 根据参数名推断
    if param_name.endswith('_id'):
        return 'str'
    elif param_name.endswith('_name'):
        return 'str'
    elif param_name.endswith('_list'):
        return 'List'
    elif param_name.endswith('_dict'):
        return 'Dict'
    elif param_name.endswith('_data'):
        return 'Dict[str, Any]'
    elif param_name.endswith('_count'):
        return 'int'
    elif param_name.endswith('_time'):
        return 'float'
    elif param_name.endswith('_enabled'):
        return 'bool'
    elif param_name.endswith('_status'):
        return 'str'
    elif param_name.endswith('_type'):
        return 'str'
    
    # 默认返回Any
    return 'Any'


def infer_return_type(func_name: str) -> str:
    """
    推断函数返回类型
    
    Args:
        func_name: 函数名
    
    Returns:
        返回类型字符串
    """
    # 根据函数名前缀推断
    for prefix, return_type in RETURN_TYPES.items():
        if func_name.startswith(prefix):
            return return_type
    
    # 特殊处理
    if func_name.startswith('__') and func_name.endswith('__'):
        if func_name == '__init__':
            return 'None'
        elif func_name == '__str__':
            return 'str'
        elif func_name == '__repr__':
            return 'str'
        elif func_name == '__len__':
            return 'int'
        elif func_name == '__getitem__':
            return 'Any'
    
    # 默认返回Any
    return 'Any'


def analyze_file(file_path: Path) -> List[Dict]:
    """
    分析Python文件，找出需要添加类型提示的函数/方法
    
    Args:
        file_path: Python文件路径
    
    Returns:
        需要添加类型提示的函数列表
    """
    try:
        with open(file_path, 'r', encoding=Encoding.UTF8) as f:
            source = f.read()
    except Exception:
        return []
    
    tree = ast.parse(source)
    functions_needing_types = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 检查是否已经有返回类型注解
            if node.returns is None:
                # 检查参数
                params_needing_types = []
                for arg in node.args.args:
                    if arg.arg == 'self' or arg.arg == 'cls':
                        continue
                    if arg.annotation is None:
                        # 尝试从默认值推断类型
                        default_value = None
                        for i, default in enumerate(node.args.defaults):
                            if len(node.args.args) - len(node.args.defaults) + i == node.args.args.index(arg):
                                try:
                                    default_value = ast.literal_eval(default)
                                except:
                                    pass
                        
                        param_type = infer_parameter_type(arg.arg, default_value)
                        params_needing_types.append({
                            'name': arg.arg,
                            'type': param_type
                        })
                
                if params_needing_types:
                    return_type = infer_return_type(node.name)
                    functions_needing_types.append({
                        'name': node.name,
                        'line': node.lineno,
                        'params': params_needing_types,
                        'return_type': return_type
                    })
    
    return functions_needing_types


def generate_type_suggestions(file_path: Path) -> List[str]:
    """
    生成类型提示建议
    
    Args:
        file_path: Python文件路径
    
    Returns:
        类型提示建议列表
    """
    functions = analyze_file(file_path)
    suggestions = []
    
    for func in functions:
        suggestion = f"\n# 函数: {func['name']} (行 {func['line']})\n"
        suggestion += f"def {func['name']}("
        
        param_suggestions = []
        for param in func['params']:
            param_suggestions.append(f"{param['name']}: {param['type']}")
        
        suggestion += ', '.join(param_suggestions)
        suggestion += f") -> {func['return_type']}:"
        suggestions.append(suggestion)
    
    return suggestions


def main():
    """主函数"""
    core_dir = Path(__file__).parent.parent / 'core'
    
    print("=" * 80)
    print("弥娅核心模块类型提示检查")
    print("=" * 80)
    
    total_files = 0
    total_functions = 0
    
    for py_file in core_dir.glob('*.py'):
        if py_file.name == '__init__.py':
            continue
        
        functions = analyze_file(py_file)
        if functions:
            print(f"\n📄 {py_file.name}:")
            print("-" * 80)
            
            suggestions = generate_type_suggestions(py_file)
            for suggestion in suggestions:
                print(suggestion)
            
            total_files += 1
            total_functions += len(functions)
    
    print("\n" + "=" * 80)
    print(f"总结: 找到 {total_files} 个文件中的 {total_functions} 个函数需要添加类型提示")
    print("=" * 80)


if __name__ == '__main__':
    main()
