"""
插件系统模块
包含插件加载、管理和执行功能
"""
import os
import importlib.util
import sys
import asyncio
import inspect
import re
from typing import Dict, Any, List
from pathlib import Path
import importlib
from functools import partial

from storage.bucket import BucketManager
from rule_engine.rule_engine import RuleEngine, Rule
from middleware.middleware import Middleware
from utils.logger import get_logger
from apscheduler.schedulers.background import BackgroundScheduler

# 定义核心文件的路径和名称
if getattr(sys, 'frozen', False):
    # 如果是打包后的环境，使用 sys._MEIPASS
    CORE_MIDDLEWARE_PATH = Path(sys._MEIPASS) / "middleware" / "middleware.py"
else:
    CORE_MIDDLEWARE_PATH = Path(__file__).parent.parent / "middleware" / "middleware.py"

CORE_MIDDLEWARE_NAME = "core_middleware"

class Plugin:
    """插件元数据类"""
    def __init__(self, name: str, module: Any, rules: List[Dict], is_loaded: bool = True, is_system: bool = False, file_path: str = None):
        self.name = name
        self.module = module
        self.description = getattr(module, '__description__', '无描述') if module else '核心中间件'
        self.version = getattr(module, '__version__', '1.0.0') if module else '核心'
        self.author = getattr(module, '__author__', '匿名作者') if module else '系统'
        
        # --- 新增：读取模块级别的权限和平台配置 ---
        self.is_admin = getattr(module, '__admin__', False) if module else False
        self.im_types = getattr(module, '__imType__', None) if module else None
        # ---------------------------------------
        
        self.is_system = is_system
        self.rules = rules
        self.is_loaded = is_loaded
        self.file_path = file_path

class PluginManager:
    """插件管理器"""
    def __init__(self, plugins_dir: str, bucket_manager: BucketManager, rule_engine: RuleEngine, middleware: Middleware, scheduler: BackgroundScheduler):
        self.plugins_dir = plugins_dir
        self.bucket_manager = bucket_manager
        self.rule_engine = rule_engine
        self.middleware = middleware
        self.scheduler = scheduler
        self.plugins: Dict[str, Plugin] = {}
        self.logger = get_logger("plugin_manager")

        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)
        
        # 【增强】更健壮的依赖目录检测逻辑
        # 尝试多个可能的 plugins/lib 位置，只要存在就添加到 sys.path
        possible_lib_dirs = []
        
        # 1. 相对于当前文件 (__init__.py 在 plugins/ 目录下)
        # 这是最可靠的方法，因为 lib 通常就在 plugins/lib
        current_plugins_dir = os.path.dirname(os.path.abspath(__file__))
        possible_lib_dirs.append(os.path.join(current_plugins_dir, 'lib'))

        # 2. 相对于传入的 plugins_dir 参数
        if os.path.isabs(self.plugins_dir):
             possible_lib_dirs.append(os.path.join(self.plugins_dir, 'lib'))
        else:
             possible_lib_dirs.append(os.path.abspath(os.path.join(self.plugins_dir, 'lib')))

        # 3. 打包环境下的特殊路径
        if getattr(sys, 'frozen', False):
             possible_lib_dirs.append(os.path.join(os.path.dirname(sys.executable), 'plugins', 'lib'))

        # 去重并检查存在性
        added_paths = set()
        for lib_dir in possible_lib_dirs:
            if lib_dir in added_paths:
                continue
            
            if os.path.exists(lib_dir):
                if lib_dir not in sys.path:
                    sys.path.insert(0, lib_dir)
                    self.logger.info(f"已将外部依赖目录添加到 sys.path: {lib_dir}")
                added_paths.add(lib_dir)

        self.disabled_plugins_bucket = self.bucket_manager.get_sync('plugin_manager', 'disabled_plugins', default=[])

    async def load_all_plugins(self):
        """加载所有未被禁用的插件"""
        self.logger.info("开始加载所有插件...")
        if not os.path.exists(self.plugins_dir):
            self.logger.warning(f"插件目录 {self.plugins_dir} 不存在，跳过加载外部插件。")
            return

        tasks = []
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                plugin_name = filename[:-3]
                if plugin_name in self.disabled_plugins_bucket:
                    self.logger.info(f"插件 {plugin_name} 已被禁用，跳过加载。")
                    continue
                tasks.append(self.load_plugin(plugin_name))
        await asyncio.gather(*tasks)
        self.logger.info("所有插件加载完毕。")

    async def load_plugin(self, name: str) -> bool:
        """加载单个插件"""
        if name in self.plugins and self.plugins[name].is_loaded:
            self.logger.warning(f"插件 {name} 已经加载。")
            return True

        try:
            plugin_path = os.path.join(self.plugins_dir, f"{name}.py")
            spec = importlib.util.spec_from_file_location(name, plugin_path)
            module = importlib.util.module_from_spec(spec)

            if name in sys.modules:
                module = importlib.reload(sys.modules[name])
            else:
                spec.loader.exec_module(module)
                sys.modules[name] = module

            # --- 读取插件元数据 ---
            is_admin = getattr(module, '__admin__', False)
            im_types = getattr(module, '__imType__', None)
            if isinstance(im_types, str):
                im_types = [t.strip() for t in im_types.split(',')]
            
            # 将元数据传递给 middleware
            self.middleware.set_plugin_metadata(name, is_admin=is_admin, im_types=im_types)
            # -------------------

            if hasattr(module, 'register') and callable(getattr(module, 'register')):
                register_func = getattr(module, 'register')
                
                # --- 关键修改：猴子补丁 middleware ---
                original_register_handler = self.middleware.register_message_handler
                # 使用 partial 创建一个预先填充了 plugin_name 参数的新函数
                self.middleware.register_message_handler = partial(original_register_handler, plugin_name=name)
                
                try:
                    sig = inspect.signature(register_func)
                    num_params = len(sig.parameters)

                    if num_params == 1:
                        register_func(self.middleware)
                    elif num_params == 2:
                        register_func(self.middleware, self.scheduler)
                    else:
                        self.logger.warning(f"插件 {name} 的 register 函数有 {num_params} 个参数，无法确定如何调用。")
                    self.logger.info(f"为插件 {name} 调用了 register 函数。")
                finally:
                    # 恢复原始的 register_message_handler 方法
                    self.middleware.register_message_handler = original_register_handler

            rules = getattr(module, 'rules', [])
            is_system = getattr(module, '__system__', False)
            self.plugins[name] = Plugin(name, module, rules, is_system=is_system, file_path=plugin_path)
            await self._register_plugin_rules(name)

            self.logger.info(f"插件 {name} 加载成功。")
            return True
        except Exception as e:
            self.logger.error(f"加载插件 {name} 失败: {e}", exc_info=True)
            return False

    async def unload_plugin(self, name: str) -> bool:
        """卸载单个插件"""
        if name == CORE_MIDDLEWARE_NAME:
            self.logger.warning(f"核心中间件 {name} 不能被卸载。")
            return False

        plugin = self.get_plugin(name)
        if not plugin or not plugin.is_loaded:
            self.logger.warning(f"插件 {name} 未加载或已卸载。")
            return True

        if plugin.is_system:
            self.logger.warning(f"插件 {name} 是系统插件，不能卸载。")
            return False

        try:
            # --- 关键修改：注销消息处理器 ---
            self.middleware.unregister_message_handlers(name)

            if hasattr(plugin.module, 'unload'):
                unload_func = getattr(plugin.module, 'unload')
                sig = inspect.signature(unload_func)
                num_params = len(sig.parameters)
                if num_params == 0:
                    unload_func()
                elif num_params == 1:
                    unload_func(self.scheduler)

            await self._unregister_plugin_rules(name)

            self._deep_unload_module(plugin.module)

            del self.plugins[name]

            self.logger.info(f"插件 {name} 卸载成功。")
            return True
        except Exception as e:
            self.logger.error(f"卸载插件 {name} 失败: {e}", exc_info=True)
            return False

    def _deep_unload_module(self, module):
        """
        递归卸载模块及其所有子模块
        """
        name = module.__name__
        self.logger.debug(f"开始深度卸载模块: {name}")

        related_modules = {name}
        for mod_name, mod in sys.modules.items():
            if mod_name.startswith(name + '.'):
                related_modules.add(mod_name)

        for mod_name in sorted(list(related_modules), reverse=True):
            if mod_name in sys.modules:
                try:
                    del sys.modules[mod_name]
                    self.logger.debug(f"已从 sys.modules 中移除: {mod_name}")
                except KeyError:
                    pass

    async def reload_plugin(self, name: str) -> bool:
        """重新加载插件"""
        self.logger.info(f"正在重载插件 {name}...")

        if name == CORE_MIDDLEWARE_NAME:
            self.logger.warning(f"核心中间件 {name} 无法通过此方式重载，请重启应用。")
            return False

        importlib.invalidate_caches()

        if name in self.plugins:
            await self.unload_plugin(name)

        return await self.load_plugin(name)

    async def enable_plugin(self, name: str):
        """启用插件"""
        if name == CORE_MIDDLEWARE_NAME:
            return True

        if name in self.disabled_plugins_bucket:
            self.disabled_plugins_bucket.remove(name)
            await self.bucket_manager.set('plugin_manager', 'disabled_plugins', self.disabled_plugins_bucket)
            self.logger.info(f"插件 {name} 已从禁用列表移除。")
            return await self.load_plugin(name)
        self.logger.warning(f"插件 {name} 未被禁用。")
        return True

    async def disable_plugin(self, name: str):
        """禁用插件"""
        if name == CORE_MIDDLEWARE_NAME:
            self.logger.warning(f"核心中间件 {name} 不能被禁用。")
            return False

        plugin = self.get_plugin(name)
        if plugin and plugin.is_system:
            self.logger.warning(f"插件 {name} 是系统插件，不能禁用。")
            return False

        if name not in self.disabled_plugins_bucket:
            self.disabled_plugins_bucket.append(name)
            await self.bucket_manager.set('plugin_manager', 'disabled_plugins', self.disabled_plugins_bucket)
            self.logger.info(f"插件 {name} 已添加到禁用列表。")
            if name in self.plugins:
                return await self.unload_plugin(name)
            return True
        self.logger.warning(f"插件 {name} 已在禁用列表中。")
        return True

    def get_all_plugins(self) -> Dict[str, Plugin]:
        """获取所有已发现的插件，并确保is_system标志正确"""
        all_plugins_info = {}

        # 加载核心中间件
        try:
            if getattr(sys, 'frozen', False):
                # 打包环境下，直接导入
                import middleware.middleware as mw_module
                core_plugin = Plugin(name=CORE_MIDDLEWARE_NAME, module=mw_module, rules=[], is_loaded=True, is_system=True, file_path="internal")
            else:
                # 开发环境下，从文件加载
                spec = importlib.util.spec_from_file_location("middleware.middleware", CORE_MIDDLEWARE_PATH)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                core_plugin = Plugin(name=CORE_MIDDLEWARE_NAME, module=module, rules=[], is_loaded=True, is_system=True, file_path=str(CORE_MIDDLEWARE_PATH))
            
            core_plugin.enabled = True
            all_plugins_info[CORE_MIDDLEWARE_NAME] = core_plugin
        except Exception as e:
            self.logger.error(f"加载核心中间件失败: {e}")

        if os.path.exists(self.plugins_dir):
            for filename in os.listdir(self.plugins_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    plugin_name = filename[:-3]

                    if plugin_name in self.plugins:
                        plugin_obj = self.plugins[plugin_name]
                    else:
                        is_system = False
                        plugin_path = os.path.join(self.plugins_dir, filename)
                        try:
                            with open(plugin_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if re.search(r"^\s*__system__\s*=\s*True", content, re.MULTILINE):
                                    is_system = True
                            plugin_obj = Plugin(name=plugin_name, module=None, rules=[], is_loaded=False, is_system=is_system, file_path=plugin_path)
                        except Exception as e:
                            self.logger.error(f"扫描插件 {plugin_name} 元数据时出错: {e}")
                            plugin_obj = Plugin(name=plugin_name, module=None, rules=[], is_loaded=False, is_system=False, file_path=plugin_path)
                            plugin_obj.description = f"加载失败: {e}"

                    plugin_obj.enabled = self.is_plugin_enabled(plugin_name)
                    all_plugins_info[plugin_name] = plugin_obj

        return all_plugins_info

    def get_plugin(self, name: str) -> Plugin:
        """获取单个插件，无论是已加载还是仅在磁盘上"""
        if name == CORE_MIDDLEWARE_NAME:
            try:
                if getattr(sys, 'frozen', False):
                    import middleware.middleware as mw_module
                    return Plugin(name=CORE_MIDDLEWARE_NAME, module=mw_module, rules=[], is_loaded=True, is_system=True, file_path="internal")
                else:
                    spec = importlib.util.spec_from_file_location("middleware.middleware", CORE_MIDDLEWARE_PATH)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return Plugin(name=CORE_MIDDLEWARE_NAME, module=module, rules=[], is_loaded=True, is_system=True, file_path=str(CORE_MIDDLEWARE_PATH))
            except Exception as e:
                self.logger.error(f"获取核心中间件失败: {e}")
                return None

        if name in self.plugins:
            return self.plugins[name]

        plugin_path = os.path.join(self.plugins_dir, f"{name}.py")
        if os.path.exists(plugin_path):
            is_system = False
            try:
                with open(plugin_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if re.search(r"^\s*__system__\s*=\s*True", content, re.MULTILINE):
                        is_system = True
                return Plugin(name=name, module=None, rules=[], is_loaded=False, is_system=is_system, file_path=plugin_path)
            except Exception as e:
                self.logger.error(f"获取插件 {name} 元数据时出错: {e}")
        return None

    def is_plugin_enabled(self, name: str) -> bool:
        if name == CORE_MIDDLEWARE_NAME:
            return True
        return name not in self.disabled_plugins_bucket

    async def _register_plugin_rules(self, plugin_name: str):
        plugin = self.plugins.get(plugin_name)
        if not plugin or not plugin.is_loaded: return
        for rule_dict in plugin.rules:
            rule_name = f"{plugin_name}.{rule_dict['name']}"
            
            extra_kwargs = {}
            
            # --- 优先级逻辑：规则级配置 > 插件级配置 ---
            
            # 1. 管理员权限
            if "__admin__" in rule_dict:
                extra_kwargs["is_admin"] = rule_dict["__admin__"]
            elif plugin.is_admin:
                extra_kwargs["is_admin"] = True
            
            # 2. IM 平台白名单
            im_types_val = None
            if "__imType__" in rule_dict:
                im_types_val = rule_dict["__imType__"]
            elif plugin.im_types:
                im_types_val = plugin.im_types
            
            if im_types_val:
                if isinstance(im_types_val, str):
                    extra_kwargs["im_types"] = [t.strip() for t in im_types_val.split(',')]
                else:
                    extra_kwargs["im_types"] = im_types_val
            
            rule = Rule(
                name=rule_name, 
                pattern=rule_dict["pattern"], 
                handler=rule_dict["handler"], 
                rule_type=rule_dict.get("rule_type", "regex"), 
                priority=rule_dict.get("priority", 0), 
                description=rule_dict.get("description", ""), 
                source='plugin',
                **extra_kwargs # 传递额外参数
            )
            await self.rule_engine.add_rule(rule)
        self.logger.debug(f"为插件 {plugin_name} 注册了 {len(plugin.rules)} 条规则。")

    async def _unregister_plugin_rules(self, plugin_name: str):
        rules_to_remove = [rule for rule in self.rule_engine.rules if rule.name.startswith(f"{plugin_name}.")]
        tasks = [self.rule_engine.remove_rule(rule.name) for rule in rules_to_remove]
        await asyncio.gather(*tasks)
        self.logger.debug(f"为插件 {plugin_name} 注销了 {len(rules_to_remove)} 条规则。")
