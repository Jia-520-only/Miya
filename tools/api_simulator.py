"""
API 模拟器工具
用于模拟HTTP API响应，支持自定义路由和响应数据
"""

import json
import re
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

logger = logging.getLogger(__name__)


@dataclass
class MockResponse:
    """模拟响应"""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=lambda: {
        'Content-Type': 'application/json'
    })
    body: Any = None
    delay: float = 0.0

    def to_http_response(self) -> bytes:
        """转换为HTTP响应"""
        if isinstance(self.body, (dict, list)):
            body_str = json.dumps(self.body, ensure_ascii=False)
        else:
            body_str = str(self.body)

        response = f"HTTP/1.1 {self.status_code} {self._get_status_message()}\r\n"
        for key, value in self.headers.items():
            response += f"{key}: {value}\r\n"
        response += f"\r\n{body_str}"
        return response.encode('utf-8')

    def _get_status_message(self) -> str:
        """获取状态消息"""
        messages = {
            200: 'OK',
            201: 'Created',
            204: 'No Content',
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            500: 'Internal Server Error',
            503: 'Service Unavailable'
        }
        return messages.get(self.status_code, 'Unknown')


@dataclass
class MockRoute:
    """模拟路由"""
    method: str
    path: str
    response: MockResponse
    path_params: Dict[str, str] = field(default_factory=dict)
    condition: Optional[Callable] = None
    call_count: int = 0

    def matches(self, method: str, path: str) -> bool:
        """
        检查是否匹配请求

        Args:
            method: HTTP方法
            path: 请求路径

        Returns:
            是否匹配
        """
        if method.upper() != self.method.upper():
            return False

        # 将路径模式转换为正则表达式
        pattern = self.path
        # 替换 {param} 为正则捕获组
        pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', pattern)
        pattern = '^' + pattern + '$'

        return bool(re.match(pattern, path))


class APISimulator:
    """API模拟器主类"""

    def __init__(self, host: str = 'localhost', port: int = 8888):
        """
        初始化API模拟器

        Args:
            host: 监听主机
            port: 监听端口
        """
        self.host = host
        self.port = port
        self.routes: List[MockRoute] = []
        self.global_headers: Dict[str, str] = {}
        self.global_delay: float = 0.0
        self.middleware: List[Callable] = []
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None

    def add_route(self, method: str, path: str, response: MockResponse) -> None:
        """
        添加路由

        Args:
            method: HTTP方法
            path: 路径模式
            response: 响应
        """
        route = MockRoute(method=method, path=path, response=response)
        self.routes.append(route)
        logger.info(f"添加路由: {method.upper()} {path}")

    def get(self, path: str, response: MockResponse) -> None:
        """添加GET路由"""
        self.add_route('GET', path, response)

    def post(self, path: str, response: MockResponse) -> None:
        """添加POST路由"""
        self.add_route('POST', path, response)

    def put(self, path: str, response: MockResponse) -> None:
        """添加PUT路由"""
        self.add_route('PUT', path, response)

    def delete(self, path: str, response: MockResponse) -> None:
        """添加DELETE路由"""
        self.add_route('DELETE', path, response)

    def add_json_response(self, method: str, path: str, data: Any,
                         status_code: int = 200, delay: float = 0.0) -> None:
        """
        添加JSON响应路由

        Args:
            method: HTTP方法
            path: 路径
            data: 响应数据
            status_code: 状态码
            delay: 延迟秒数
        """
        response = MockResponse(
            status_code=status_code,
            body=data,
            delay=delay
        )
        self.add_route(method, path, response)

    def add_error_response(self, method: str, path: str, status_code: int,
                         message: str = None) -> None:
        """
        添加错误响应路由

        Args:
            method: HTTP方法
            path: 路径
            status_code: 状态码
            message: 错误消息
        """
        body = {
            'error': True,
            'status_code': status_code,
            'message': message or self._get_error_message(status_code)
        }
        response = MockResponse(status_code=status_code, body=body)
        self.add_route(method, path, response)

    def add_conditional_route(self, method: str, path: str,
                             condition: Callable[[Dict], bool],
                             true_response: MockResponse,
                             false_response: MockResponse) -> None:
        """
        添加条件路由

        Args:
            method: HTTP方法
            path: 路径
            condition: 条件函数，接收请求字典，返回布尔值
            true_response: 条件为真时的响应
            false_response: 条件为假时的响应
        """
        route = MockRoute(method=method, path=path, response=true_response, condition=condition)
        self.routes.append(route)
        logger.info(f"添加条件路由: {method.upper()} {path}")

    def add_dynamic_route(self, method: str, path: str,
                          response_generator: Callable[[Dict], MockResponse]) -> None:
        """
        添加动态路由（响应由函数生成）

        Args:
            method: HTTP方法
            path: 路径
            response_generator: 响应生成函数
        """
        # 使用condition来捕获动态响应生成器
        def make_dynamic_response(req):
            return response_generator(req)

        response = MockResponse(status_code=200)
        self.middleware.append(make_dynamic_response)

    def load_from_config(self, config_path: str) -> None:
        """
        从配置文件加载路由

        Args:
            config_path: 配置文件路径
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 加载全局配置
            if 'global_headers' in config:
                self.global_headers.update(config['global_headers'])
            if 'global_delay' in config:
                self.global_delay = config['global_delay']

            # 加载路由
            for route_config in config.get('routes', []):
                response = MockResponse(
                    status_code=route_config.get('status_code', 200),
                    headers=route_config.get('headers', {}),
                    body=route_config.get('body', {}),
                    delay=route_config.get('delay', 0.0) + self.global_delay
                )
                self.add_route(
                    route_config['method'],
                    route_config['path'],
                    response
                )

            logger.info(f"从配置文件加载了 {len(config.get('routes', []))} 个路由")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise

    def save_config(self, config_path: str) -> None:
        """
        保存配置到文件

        Args:
            config_path: 配置文件路径
        """
        try:
            config = {
                'global_headers': self.global_headers,
                'global_delay': self.global_delay,
                'routes': []
            }

            for route in self.routes:
                config['routes'].append({
                    'method': route.method,
                    'path': route.path,
                    'status_code': route.response.status_code,
                    'headers': route.response.headers,
                    'body': route.response.body,
                    'delay': route.response.delay
                })

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            logger.info(f"配置已保存到: {config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise

    def find_route(self, method: str, path: str) -> Optional[MockRoute]:
        """
        查找匹配的路由

        Args:
            method: HTTP方法
            path: 请求路径

        Returns:
            匹配的路由，如果没有则返回None
        """
        for route in self.routes:
            if route.matches(method, path):
                return route
        return None

    def handle_request(self, method: str, path: str, headers: Dict[str, str],
                      body: Any = None, query_params: Dict[str, List[str]] = None) -> MockResponse:
        """
        处理请求

        Args:
            method: HTTP方法
            path: 请求路径
            headers: 请求头
            body: 请求体
            query_params: 查询参数

        Returns:
            模拟响应
        """
        # 应用中间件
        request = {
            'method': method,
            'path': path,
            'headers': headers,
            'body': body,
            'query_params': query_params or {}
        }

        for middleware in self.middleware:
            result = middleware(request)
            if isinstance(result, MockResponse):
                return result

        # 查找匹配的路由
        route = self.find_route(method, path)

        if not route:
            return MockResponse(
                status_code=404,
                body={'error': 'Not Found', 'message': f'Route not found: {method} {path}'}
            )

        # 检查条件
        if route.condition and not route.condition(request):
            return MockResponse(
                status_code=400,
                body={'error': 'Bad Request', 'message': 'Condition not met'}
            )

        # 更新调用计数
        route.call_count += 1

        # 延迟响应
        if route.response.delay > 0:
            time.sleep(route.response.delay)

        # 添加全局头部
        response = MockResponse(
            status_code=route.response.status_code,
            headers={**self.global_headers, **route.response.headers},
            body=route.response.body,
            delay=route.response.delay
        )

        return response

    def get_call_count(self, method: str, path: str) -> int:
        """
        获取路由调用次数

        Args:
            method: HTTP方法
            path: 路径

        Returns:
            调用次数
        """
        route = self.find_route(method, path)
        return route.call_count if route else 0

    def reset_call_counts(self) -> None:
        """重置所有路由的调用计数"""
        for route in self.routes:
            route.call_count = 0

    def get_route_list(self) -> List[Dict[str, Any]]:
        """
        获取路由列表

        Returns:
            路由信息列表
        """
        return [
            {
                'method': route.method,
                'path': route.path,
                'call_count': route.call_count,
                'status_code': route.response.status_code
            }
            for route in self.routes
        ]

    def start(self, block: bool = False) -> None:
        """
        启动API模拟服务器

        Args:
            block: 是否阻塞主线程
        """
        class RequestHandler(BaseHTTPRequestHandler):
            simulator = self

            def _set_response(self, response: MockResponse):
                """设置响应"""
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()

                if isinstance(response.body, (dict, list)):
                    body_str = json.dumps(response.body, ensure_ascii=False)
                else:
                    body_str = str(response.body)

                self.wfile.write(body_str.encode('utf-8'))

            def do_GET(self):
                """处理GET请求"""
                parsed_url = urlparse(self.path)
                query_params = parse_qs(parsed_url.query)

                response = self.simulator.handle_request(
                    'GET',
                    parsed_url.path,
                    dict(self.headers),
                    None,
                    query_params
                )
                self._set_response(response)

            def do_POST(self):
                """处理POST请求"""
                parsed_url = urlparse(self.path)
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)

                try:
                    body_data = json.loads(body.decode('utf-8'))
                except:
                    body_data = body.decode('utf-8')

                response = self.simulator.handle_request(
                    'POST',
                    parsed_url.path,
                    dict(self.headers),
                    body_data
                )
                self._set_response(response)

            def do_PUT(self):
                """处理PUT请求"""
                parsed_url = urlparse(self.path)
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)

                try:
                    body_data = json.loads(body.decode('utf-8'))
                except:
                    body_data = body.decode('utf-8')

                response = self.simulator.handle_request(
                    'PUT',
                    parsed_url.path,
                    dict(self.headers),
                    body_data
                )
                self._set_response(response)

            def do_DELETE(self):
                """处理DELETE请求"""
                parsed_url = urlparse(self.path)

                response = self.simulator.handle_request(
                    'DELETE',
                    parsed_url.path,
                    dict(self.headers)
                )
                self._set_response(response)

            def log_message(self, format, *args):
                """自定义日志"""
                logger.info(f"{self.address_string()} - {format % args}")

        try:
            self.server = HTTPServer((self.host, self.port), RequestHandler)
            logger.info(f"API模拟器启动在 http://{self.host}:{self.port}")

            if block:
                self.server.serve_forever()
            else:
                self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                self.server_thread.start()
        except Exception as e:
            logger.error(f"启动API模拟器失败: {e}")
            raise

    def stop(self) -> None:
        """停止API模拟服务器"""
        if self.server:
            self.server.shutdown()
            logger.info("API模拟器已停止")

    def _get_error_message(self, status_code: int) -> str:
        """获取错误消息"""
        messages = {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            500: 'Internal Server Error',
            503: 'Service Unavailable'
        }
        return messages.get(status_code, 'Error')


class MockScenario:
    """模拟场景"""

    def __init__(self, name: str):
        self.name = name
        self.routes: List[Dict] = []

    def add_step(self, method: str, path: str, response: MockResponse) -> 'MockScenario':
        """添加场景步骤"""
        self.routes.append({
            'method': method,
            'path': path,
            'response': response
        })
        return self

    def apply_to(self, simulator: APISimulator) -> None:
        """将场景应用到模拟器"""
        for step in self.routes:
            simulator.add_route(
                step['method'],
                step['path'],
                step['response']
            )


# 便捷函数
def create_simple_api(port: int = 8888) -> APISimulator:
    """创建简单的API模拟器"""
    simulator = APISimulator(port=port)

    # 添加一些常用路由
    simulator.get('/', MockResponse(body={'message': 'Welcome to Mock API'}))
    simulator.get('/health', MockResponse(body={'status': 'healthy'}))
    simulator.post('/echo', MockResponse(body=lambda req: req['body']))

    return simulator


def create_rest_crud_api(port: int = 8888) -> APISimulator:
    """创建REST CRUD API模拟器"""
    simulator = APISimulator(port=port)

    # 示例数据
    items = {}

    # GET /items - 获取所有项目
    simulator.get('/items', MockResponse(body=list(items.values())))

    # GET /items/{id} - 获取单个项目
    simulator.get('/items/{id}', MockResponse(
        body=lambda req: items.get(req['path_params']['id'], {'error': 'Not found'})
    ))

    # POST /items - 创建项目
    def create_item(req):
        item_id = str(len(items) + 1)
        item = {'id': item_id, **req['body']}
        items[item_id] = item
        return MockResponse(status_code=201, body=item)

    # 使用动态路由需要更复杂的处理
    simulator.post('/items', MockResponse(
        body={'message': 'Item created'}
    ))

    return simulator


if __name__ == "__main__":
    # 示例使用
    simulator = APISimulator(port=8888)

    # 添加路由
    simulator.get('/api/users', MockResponse(body={
        'users': [
            {'id': 1, 'name': 'Alice'},
            {'id': 2, 'name': 'Bob'}
        ]
    }))

    simulator.get('/api/users/{id}', MockResponse(body={
        'id': 1, 'name': 'Alice'
    }))

    simulator.post('/api/users', MockResponse(
        status_code=201,
        body={'id': 3, 'name': 'New User'}
    ))

    # 启动服务器
    print("API模拟器启动在 http://localhost:8888")
    print("可用路由:")
    for route in simulator.get_route_list():
        print(f"  {route['method']} {route['path']}")

    try:
        simulator.start(block=True)
    except KeyboardInterrupt:
        print("\n停止服务器...")
        simulator.stop()
