"""
插件管理器
负责插件的加载、卸载、管理和执行
"""
import os
import sys
import importlib.util
import asyncio
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
import logging
from utils.logger import get_logger
__system__ = True

class Plugin:
    """
    插件类，封装单个插件的信息和功能
    """
    
    def __init__(self, name: str, module, file_path: str):
        """
        初始化插件
        :param name: 插件名称
        :param module: 插件模块
        :param file_path: 插件文件路径
        """
        self.name = name
        self.module = module
        self.file_path = file_path
        self.is_loaded = True
        self.rules = []  # 插件定义的规则列表
        self.logger = get_logger(f"plugin.{name}")
        
        # 尝试获取插件信息
        self.description = getattr(module, "__description__", "无描述")
        self.version = getattr(module, "__version__", "1.0.0")
        self.author = getattr(module, "__author__", "未知")
        self.is_system = getattr(module, "__system__", False)
        
        # 获取插件中定义的规则
        if hasattr(module, "rules"):
            self.rules = module.rules
        elif hasattr(module, "get_rules"):
            self.rules = module.get_rules()


class PluginManager:
    """
    插件管理器，负责插件的加载、卸载、管理和执行
    """
    
    def __init__(self, middleware, plugins_dir: str = "plugins"):
        """
        初始化插件管理器
        :param middleware: 中间件实例
        :param plugins_dir: 插件目录
        """
        self.middleware = middleware
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, Plugin] = {}
        self.logger = get_logger("plugin_manager")
        
    def load_plugin(self, plugin_name: str) -> bool:
        """
        加载单个插件
        :param plugin_name: 插件名称（不包含.py扩展名）
        :return: 是否加载成功
        """
        try:
            plugin_file = os.path.join(self.plugins_dir, f"{plugin_name}.py")
            
            if not os.path.exists(plugin_file):
                self.logger.error(f"插件文件不存在: {plugin_file}")
                return False
            
            # 动态导入插件模块
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            
            # 将middleware注入到模块的全局变量中
            module.middleware = self.middleware
            
            spec.loader.exec_module(module)
            
            # 创建插件实例
            plugin = Plugin(plugin_name, module, plugin_file)
            self.plugins[plugin_name] = plugin
            
            self.logger.info(f"插件 {plugin_name} 加载成功 - {plugin.description} (v{plugin.version} by {plugin.author})")
            return True
            
        except Exception as e:
            self.logger.error(f"加载插件 {plugin_name} 失败: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载单个插件
        :param plugin_name: 插件名称
        :return: 是否卸载成功
        """
        if plugin_name not in self.plugins:
            self.logger.warning(f"插件 {plugin_name} 未加载")
            return False

        if self.plugins[plugin_name].is_system:
            self.logger.warning(f"插件 {plugin_name} 是系统插件，不能卸载")
            return False
        
        try:
            plugin = self.plugins[plugin_name]
            
            # 如果插件有卸载函数，调用它
            if hasattr(plugin.module, "unload"):
                plugin.module.unload()
            
            # 从系统模块中删除插件
            module_name = plugin.module.__name__
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # 从插件管理器中删除插件
            del self.plugins[plugin_name]
            
            self.logger.info(f"插件 {plugin_name} 希载成功")
            return True
            
        except Exception as e:
            self.logger.error(f"卸载插件 {plugin_name} 失败: {e}")
            return False
    
    def load_all_plugins(self) -> int:
        """
        加载所有插件
        :return: 成功加载的插件数量
        """
        if not os.path.exists(self.plugins_dir):
            self.logger.warning(f"插件目录不存在: {self.plugins_dir}")
            return 0
        
        loaded_count = 0
        for file in os.listdir(self.plugins_dir):
            if file.endswith(".py") and not file.startswith("__"):
                plugin_name = file[:-3]  # 移除.py扩展名
                if self.load_plugin(plugin_name):
                    loaded_count += 1
        
        self.logger.info(f"插件加载完成，共加载 {loaded_count} 个插件")
        return loaded_count
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件
        :param plugin_name: 插件名称
        :return: 是否重新加载成功
        """
        if plugin_name in self.plugins and self.plugins[plugin_name].is_system:
            self.logger.warning(f"插件 {plugin_name} 是系统插件，不能重新加载")
            return False

        # Invalidate file system caches to ensure the latest code is loaded
        importlib.invalidate_caches()

        if plugin_name in self.plugins:
            self.unload_plugin(plugin_name)
        
        return self.load_plugin(plugin_name)
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """
        获取插件实例
        :param plugin_name: 插件名称
        :return: 插件实例或None
        """
        return self.plugins.get(plugin_name)
    
    def get_all_plugins(self) -> Dict[str, Plugin]:
        """
        获取所有插件
        :return: 插件字典
        """
        return self.plugins.copy()
    
    def get_plugin_rules(self) -> List[Dict[str, Any]]:
        """
        获取所有插件的规则
        :return: 规则列表
        """
        all_rules = []
        for plugin in self.plugins.values():
            all_rules.extend(plugin.rules)
        return all_rules
    
    def scan_plugins(self) -> List[str]:
        """
        扫描插件目录中的所有插件文件
        :return: 插件文件名列表（不含.py扩展名）
        """
        if not os.path.exists(self.plugins_dir):
            self.logger.warning(f"插件目录不存在: {self.plugins_dir}")
            return []
        
        plugin_files = []
        for file in os.listdir(self.plugins_dir):
            if file.endswith(".py") and not file.startswith("__"):
                plugin_name = file[:-3]  # 移除.py扩展名
                plugin_files.append(plugin_name)
        
        return plugin_files
    
    async def execute_plugin_function(self, plugin_name: str, function_name: str, *args, **kwargs):
        """
        执行插件中的特定函数
        :param plugin_name: 插件名称
        :param function_name: 函数名称
        :param args: 位置参数
        :param kwargs: 关键字参数
        :return: 函数执行结果
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            self.logger.error(f"插件 {plugin_name} 未加载")
            return None
        
        if not hasattr(plugin.module, function_name):
            self.logger.error(f"插件 {plugin_name} 中不存在函数 {function_name}")
            return None
        
        func = getattr(plugin.module, function_name)
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            return result
        except Exception as e:
            self.logger.error(f"执行插件 {plugin_name} 的函数 {function_name} 失败: {e}")
            return None
