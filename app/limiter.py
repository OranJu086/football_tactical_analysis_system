"""基于 slowapi 的按 IP 限流组件（仅 /api/analyze 使用）。"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 默认按客户端 IP 计数；具体限额在路由装饰器上注入
limiter = Limiter(key_func=get_remote_address)
