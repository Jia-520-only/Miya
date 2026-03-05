"""
EntertainmentNet - 娱乐子网

> 提供QQ机器人娱乐功能
>
> 功能：
> - QQ点赞
> - 星座运势
> - 占卜抽签
> - 戳一戳
> - 表情回应
>
> 参考文档: docs/ARCHITECTURE_OVERVIEW.md
"""
from .subnet import EntertainmentSubnet


__all__ = ['EntertainmentSubnet']


def get_entertainment_subnet(**kwargs) -> EntertainmentSubnet:
    """获取娱乐子网实例

    Args:
        **kwargs: 子网初始化参数

    Returns:
        EntertainmentSubnet 实例
    """
    return EntertainmentSubnet(**kwargs)
