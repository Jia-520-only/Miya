"""
TRPG 跑团子网 - 弥娅 TRPG 系统
支持 COC7、DND5E 等多种规则系统
"""

# 延迟导入，避免循环依赖
def get_trpg_net(mlink=None, ai_client=None, memory_engine=None):
    """获取 TRPG 子网实例"""
    from .subnet import TRPGNet
    return TRPGNet(mlink, ai_client, memory_engine)

__all__ = ['get_trpg_net']
