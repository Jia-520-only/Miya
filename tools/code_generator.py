"""
代码生成器工具
支持生成多种类型的代码模板和实际代码
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeGenerator:
    """代码生成器主类"""

    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化代码生成器

        Args:
            template_dir: 模板目录路径
        """
        self.template_dir = template_dir or os.path.join(os.path.dirname(__file__), "templates")

    def generate_rest_api(self, spec: Dict[str, Any]) -> str:
        """
        生成REST API代码

        Args:
            spec: API规范，包含endpoints, base_path, version等

        Returns:
            生成的API代码
        """
        template = """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

app = FastAPI(
    title="{title}",
    version="{version}",
    description="{description}"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port={port})
""".format(
            title=spec.get('title', 'API'),
            version=spec.get('version', '1.0.0'),
            description=spec.get('description', ''),
            port=spec.get('port', 8000)
        )
        return template

    def generate_code_from_spec(self, spec_type: str, spec: Dict[str, Any]) -> str:
        """
        根据规范生成代码

        Args:
            spec_type: 规范类型 (rest_api, database, test, class, cli, dockerfile)
            spec: 规范数据

        Returns:
            生成的代码
        """
        if spec_type == 'rest_api':
            return self.generate_rest_api(spec)
        else:
            raise ValueError(f"不支持的规范类型: {spec_type}")


if __name__ == "__main__":
    # 示例使用
    generator = CodeGenerator()
    spec = {
        'title': '示例API',
        'version': '1.0.0',
        'description': '示例API描述',
        'port': 8000
    }
    print(generator.generate_rest_api(spec))
