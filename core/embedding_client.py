"""
弥娅 - Embedding API 客户端
支持多种Embedding提供商
"""
import logging
from typing import List, Optional
import asyncio
from enum import Enum

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
        **kwargs
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

        # 根据提供商设置默认模型
        if self.model is None:
            self.model = self._get_default_model()

        logger.info(
            f"[EmbeddingClient] 初始化完成 - "
            f"provider={provider.value}, model={self.model}"
        )

    def _get_default_model(self) -> str:
        """获取默认模型"""
        defaults = {
            EmbeddingProvider.OPENAI: "text-embedding-3-small",
            EmbeddingProvider.DEEPSEEK: "deepseek-embedding",
            EmbeddingProvider.SILICONFLOW: "BAAI/bge-large-zh-v1.5",
            EmbeddingProvider.SENTENCE_TRANSFORMERS: "paraphrase-multilingual-MiniLM-L12-v2"
        }
        return defaults.get(self.provider, "text-embedding-3-small")

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

            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_deepseek(self):
        """初始化DeepSeek客户端"""
        try:
            from openai import AsyncOpenAI

            # DeepSeek使用OpenAI兼容的API
            base_url = self.base_url or "https://api.deepseek.com"
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
        except ImportError:
            raise ImportError("请安装openai包: pip install openai")

    async def _init_siliconflow(self):
        """初始化硅基流动客户端"""
        try:
            from openai import AsyncOpenAI

            # 硅基流动使用OpenAI兼容的API
            base_url = self.base_url or "https://api.siliconflow.cn"
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
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

        try:
            if self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                # 本地模型（同步）- 强制使用CPU
                import torch
                device = 'cpu' if not torch.cuda.is_available() else 'cuda'
                vector = self._client.encode(text, convert_to_numpy=True, device=device)
                return vector.tolist()
            else:
                # API调用（异步）
                response = await self._client.embeddings.create(
                    model=self.model,
                    input=text
                )
                return response.data[0].embedding

        except Exception as e:
            logger.error(f"[EmbeddingClient] Embedding生成失败: {e}")
            # 如果CUDA失败，重试使用CPU
            if self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                try:
                    vector = self._client.encode(text, convert_to_numpy=True, device='cpu')
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

        vectors = []

        try:
            if self.provider == EmbeddingProvider.SENTENCE_TRANSFORMERS:
                # 本地模型支持批量处理
                vectors_batch = self._client.encode(texts, convert_to_numpy=True)
                vectors = [v.tolist() for v in vectors_batch]
            else:
                # API批量调用
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    response = await self._client.embeddings.create(
                        model=self.model,
                        input=batch
                    )
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
                "text-embedding-ada-002": 1536
            },
            EmbeddingProvider.DEEPSEEK: {
                "deepseek-embedding": 1536
            },
            EmbeddingProvider.SILICONFLOW: {
                "BAAI/bge-large-zh-v1.5": 1024,
                "BAAI/bge-base-zh-v1.5": 768
            },
            EmbeddingProvider.SENTENCE_TRANSFORMERS: {
                "paraphrase-multilingual-MiniLM-L12-v2": 384
            }
        }

        provider_dims = dimensions.get(self.provider, {})
        return provider_dims.get(self.model)


# 全局单例
_global_embedding_client: Optional[EmbeddingClient] = None


async def get_embedding_client(
    provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
    model: Optional[str] = None,
    api_key: Optional[str] = None
) -> EmbeddingClient:
    """
    获取全局Embedding客户端（单例）

    Args:
        provider: Embedding提供商
        model: 模型名称
        api_key: API密钥

    Returns:
        EmbeddingClient实例
    """
    global _global_embedding_client

    if _global_embedding_client is None:
        _global_embedding_client = EmbeddingClient(
            provider=provider,
            model=model,
            api_key=api_key
        )
        await _global_embedding_client.initialize()

    return _global_embedding_client


def reset_embedding_client():
    """重置Embedding客户端（主要用于测试）"""
    global _global_embedding_client
    _global_embedding_client = None
