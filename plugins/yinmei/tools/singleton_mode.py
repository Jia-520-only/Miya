def singleton(cls):
    """单例装饰器 (线程安全)"""
    _instances = {}

    def wrapper(*args, **kwargs):
        if cls not in _instances:
            _instances[cls] = cls(*args, **kwargs)
        return _instances[cls]

    return wrapper
