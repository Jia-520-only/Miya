"""
测试用例生成器工具
自动生成单元测试、集成测试和端到端测试用例
"""

import ast
import inspect
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import importlib.util

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """测试用例"""
    name: str
    description: str
    function_name: str
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    expected_output: Any = None
    expected_exception: Optional[str] = None
    setup_code: Optional[str] = None
    teardown_code: Optional[str] = None
    test_type: str = 'unit'  # unit, integration, e2e


@dataclass
class TestSuite:
    """测试套件"""
    name: str
    description: str
    test_cases: List[TestCase] = field(default_factory=list)
    setup_code: Optional[str] = None
    teardown_code: Optional[str] = None


class TestCaseGenerator:
    """测试用例生成器"""

    def __init__(self):
        self.generators = {
            'unit': self._generate_unit_test,
            'integration': self._generate_integration_test,
            'e2e': self._generate_e2e_test,
            'api': self._generate_api_test,
            'database': self._generate_database_test
        }

    def generate_from_function(self, func: Callable, test_type: str = 'unit') -> TestSuite:
        """
        从函数生成测试用例

        Args:
            func: 要测试的函数
            test_type: 测试类型

        Returns:
            测试套件
        """
        func_info = self._extract_function_info(func)

        test_suite = TestSuite(
            name=f"{func.__name__}_test_suite",
            description=f"{func.__name__}的测试套件"
        )

        # 基于函数签名生成测试用例
        test_cases = self._generate_test_cases_from_signature(func, func_info)

        for test_case in test_cases:
            test_case.test_type = test_type
            test_suite.test_cases.append(test_case)

        return test_suite

    def generate_from_class(self, cls: type) -> TestSuite:
        """
        从类生成测试用例

        Args:
            cls: 要测试的类

        Returns:
            测试套件
        """
        test_suite = TestSuite(
            name=f"{cls.__name__}_test_suite",
            description=f"{cls.__name__}的测试套件"
        )

        # 为每个公共方法生成测试用例
        for name, method in inspect.getmembers(cls, inspect.isfunction):
            if not name.startswith('_'):
                func_suite = self.generate_from_function(method)
                test_suite.test_cases.extend(func_suite.test_cases)

        return test_suite

    def generate_from_module(self, module_path: str) -> List[TestSuite]:
        """
        从模块生成测试用例

        Args:
            module_path: 模块文件路径

        Returns:
            测试套件列表
        """
        spec = importlib.util.spec_from_file_location("module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        test_suites = []

        # 为每个函数生成测试用例
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith('_'):
                test_suite = self.generate_from_function(obj)
                test_suites.append(test_suite)

        # 为每个类生成测试用例
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not name.startswith('_'):
                test_suite = self.generate_from_class(obj)
                test_suites.append(test_suite)

        return test_suites

    def _extract_function_info(self, func: Callable) -> Dict[str, Any]:
        """提取函数信息"""
        sig = inspect.signature(func)

        info = {
            'name': func.__name__,
            'docstring': inspect.getdoc(func) or '',
            'parameters': [],
            'return_annotation': sig.return_annotation,
            'is_async': inspect.iscoroutinefunction(func)
        }

        for param_name, param in sig.parameters.items():
            param_info = {
                'name': param_name,
                'type': param.annotation,
                'default': param.default if param.default != inspect.Parameter.empty else None
            }
            info['parameters'].append(param_info)

        return info

    def _generate_test_cases_from_signature(self, func: Callable, func_info: Dict) -> List[TestCase]:
        """
        基于函数签名生成测试用例

        Args:
            func: 函数
            func_info: 函数信息

        Returns:
            测试用例列表
        """
        test_cases = []

        # 正常情况测试
        test_cases.append(self._create_normal_test_case(func_info))

        # 边界情况测试
        test_cases.extend(self._create_boundary_test_cases(func_info))

        # 异常情况测试
        test_cases.extend(self._create_exception_test_cases(func_info))

        return test_cases

    def _create_normal_test_case(self, func_info: Dict) -> TestCase:
        """创建正常测试用例"""
        inputs = []
        for param in func_info['parameters']:
            inputs.append({
                'name': param['name'],
                'value': self._get_default_value(param['type'])
            })

        return TestCase(
            name=f"test_{func_info['name']}_normal",
            description=f"测试{func_info['name']}的正常执行",
            function_name=func_info['name'],
            inputs=inputs,
            expected_output=None  # 用户需要手动设置
        )

    def _create_boundary_test_cases(self, func_info: Dict) -> List[TestCase]:
        """创建边界测试用例"""
        test_cases = []

        # 空值测试
        test_cases.append(TestCase(
            name=f"test_{func_info['name']}_empty",
            description=f"测试{func_info['name']}的空值输入",
            function_name=func_info['name'],
            inputs=[{
                'name': param['name'],
                'value': self._get_empty_value(param['type'])
            } for param in func_info['parameters']],
            expected_exception=None
        ))

        # 最小值/最大值测试
        test_cases.append(TestCase(
            name=f"test_{func_info['name']}_boundary",
            description=f"测试{func_info['name']}的边界值",
            function_name=func_info['name'],
            inputs=[{
                'name': param['name'],
                'value': self._get_boundary_value(param['type'])
            } for param in func_info['parameters']],
            expected_output=None
        ))

        return test_cases

    def _create_exception_test_cases(self, func_info: Dict) -> List[TestCase]:
        """创建异常测试用例"""
        test_cases = []

        # 无效类型测试
        test_cases.append(TestCase(
            name=f"test_{func_info['name']}_invalid_type",
            description=f"测试{func_info['name']}的无效类型输入",
            function_name=func_info['name'],
            inputs=[{
                'name': param['name'],
                'value': 'invalid'
            } for param in func_info['parameters']],
            expected_exception='TypeError'
        ))

        return test_cases

    def _get_default_value(self, type_annotation: Any) -> Any:
        """获取默认值"""
        if type_annotation == int:
            return 1
        elif type_annotation == float:
            return 1.0
        elif type_annotation == str:
            return "test"
        elif type_annotation == bool:
            return True
        elif type_annotation == list:
            return []
        elif type_annotation == dict:
            return {}
        else:
            return None

    def _get_empty_value(self, type_annotation: Any) -> Any:
        """获取空值"""
        if type_annotation == int:
            return 0
        elif type_annotation == float:
            return 0.0
        elif type_annotation == str:
            return ""
        elif type_annotation == bool:
            return False
        elif type_annotation == list:
            return []
        elif type_annotation == dict:
            return {}
        else:
            return None

    def _get_boundary_value(self, type_annotation: Any) -> Any:
        """获取边界值"""
        if type_annotation == int:
            return 999999999
        elif type_annotation == float:
            return 999999.999
        elif type_annotation == str:
            return "a" * 1000
        elif type_annotation == list:
            return list(range(100))
        elif type_annotation == dict:
            return {str(i): i for i in range(100)}
        else:
            return None

    def _generate_unit_test(self, test_suite: TestSuite) -> str:
        """生成单元测试代码"""
        code = f'''"""
{test_suite.description}
自动生成的单元测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# TODO: 导入要测试的模块
# from your_module import {test_suite.test_cases[0].function_name if test_suite.test_cases else 'your_function'}


class {test_suite.name.replace(' ', '_')}:
    """
    {test_suite.name}
    """

    {f'{test_suite.setup_code}' if test_suite.setup_code else ''}

    {chr(10).join([self._generate_test_case_code(test_case) for test_case in test_suite.test_cases])}

    {f'{test_suite.teardown_code}' if test_suite.teardown_code else ''}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return code

    def _generate_integration_test(self, test_suite: TestSuite) -> str:
        """生成集成测试代码"""
        code = f'''"""
{test_suite.description}
自动生成的集成测试
"""

import pytest
import asyncio
from unittest.mock import AsyncMock


class {test_suite.name.replace(' ', '_')}_Integration:
    """
    集成测试 - 测试组件间的交互
    """

    @pytest.fixture(autouse=True)
    async def setup(self):
        """
        设置测试环境
        """
        # TODO: 初始化数据库、服务等
        pass

    @pytest.fixture(autouse=True)
    async def teardown(self):
        """
        清理测试环境
        """
        yield
        # TODO: 清理数据库、关闭服务等
        pass

    {chr(10).join([self._generate_integration_test_case_code(test_case) for test_case in test_suite.test_cases])}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return code

    def _generate_e2e_test(self, test_suite: TestSuite) -> str:
        """生成端到端测试代码"""
        code = f'''"""
{test_suite.description}
自动生成的端到端测试
"""

import pytest
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class {test_suite.name.replace(' ', '_')}_E2E:
    """
    端到端测试 - 测试完整的用户流程
    """

    @pytest.fixture(autouse=True)
    def browser(self):
        """
        初始化浏览器
        """
        # TODO: 根据需要配置浏览器
        driver = webdriver.Chrome()
        driver.implicitly_wait(10)
        yield driver
        driver.quit()

    {chr(10).join([self._generate_e2e_test_case_code(test_case) for test_case in test_suite.test_cases])}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return code

    def _generate_api_test(self, test_suite: TestSuite) -> str:
        """生成API测试代码"""
        code = f'''"""
{test_suite.description}
自动生成的API测试
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

# TODO: 导入你的FastAPI应用
# from your_app import app


class {test_suite.name.replace(' ', '_')}_API:
    """
    API测试
    """

    @pytest.fixture(autouse=True)
    def client(self):
        """
        测试客户端
        """
        # TODO: 配置测试客户端
        client = TestClient(app)
        return client

    {chr(10).join([self._generate_api_test_case_code(test_case) for test_case in test_suite.test_cases])}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return code

    def _generate_database_test(self, test_suite: TestSuite) -> str:
        """生成数据库测试代码"""
        code = f'''"""
{test_suite.description}
自动生成的数据库测试
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# TODO: 导入你的模型
# from your_models import Base, YourModel


class {test_suite.name.replace(' ', '_')}_Database:
    """
    数据库测试
    """

    @pytest.fixture(autouse=True)
    def db_session(self):
        """
        测试数据库会话
        """
        # TODO: 配置测试数据库
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        session = SessionLocal()
        yield session
        session.close()

    {chr(10).join([self._generate_database_test_case_code(test_case) for test_case in test_suite.test_cases])}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return code

    def _generate_test_case_code(self, test_case: TestCase) -> str:
        """生成测试用例代码"""
        param_str = ', '.join([f"{p['name']}={p['value']}" for p in test_case.inputs])

        code = f'''    def {test_case.name}(self):
        """
        {test_case.description}
        """
        # TODO: 导入要测试的函数
        result = {test_case.function_name}({param_str})

        # TODO: 根据实际情况修改断言
        assert result is not None

'''

        if test_case.expected_exception:
            code = f'''    def {test_case.name}(self):
        """
        {test_case.description}
        """
        with pytest.raises({test_case.expected_exception}):
            # TODO: 导入要测试的函数
            result = {test_case.function_name}({param_str})

'''

        return code

    def _generate_integration_test_case_code(self, test_case: TestCase) -> str:
        """生成集成测试用例代码"""
        param_str = ', '.join([f"{p['name']}={p['value']}" for p in test_case.inputs])

        return f'''    async def {test_case.name}(self):
        """
        {test_case.description}
        """
        # TODO: 测试组件间的交互
        pass

'''

    def _generate_e2e_test_case_code(self, test_case: TestCase) -> str:
        """生成端到端测试用例代码"""
        return f'''    def {test_case.name}(self, browser):
        """
        {test_case.description}
        """
        # TODO: 实现端到端测试逻辑
        # browser.get("http://localhost:8000")
        # element = browser.find_element(By.ID, "submit")
        # element.click()
        pass

'''

    def _generate_api_test_case_code(self, test_case: TestCase) -> str:
        """生成API测试用例代码"""
        return f'''    def {test_case.name}(self, client):
        """
        {test_case.description}
        """
        # TODO: 实现API测试逻辑
        # response = client.get("/api/endpoint")
        # assert response.status_code == 200
        pass

'''

    def _generate_database_test_case_code(self, test_case: TestCase) -> str:
        """生成数据库测试用例代码"""
        return f'''    def {test_case.name}(self, db_session):
        """
        {test_case.description}
        """
        # TODO: 实现数据库测试逻辑
        # record = YourModel(field1="value1", field2="value2")
        # db_session.add(record)
        # db_session.commit()
        # assert record.id is not None
        pass

'''

    def generate_code(self, test_suite: TestSuite, test_type: str = 'unit') -> str:
        """
        生成测试代码

        Args:
            test_suite: 测试套件
            test_type: 测试类型

        Returns:
            测试代码
        """
        generator = self.generators.get(test_type, self._generate_unit_test)
        return generator(test_suite)

    def save_test_file(self, test_suite: TestSuite, output_path: str, test_type: str = 'unit') -> None:
        """
        保存测试文件

        Args:
            test_suite: 测试套件
            output_path: 输出文件路径
            test_type: 测试类型
        """
        code = self.generate_code(test_suite, test_type)

        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(code)

        logger.info(f"测试文件已保存到: {output_path}")


# 便捷函数
def generate_simple_test(func: Callable, output_path: str = None) -> TestSuite:
    """
    快速生成简单测试

    Args:
        func: 要测试的函数
        output_path: 输出路径

    Returns:
        测试套件
    """
    generator = TestCaseGenerator()
    test_suite = generator.generate_from_function(func)

    if output_path:
        generator.save_test_file(test_suite, output_path)

    return test_suite


def generate_api_test(api_spec: Dict[str, Any]) -> str:
    """
    根据API规范生成测试

    Args:
        api_spec: API规范

    Returns:
        测试代码
    """
    code = f'''"""
API测试 - {api_spec.get('title', 'API')}
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient


class APITests:
    """
    API测试套件
    """

    @pytest.fixture(autouse=True)
    def client(self):
        """
        测试客户端
        """
        from app import app
        return TestClient(app)

'''

    for endpoint in api_spec.get('endpoints', []):
        method = endpoint.get('method', 'GET').lower()
        path = endpoint.get('path', '/')
        func_name = f"test_{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"

        code += f'''    def {func_name}(self, client):
        """
        测试 {method.upper()} {path}
        """
        response = client.{method}("{path}")
        assert response.status_code in [200, 201]

'''

    code += '''
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''

    return code


if __name__ == "__main__":
    # 示例使用
    def example_function(a: int, b: int) -> int:
        """示例函数"""
        return a + b

    generator = TestCaseGenerator()
    test_suite = generator.generate_from_function(example_function)

    print("生成的测试用例:")
    for test_case in test_suite.test_cases:
        print(f"  - {test_case.name}: {test_case.description}")

    print("\n生成的测试代码:")
    code = generator.generate_code(test_suite, 'unit')
    print(code)
