"""
# TODO(cleanup): _init_deepseek / _init_siliconflow 各有两个定义，前一个会被后一个覆盖，后续应删除旧实现。
弥娅 - Embedding API 客户端
支持多种Embedding提供商
"""

import logging
from enum import Enum
from typing import List, Optional

from core.system_config import get_api_url

logger = logging.getLogger(__name__)


class EmbeddingProvider(Enum):
    """Embedding提供商"""

    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"
    SENTENCE_TRANSFORMERS = "sentence_transformers"  # 本地模型


class EmbeddingClient:
    """
    Embedding API 客户端

    支持的提供商：
    - OpenAI: text-embedding-3-small/large
    - DeepSeek: deepseek-embedding
    - SiliconFlow: 各种中文embedding模型
    - Sentence Transformers: 本地模型（无需API）
    """

    def __init__(
        self,
        provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化Embedding客户端

        Args:
            provider: Embedding提供商
            model: 模型名称（可选，使用默认模型）
            api_key: API密钥
            base_url: API基础URL（用于自定义端点）
            **kwargs: 其他参数
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

        # 模型必须由调用方指定，不再设置默认值
        if self.model is None:
            raise ValueError("[EmbeddingClient] model 参数必须提供，请检查 multi_model_config.json")

        logger.info(f"[EmbeddingClient] 初始化完成 - provider={provider.value}, model={self.model}")

    async def initialize(self):
        """初始化客户端"""
        try:
            if self.provider == EmbeddingProvider.OPENAI:
                await self._init_openai()
            elif self.provider == EmbeddingProvider.DEEPSEEK:
                await self._init_deepseek()
            elif self.provider == EmbeddingProvider.SILICONFLOW:
                await self._init_siliconflow()
            elif self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                await self._init_sentence_transformers()
            else:
                raise ValueError(f"不支持的provider: {self.provider}")

            logger.info(f"[EmbeddingClient] {self.provider.value} 客户端初始化成功")
        except Exception as e:
            logger.error(f"[EmbeddingClient] 客户端初始化失败: {e}")
            raise

    async def _init_openai(self):
        """初始化OpenAI客户端"""
        try:
            from openai import AsyncOpenAI

            if not self.base_url:
                raise ValueError("[EmbeddingClient] OpenAI base_url 必须提供")
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_deepseek(self):
        """初始化DeepSeek客户端"""
        try:
            from openai import AsyncOpenAI

            if not self.base_url:
                raise ValueError("[EmbeddingClient] DeepSeek base_url 必须提供")
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_siliconflow(self):
        """初始化硅基流动客户端"""
        try:
            from openai import AsyncOpenAI

            if not self.base_url:
                raise ValueError("[EmbeddingClient] SiliconFlow base_url 必须提供")
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_deepseek(self):
        """初始化DeepSeek客户端"""
        try:
            from openai import AsyncOpenAI

            # DeepSeek使用OpenAI兼容的API
            base_url = self.base_url or get_api_url("deepseek")
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_siliconflow(self):
        """初始化硅基流动客户端"""
        try:
            from openai import AsyncOpenAI

            # 硅基流动使用OpenAI兼容的API
            base_url = self.base_url or get_api_url("siliconflow")
            self._client = AsyncOpenAI(api_key=self.api_key, base_url=base_url)
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_sentence_transformers(self):
        """初始化Sentence Transformers（本地模型）"""
        try:
            from sentence_transformers import SentenceTransformer

            # 同步加载模型
            self._client = SentenceTransformer(self.model)
            logger.info(f"[EmbeddingClient] Sentence Transformers模型加载完成: {self.model}")
        except ImportError:
            raise ImportError("请安装sentence-transformers包: pip install sentence-transformers")

    async def embed(self, text: str) -> List[float]:
        """
        生成文本的向量嵌入

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        if not text or not text.strip():
            logger.warning("[EmbeddingClient] 输入文本为空")
            return []

        # 确保客户端已初始化
        if self._client is None:
            await self.initialize()

        import os

        try:
            if self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                # 本地模型（同步）- 检测CUDA兼容性
                import torch

                # 检查环境变量，强制使用CPU
                force_cpu = os.environ.get("MIYA_FORCE_CPU", "true").lower() == "true"

                device = "cpu"
                if not force_cpu and torch.cuda.is_available():
                    try:
                        # 检测 compute capability
                        cap = torch.cuda.get_device_capability(0)
                        # 支持 sm_50 到 sm_120 (RTX 50系列)
                        if cap[0] >= 5:
                            device = "cuda"
                        else:
                            logger.warning(f"[Embedding] GPU compute capability {cap} not supported, using CPU")
                    except Exception as e:
                        logger.warning(f"[Embedding] GPU detection failed: {e}, using CPU")
                vector = self._client.encode(text, convert_to_numpy=True, device=device)
                return vector.tolist()
            else:
                # API调用（异步）
                response = await self._client.embeddings.create(model=self.model, input=text)
                return response.data[0].embedding

        except Exception as e:
            logger.error(f"[EmbeddingClient] Embedding生成失败: {e}")
            # 如果CUDA失败，重试使用CPU
            if self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                try:
                    vector = self._client.encode(text, convert_to_numpy=True, device="cpu")
                    logger.warning("[EmbeddingClient] 使用CPU重新生成向量成功")
                    return vector.tolist()
                except:
                    pass
            raise

    async def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        批量生成向量嵌入

        Args:
            texts: 输入文本列表
            batch_size: 批量大小

        Returns:
            向量列表
        """
        if not texts:
            return []

        # 确保客户端已初始化
        if self._client is None:
            await self.initialize()

        import os

        vectors = []

        try:
            if self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                # 本地模型支持批量处理 - 检测CUDA兼容性
                import torch

                # 检查环境变量，强制使用CPU
                force_cpu = os.environ.get("MIYA_FORCE_CPU", "true").lower() == "true"

                device = "cpu"
                if not force_cpu and torch.cuda.is_available():
                    try:
                        cap = torch.cuda.get_device_capability(0)
                        if cap[0] >= 5:
                            device = "cuda"
                    except:
                        pass
                vectors_batch = self._client.encode(texts, convert_to_numpy=True, device=device)
                vectors = [v.tolist() for v in vectors_batch]
            else:
                # API批量调用
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    response = await self._client.embeddings.create(model=self.model, input=batch)
                    batch_vectors = [item.embedding for item in response.data]
                    vectors.extend(batch_vectors)

            logger.info(f"[EmbeddingClient] 批量Embedding完成: {len(texts)} 条")
            return vectors

        except Exception as e:
            logger.error(f"[EmbeddingClient] 批量Embedding失败: {e}")
            raise

    def get_dimension(self) -> Optional[int]:
        """
        获取向量维度

        Returns:
            向量维度
        """
        dimensions = {
            EmbeddingProvider.OPENAI: {
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072,
                "text-embedding-ada-002": 1536,
            },
            EmbeddingProvider.DEEPSEEK: {"deepseek-embedding": 1536},
            EmbeddingProvider.SILICONFLOW: {
                "BAAI/bge-large-zh-v1.5": 1024,
                "BAAI/bge-base-zh-v1.5": 768,
                "Qwen/Qwen3-VL-Embedding-8B": 4096,
            },
            EmbeddingProvider.SENTENCE_TRANSFORMERS: {"paraphrase-multilingual-MiniLM-L12-v2": 384},
        }

        provider_dims = dimensions.get(self.provider, {})
        return provider_dims.get(self.model)


# 全局单例
_global_embedding_client: Optional[EmbeddingClient] = None


async def get_embedding_client(
    provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> EmbeddingClient:
    """
    获取全局Embedding客户端（单例）

    Args:
        provider: Embedding提供商
        model: 模型名称
        api_key: API密钥
        base_url: API 基础 URL

    Returns:
        EmbeddingClient实例
    """
    global _global_embedding_client

    if _global_embedding_client is None:
        _global_embedding_client = EmbeddingClient(provider=provider, model=model, api_key=api_key, base_url=base_url)
        await _global_embedding_client.initialize()

    return _global_embedding_client


def reset_embedding_client():
    """重置Embedding客户端（主要用于测试）"""
    global _global_embedding_client
    _global_embedding_client = None
