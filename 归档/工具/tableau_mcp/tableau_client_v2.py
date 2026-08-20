"""
Tableau Server REST API 客户端 v2 - 重构版本
采用模块化设计，职责分离，提高代码可维护性和可扩展性
"""

import io
import logging
import os
import xml.etree.cElementTree as ET
import zipfile
from typing import Optional, Callable, Tuple, Dict, Any, List
import time
import requests
import pandas as pd
from functools import wraps
import urllib.parse
import random
from datetime import datetime, timezone, timedelta
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== 配置管理模块 ====================

class ProductType(Enum):
    """产品类型枚举"""
    ARIES = "Aries"
    CLASSUP_OLD = "ClassUpOld"
    CLASSUP = "ClassUp"


class TableauConfig:
    """Tableau服务器配置"""
    
    def __init__(self, server_url: str, token_name: str, token_value: str, api_version: str = "3.17"):
        self.server_url = server_url
        self.token_name = token_name
        self.token_value = token_value
        self.api_version = api_version
    
    def __repr__(self):
        return f"TableauConfig(server_url='{self.server_url}', token_name='{self.token_name}', api_version='{self.api_version}')"


class ConfigManager:
    """配置管理器"""
    
    _configs = {
        ProductType.ARIES: TableauConfig(
            server_url="http://10.31.25.31:80",
            token_name="huxiaoke",
            token_value="hujukeai"
        ),
        ProductType.CLASSUP_OLD: TableauConfig(
            server_url="http://10.31.25.71:80",
            token_name="huxiaoke",
            token_value="hujukeai"
        ),
        ProductType.CLASSUP: TableauConfig(
            server_url="http://10.225.1.164:80",
            token_name="huxiaoke",
            token_value="hujukeai"
        )
    }
    
    @classmethod
    def get_config(cls, product: ProductType) -> TableauConfig:
        """获取指定产品的配置"""
        if product not in cls._configs:
            raise ValueError(f"未知产品类型: {product}")
        return cls._configs[product]
    
    @classmethod
    def add_config(cls, product: ProductType, config: TableauConfig):
        """添加新的产品配置"""
        cls._configs[product] = config


# ==================== 工具类模块 ====================

class ExponentialBackoffTimer:
    """指数退避定时器，用于异步轮询等待"""
    
    MIN_INTERVAL = 10
    MAX_INTERVAL = 60
    BACKOFF_FACTOR = 1.5
    
    def __init__(self, timeout: Optional[float] = None):
        self.start_time = time.time()
        self.timeout = timeout
        self.current_sleep_interval = self.MIN_INTERVAL

    def sleep(self):
        max_sleep_time = self.MAX_INTERVAL
        if self.timeout is not None:
            elapsed = time.time() - self.start_time
            if elapsed >= self.timeout:
                raise TimeoutError(f"等待超时: {elapsed}秒")
            remaining_time = self.timeout - elapsed
            max_sleep_time = min(self.MAX_INTERVAL, remaining_time)
            max_sleep_time = max(max_sleep_time, self.MIN_INTERVAL)
        
        time.sleep(min(self.current_sleep_interval, max_sleep_time))
        self.current_sleep_interval *= self.BACKOFF_FACTOR


class RetryDecorator:
    """重试装饰器工厂"""
    
    @staticmethod
    def retry(retries: int = 3, delay: float = 5, backoff: float = 2,
              exceptions: tuple = (Exception,), on_retry: Optional[Callable] = None):
        """通用重试装饰器，支持指数退避"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                mtries, mdelay = retries, delay
                while mtries > 0:
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        logger.warning(str(e))
                        true_delay = mdelay + random.uniform(1, 3)
                        logger.warning(f"在{true_delay:.1f}秒后重试...")
                        time.sleep(true_delay)
                        if callable(on_retry):
                            on_retry(args[0])
                        mtries -= 1
                        mdelay *= backoff
                # 最后一次尝试
                return func(*args, **kwargs)
            return wrapper
        return decorator


class TextUtils:
    """文本处理工具"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """去除多余空白字符"""
        import re
        return ' '.join(re.sub(r'\s+', ' ', text or '').split())
    
    @staticmethod
    def parse_utc_time(utc_time_str: Optional[str]) -> Optional[str]:
        """UTC时间字符串转北京时间字符串"""
        if not utc_time_str:
            return None
        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%SZ")
        beijing_tz = timezone(timedelta(hours=8))
        beijing_time = utc_time.replace(tzinfo=timezone.utc).astimezone(beijing_tz)
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")


# ==================== 认证模块 ====================

class AuthenticationManager:
    """认证管理器"""
    
    def __init__(self, config: TableauConfig):
        self.config = config
        self.auth_token: Optional[str] = None
        self.site_id: str = ''
    
    @RetryDecorator.retry(on_retry=lambda self: logger.info('重新登录...'))
    def sign_in(self) -> Tuple[str, str]:
        """登录并返回认证令牌和站点ID"""
        self.auth_token = None
        self.site_id = ''
        
        url = f"{self.config.server_url}/api/{self.config.api_version}/auth/signin"
        payload = (
            f"<tsRequest>"
            f"<credentials name=\"{self.config.token_name}\" password=\"{self.config.token_value}\">"
            f"<site contentUrl=\"{self.site_id}\"/>"
            f"</credentials>"
            f"</tsRequest>"
        )
        
        headers = {'Content-Type': 'application/xml'}
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        
        self.auth_token, self.site_id = XMLResponseParser.parse_signin_response(response.content)
        
        logger.info(f'以用户名: {self.config.token_name} 登录成功, 站点ID: {self.site_id}')
        return self.auth_token, self.site_id
    
    def sign_out(self):
        """退出登录"""
        if not self.auth_token:
            return
            
        url = f"{self.config.server_url}/api/{self.config.api_version}/auth/signout"
        headers = {'X-Tableau-Auth': self.auth_token}
        
        try:
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            logger.info('成功退出登录')
        except Exception:
            logger.info('有其他登录替换此会话,此会话已自动关闭')
        finally:
            self.auth_token = None
            self.site_id = ''


# ==================== HTTP客户端模块 ====================

class TableauHTTPClient:
    """Tableau HTTP客户端,处理所有HTTP请求"""
    
    def __init__(self, config: TableauConfig, auth_manager: AuthenticationManager):
        self.config = config
        self.auth_manager = auth_manager
    
    @RetryDecorator.retry(on_retry=lambda self: self.auth_manager.sign_in())
    def send_request(self, method: str, url: str, headers: Optional[Dict] = None,
                     data: Optional[str] = None, stream: bool = False):
        """发送HTTP请求到Tableau Server API"""
        headers = headers.copy() if headers else {}
        headers['X-Tableau-Auth'] = self.auth_manager.auth_token
        headers.setdefault('Content-Type', 'application/xml')
        
        method = method.lower()
        request_methods = {
            'get': requests.get,
            'post': requests.post,
            'put': requests.put,
            'delete': requests.delete
        }
        
        if method not in request_methods:
            raise ValueError(f"不支持的HTTP方法: {method}")
        
        try:
            response = request_methods[method](url, headers=headers, data=data, stream=stream)
            response.raise_for_status()
            return response.iter_content(chunk_size=8192) if stream else response
        except (requests.RequestException, requests.HTTPError) as e:
            error_message = self._parse_error_response(e)
            raise ValueError(error_message)
    
    def _parse_error_response(self, error: Exception) -> str:
        """解析错误响应"""
        error_message = str(error)
        try:
            if hasattr(error, 'response') and error.response is not None:
                request_url = getattr(error.request, 'url', '') if hasattr(error, 'request') else ''
                parsed_error = XMLResponseParser.parse_error_response(error.response.content, request_url)
                return parsed_error
        except Exception:
            pass
        return error_message
    
    def paginate_request(self, url: str, resource_type: str, page_size: int = 100,
                        max_retries: int = 5, params: Optional[Dict[str, Any]] = None):
        """分页请求生成器，带重试逻辑"""
        page_number = 1
        retry_count = 0
        params = params.copy() if params else {}
        
        while True:
            params.update({'pageSize': page_size, 'pageNumber': page_number})
            paginated_url = f"{url}?{urllib.parse.urlencode(params)}"
            
            response = self.send_request('get', paginated_url)
            resources, total_available = XMLResponseParser.parse_pagination_response(
                response.content, resource_type
            )
            
            if total_available == 0:
                retry_count += 1
                if retry_count > max_retries:
                    logger.warning('达到最大重试次数')
                    break
                logger.warning('总资源数为0, 10秒后重试...')
                time.sleep(10)
                continue
            
            retry_count = 0
            yield resources
            
            if page_number * page_size >= total_available:
                break
            page_number += 1


# ==================== XML解析器模块 ====================

class XMLResponseParser:
    """XML响应解析器"""
    
    @staticmethod
    def parse_job_response(content: bytes) -> Dict[str, Any]:
        """解析作业响应"""
        tree = ET.fromstring(content)
        jobs = tree.findall(".//t:job", namespaces={'t': 'http://tableau.com/api'})
        
        if not jobs:
            return {}
        
        job = jobs[0]
        workbook = tree.find(".//t:workbook[@id]", namespaces={'t': 'http://tableau.com/api'})
        datasource = tree.find(".//t:datasource[@id]", namespaces={'t': 'http://tableau.com/api'})
        
        return {
            'id': job.get("id"),
            'type': job.get("type"),
            'progress': job.get("progress"),
            'created_at': TextUtils.parse_utc_time(job.get("createdAt")),
            'started_at': TextUtils.parse_utc_time(job.get("startedAt")),
            'completed_at': TextUtils.parse_utc_time(job.get("completedAt")),
            'finish_code': int(job.get("finishCode", -1)),
            'notes': [note.text for note in tree.findall(".//t:notes", namespaces={'t': 'http://tableau.com/api'})] or None,
            'mode': job.get("mode"),
            'workbook_id': workbook.get("id") if workbook is not None else None,
            'datasource_id': datasource.get("id") if datasource is not None else None,
            'datasource_name': datasource.get("name") if datasource is not None else None,
            'updated_at': TextUtils.parse_utc_time(tree.get("updatedAt"))
        }
    
    @staticmethod
    def parse_workbook_response(content: bytes) -> Dict[str, Any]:
        """解析工作簿响应"""
        tree = ET.fromstring(content)
        workbook = tree.find('.//t:workbook', namespaces={'t': 'http://tableau.com/api'})
        project = tree.find('.//t:project', namespaces={'t': 'http://tableau.com/api'})
        
        if workbook is None or project is None:
            raise ValueError("未能解析工作簿信息")
        
        return {
            'workbook_id': workbook.get('id'),
            'workbook_name': workbook.get('name'),
            'project_id': project.get('id')
        }
    
    @staticmethod
    def parse_user_response(content: bytes) -> Dict[str, Any]:
        """解析用户响应"""
        tree = ET.fromstring(content)
        users = tree.findall('.//t:user', namespaces={'t': 'http://tableau.com/api'})
        
        if not users:
            raise ValueError("未找到用户信息")
        if len(users) > 1:
            raise ValueError(f"找到{len(users)}个重名用户,请检查")
        
        user = users[0]
        return {
            'id': user.get('id'),
            'name': user.get('name'),
            'fullName': user.get('fullName'),
            'email': user.get('email'),
            'siteRole': user.get('siteRole'),
            'lastLogin': TextUtils.parse_utc_time(user.get('lastLogin'))
        }
    
    @staticmethod
    def parse_workbook_views_response(content: bytes) -> List[str]:
        """解析工作簿视图响应"""
        tree = ET.fromstring(content)
        views = tree.findall('.//t:view', namespaces={'t': 'http://tableau.com/api'})
        return [view.get('id') for view in views]
    
    @staticmethod
    def parse_project_response(content: bytes) -> Dict[str, Dict]:
        """解析项目响应"""
        tree = ET.fromstring(content)
        projects = tree.findall('.//t:project', namespaces={'t': 'http://tableau.com/api'})
        project_tree = {}
        for project in projects:
            project_id = project.get('id')
            project_tree[project_id] = {
                'name': project.get('name'),
                'parent_id': project.get('parentProjectId'),
                'children': []
            }
        for project_id, project_info in project_tree.items():
            parent_id = project_info['parent_id']
            if parent_id and parent_id in project_tree:
                project_tree[parent_id]['children'].append(project_id)
        return project_tree
    
    @staticmethod
    def parse_signin_response(content: bytes) -> Tuple[str, str]:
        """解析登录响应"""
        tree = ET.fromstring(content)
        credentials = tree.find('.//t:credentials', namespaces={'t': 'http://tableau.com/api'})
        site = tree.find('.//t:site', namespaces={'t': 'http://tableau.com/api'})
        
        if credentials is None or site is None:
            raise ValueError("认证响应解析失败")
        
        auth_token = credentials.get('token')
        site_id = site.get('id')
        
        if not auth_token or not site_id:
            raise ValueError("认证令牌或站点ID为空")
            
        return auth_token, site_id
    
    @staticmethod
    def parse_error_response(content: bytes, request_url: str = '') -> str:
        """解析错误响应"""
        try:
            tree = ET.fromstring(content)
            error_elem = tree.find(".//{http://tableau.com/api}error")
            
            if error_elem is not None:
                error_code = error_elem.attrib.get('code', 'Unknown')
                if error_code == '400050':  # 空工作簿特殊处理
                    return f"Error Code: {error_code}"
                
                summary_elem = tree.find(".//{http://tableau.com/api}summary")
                detail_elem = tree.find(".//{http://tableau.com/api}detail")
                
                error_summary = summary_elem.text if summary_elem is not None else "Unknown"
                error_detail = detail_elem.text if detail_elem is not None else "Unknown"
                
                error_message = f"Error Code: {error_code}, Summary: {error_summary}, Detail: {error_detail}"
                if request_url:
                    error_message += f" Request: {request_url}"
                return error_message
        except Exception:
            pass
        
        return "Unknown error occurred"
    
    @staticmethod
    def parse_pagination_response(content: bytes, resource_type: str) -> Tuple[List, int]:
        """解析带分页信息的响应"""
        tree = ET.fromstring(content.decode('utf-8'))
        resources = tree.findall(f'.//t:{resource_type}', namespaces={'t': 'http://tableau.com/api'})
        
        pagination = tree.find('.//t:pagination', namespaces={'t': "http://tableau.com/api"})
        if pagination is None:
            raise ValueError("响应中未找到分页信息")
        
        total_available = int(pagination.get('totalAvailable', 0))
        return resources, total_available
    
    @staticmethod
    def parse_job_submit_response(content: bytes) -> Optional[str]:
        """解析作业提交响应"""
        tree = ET.fromstring(content)
        job = tree.find(".//t:job", namespaces={'t': 'http://tableau.com/api'})
        return job.get('id') if job is not None else None

# ==================== 数据源解析器模块 ====================

class DataSourceParser:
    """数据源文件解析器"""
    
    @staticmethod
    def parse_tds_content(datasource_id: str, tds_content: bytes) -> Dict[str, Any]:
        """解析TDS文件内容"""
        result = {
            'datasource_id': datasource_id,
            'one_time_sql': None,
            'server': None,
            'username': None,
            'sql_content': None,
            'http_path': None
        }
        
        tree = ET.parse(io.BytesIO(tds_content))
        
        # 遍历所有connection标签
        connections = list(tree.iter(tag='connection'))
        for i, conn in enumerate(connections):
            if i == 0:
                # 只有第一个connection时直接更新
                result.update({
                    'one_time_sql': TextUtils.clean_text(conn.get('one-time-sql', '')),
                    'server': TextUtils.clean_text(conn.get('server', '')),
                    'username': TextUtils.clean_text(conn.get('username', '')),
                    'http_path': TextUtils.clean_text(conn.get('_.fcp.DatabricksCatalog.false...dbname', ''))
                })
            else:
                # 后续的connection只在原值为空时更新
                if not result['one_time_sql']:
                    result['one_time_sql'] = TextUtils.clean_text(conn.get('one-time-sql', ''))
                if not result['server']:
                    result['server'] = TextUtils.clean_text(conn.get('server', ''))
                if not result['username']:
                    result['username'] = TextUtils.clean_text(conn.get('username', ''))
                if not result['http_path']:
                    result['http_path'] = TextUtils.clean_text(conn.get('_.fcp.DatabricksCatalog.false...dbname', ''))
        
        # 解析SQL内容
        for relation in tree.iter(tag='_.fcp.ObjectModelEncapsulateLegacy.false...relation'):
            if relation.text:
                sql = TextUtils.clean_text(relation.text)
                result['sql_content'] = sql.replace('<<', '<').replace('>>', '>')
        
        return result


# ==================== 资源管理器基类 ====================

class BaseResourceManager(ABC):
    """资源管理器基类"""
    
    def __init__(self, http_client: TableauHTTPClient, auth_manager: AuthenticationManager):
        self.http_client = http_client
        self.auth_manager = auth_manager
        self.config = http_client.config
    
    def get_resource_id_by_name(self, resource_type: str, resource_name: str) -> str:
        """根据名称获取资源ID"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/{resource_type}s"
        matching_resources = []
        
        for resources in self.http_client.paginate_request(url, resource_type):
            matching_resources.extend(
                resource.get('id') for resource in resources
                if resource.get('name') == resource_name
            )
        
        if not matching_resources:
            raise ValueError(f'未找到名为 {resource_name} 的 {resource_type}')
        if len(matching_resources) > 1:
            raise ValueError(f'有{len(matching_resources)}个{resource_type}同名{resource_name},资源ID: {matching_resources},请检查')
        
        logger.info(f"找到 {len(matching_resources)} 个名为 {resource_name} 的 {resource_type}, 资源ID: {matching_resources[0]}")
        return matching_resources[0]


# ==================== 具体资源管理器 ====================


class ProjectManager(BaseResourceManager):
    """项目管理器"""
    
    def get_projects(self) -> Dict[str, Dict]:
        """获取项目层级结构"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/projects"
        response = self.http_client.send_request('get', url)
        return XMLResponseParser.parse_project_response(response.content)
    
    def get_project_path(self, project_id: str) -> str:
        """获取项目的完整路径"""
        project_tree = self.get_projects()
        path = []
        current_id = project_id
        while current_id and current_id in project_tree:
            project = project_tree[current_id]
            path.insert(0, project['name'])
            current_id = project['parent_id']
        return os.path.join(*path) if path else ''


class WorkbookManager(BaseResourceManager):
    """工作簿管理器"""
    
    def __init__(self, http_client: TableauHTTPClient, auth_manager: AuthenticationManager):
        super().__init__(http_client, auth_manager)
        self._project_manager: Optional['ProjectManager'] = None
        self._view_manager: Optional['ViewManager'] = None
    
    def set_managers(self, project_manager: 'ProjectManager', view_manager: 'ViewManager'):
        """设置依赖的管理器"""
        self._project_manager = project_manager
        self._view_manager = view_manager

    def get_workbook_by_id(self, workbook_id: str) -> Dict[str, Any]:
        """根据ID获取工作簿详情"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/workbooks/{workbook_id}"
        response = self.http_client.send_request('get', url)
        return XMLResponseParser.parse_workbook_response(response.content)
    
    
    def download_workbook(self, workbook_id: str, is_include_extract: bool = True) -> str:
        """下载工作簿并保存到本地"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/workbooks/{workbook_id}/content"
        if is_include_extract:
            url += "?includeExtract=True"
        
        workbook_info = self.get_workbook_by_id(workbook_id)
        workbook_name = workbook_info['workbook_name']
        project_id = workbook_info['project_id']
        
        # 清理工作簿名称，移除不安全的文件名字符
        safe_workbook_name = self._sanitize_filename(workbook_name)
        
        # 获取项目路径
        project_path = ''
        if self._project_manager:
            project_path = self._project_manager.get_project_path(project_id)
        
        if project_path and not os.path.exists(project_path):
            os.makedirs(project_path, exist_ok=True)
        
        extension = '.twbx' if is_include_extract else '.twb'
        workbook_path = os.path.join(project_path, f"{safe_workbook_name}{extension}")
        
        export_response = self.http_client.send_request('get', url, stream=True)
        
        with open(workbook_path, 'wb') as f:
            for chunk in export_response:
                f.write(chunk)
        
        logger.info(f"成功下载工作簿 {workbook_id} 到 {workbook_path}")
        return workbook_path
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除或替换不安全的字符"""
        # 定义不安全的字符（包括路径分隔符和其他特殊字符）
        unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        
        # 替换不安全字符为下划线
        safe_filename = filename
        for char in unsafe_chars:
            safe_filename = safe_filename.replace(char, '_')
        
        # 移除首尾空格和点号（避免隐藏文件或无效文件名）
        safe_filename = safe_filename.strip(' .')
        
        # 确保文件名不为空
        if not safe_filename:
            safe_filename = 'unnamed_workbook'
        
        # 限制文件名长度（大多数文件系统限制为255字符）
        if len(safe_filename) > 200:  # 留一些空间给扩展名
            safe_filename = safe_filename[:200]
        
        return safe_filename


    def get_workbook_images(self, workbook_id: str) -> List[bytes]:
        """获取工作簿下所有视图的图片"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/workbooks/{workbook_id}/views"
        response = self.http_client.send_request('get', url)
        view_ids = XMLResponseParser.parse_workbook_views_response(response.content)
        
        images = []
        if self._view_manager:
            images = [self._view_manager.get_view_image_by_id(view_id) for view_id in view_ids]
        
        return images
    
    
    def backup_workbooks(self, specific_workbook_id: Optional[str] = None):
        """备份工作簿，支持单个或全部"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/workbooks"
        for workbooks in self.http_client.paginate_request(url, 'workbook', max_retries=3):
            filtered_workbooks = (
                [wb for wb in workbooks if wb.get('id') == specific_workbook_id]
                if specific_workbook_id else workbooks
            )
            for workbook in filtered_workbooks:
                workbook_id = workbook.get('id')
                workbook_name = workbook.get('name')
                logger.info(f"开始处理工作簿: {workbook_name}(ID: {workbook_id})")
                try:
                    download_path = self.download_workbook(workbook_id)
                    logger.info(f'工作簿 {workbook_name} 备份完成, 保存至 {download_path}')
                except Exception as e:
                    logger.error(f'工作簿 {workbook_name} 备份失败: {str(e)}')


class DataSourceManager(BaseResourceManager):
    """数据源管理器"""
    
    def download_and_extract_datasource(self, datasource_id: str) -> Dict[str, Any]:
        """下载并解析数据源内容"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/datasources/{datasource_id}/content?includeExtract=False"
        logger.info(f"下载数据源 {datasource_id}")
        
        response = self.http_client.send_request('get', url)
        
        with io.BytesIO(response.content) as datasource_stream:
            with zipfile.ZipFile(datasource_stream) as z:
                tds_files = [f for f in z.namelist() if f.endswith('.tds')]
                if not tds_files:
                    return {}
                
                with z.open(tds_files[0]) as tds_file:
                    return DataSourceParser.parse_tds_content(datasource_id, tds_file.read())
    
    def extract_datasource(self, specific_datasource_id: Optional[str] = None) -> pd.DataFrame:
        """提取数据源信息，支持单个或全部"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/datasources"
        result_datasource_info = []
        
        for datasources in self.http_client.paginate_request(url, 'datasource', max_retries=3):
            filtered_datasources = (
                [ds for ds in datasources if ds.get('id') == specific_datasource_id]
                if specific_datasource_id else datasources
            )
            
            for datasource in filtered_datasources:
                datasource_id = datasource.get('id')
                datasource_name = datasource.get('name')
                datasource_type = datasource.get('type')
                
                owner_elem = datasource.find('.//ns0:owner', namespaces={'ns0': 'http://tableau.com/api'})
                datasource_owner = owner_elem.get('id') if owner_elem is not None else None
                
                logger.info(f"开始处理数据源: {datasource_name}(ID: {datasource_id})")
                
                datasource_info = self.download_and_extract_datasource(datasource_id)
                datasource_info.update({
                    'datasource_name': datasource_name,
                    'datasource_type': datasource_type,
                    'datasource_owner': datasource_owner
                })
                
                result_datasource_info.append(datasource_info)
                
                if specific_datasource_id and datasource_id == specific_datasource_id:
                    break
            
            if specific_datasource_id and result_datasource_info:
                break
        
        df = pd.DataFrame(result_datasource_info)
        if not df.empty:
            df = df[['datasource_id', 'datasource_name', 'datasource_owner', 'datasource_type',
                     'one_time_sql', 'server', 'username', 'http_path', 'sql_content']]
            
            # 处理用户名映射
            unique_owners = df['datasource_owner'].dropna().unique()
            owner_name_map = {}
            for owner_id in unique_owners:
                try:
                    user_info = self._get_user_by_id(owner_id)
                    owner_name_map[owner_id] = user_info['fullName']
                except Exception as e:
                    logger.warning(f"获取用户 {owner_id} 信息失败: {e}")
                    owner_name_map[owner_id] = owner_id
            
            df['datasource_owner'] = df['datasource_owner'].map(owner_name_map)
        
        return df
    
    def _get_user_by_id(self, user_id: str) -> Dict[str, Any]:
        """根据ID获取用户信息"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/users"
        params = {'filter': f"luid:eq:{user_id}"}
        final_url = f"{url}?{urllib.parse.urlencode(params)}"
        
        response = self.http_client.send_request('get', final_url)
        return XMLResponseParser.parse_user_response(response.content)


class ViewManager(BaseResourceManager):
    """视图管理器"""
    
    def get_view_image_by_id(self, view_id: str, high_resolution: bool = True, 
                           filters: Optional[Dict] = None) -> bytes:
        """获取指定分辨率的视图图片"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/views/{view_id}/image"
        params = {
            'maxAge': 0,
            ':refresh': 'y',
            'resolution': 'high' if high_resolution else 'normal'
        }
        
        if filters:
            params.update({f"vf_{k}": v for k, v in filters.items() if v is not None})
        
        final_url = f"{url}?{urllib.parse.urlencode(params)}"
        response = self.http_client.send_request('get', final_url)
        
        logger.info(f"获取视图图片成功, 视图ID: {view_id}, 图片大小: {len(response.content)/1024:.2f}KB")
        return response.content
    
    def populate_view_excel(self, view_id: str, filters: Optional[Dict] = None, 
                          header_rows: int = 1) -> pd.DataFrame:
        """获取视图的Excel数据"""
        base_url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/views/{view_id}/crosstab/excel"
        params = {}
        
        if filters:
            params.update({f"vf_{k}": v for k, v in filters.items() if v is not None})
        
        url = f"{base_url}?{urllib.parse.urlencode(params)}&maxAge=0"
        response = self.http_client.send_request('get', url)
        
        df = pd.read_excel(io.BytesIO(response.content), header=list(range(header_rows)))
        logger.info(f"成功从Tableau获取Excel数据: {df.shape[0]}行 {df.shape[1]}列")
        return df


class JobManager(BaseResourceManager):
    """作业管理器"""
    
    def get_job_by_id(self, job_id: str) -> Dict[str, Any]:
        """根据ID获取作业信息"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/jobs/{job_id}"
        response = self.http_client.send_request('get', url)
        
        job_info = XMLResponseParser.parse_job_response(response.content)
        if not job_info:
            raise ValueError(f"未找到作业 {job_id}")
        
        return job_info
    
    def submit_datasource_refresh_job(self, datasource_id: str) -> Optional[str]:
        """提交数据源刷新作业"""
        url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/datasources/{datasource_id}/refresh"
        payload = "<tsRequest></tsRequest>"
        
        response = self.http_client.send_request('post', url, data=payload)
        job_id = XMLResponseParser.parse_job_submit_response(response.content)
        
        if job_id:
            logger.info(f'数据源 {datasource_id} 刷新作业已提交, 作业ID: {job_id}')
        else:
            logger.warning(f"数据源 {datasource_id} 刷新作业提交成功, 但未返回作业ID")
        
        return job_id
    
    def wait_datasource_refresh(self, job_id: Optional[str]):
        """等待数据源刷新作业完成"""
        if not job_id:
            logger.warning("作业ID为空,无需等待")
            return
        
        timer = ExponentialBackoffTimer(timeout=60 * 60)
        job = self.get_job_by_id(job_id)
        
        while not job['completed_at']:
            timer.sleep()
            job = self.get_job_by_id(job_id)
            logger.info(f"数据源 {job['datasource_name']} 作业 {job_id} 进度: {job['progress']}")
        
        if job['finish_code'] == 0:
            logger.info(f"数据源 {job['datasource_name']} 作业 {job_id} 完成! 备注: {job['notes']}")
        elif job['finish_code'] in (1, 2):
            logger.error(f"数据源 {job['datasource_name']} 作业 {job_id} 失败! 备注: {job['notes']}")
        else:
            logger.error("作业完成代码异常")

    def extract_jobs(self, filters: Optional[Dict[str, Tuple[str, str]]] = None,
                    sorted_by: Optional[Dict[str, str]] = None) -> pd.DataFrame:
        """提取作业信息"""
        base_url = f"{self.config.server_url}/api/{self.config.api_version}/sites/{self.auth_manager.site_id}/jobs"
        params = {}
        if filters:
            params['filter'] = ",".join(f"{k}:{op}:{v}" for k, (op, v) in filters.items())
        if sorted_by:
            params['sort'] = ",".join(f"{k}:{v}" for k, v in sorted_by.items())
        records = []
        for resources in self.http_client.paginate_request(base_url, 'backgroundJob', max_retries=3, params=params):
            for resource in resources:
                job = self.get_job_by_id(resource.get('id'))
                if len(records) % 100 == 0:
                    logger.info(f"已提取{len(records)}条作业信息,时间截止到{job['completed_at']}")
                records.append({
                    'job_id': job['id'],
                    'datasource_name': job['datasource_name'],
                    'started_at': job['started_at'],
                    'completed_at': job['completed_at'],
                    'finish_code': job['finish_code']
                })
        df = pd.DataFrame(records)
        if not df.empty:
            df['duration'] = (pd.to_datetime(df['completed_at']) -
                              pd.to_datetime(df['started_at'])).dt.total_seconds()
            return df[['job_id', 'datasource_name', 'started_at',
                       'completed_at', 'finish_code', 'duration']]
        return df


# ==================== 主客户端类 ====================

class TableauServerClientV2:
    """
    Tableau Server REST API 客户端 v3 - 重构版本
    
    采用模块化设计，职责分离：
    - 配置管理: ConfigManager
    - 认证管理: AuthenticationManager  
    - HTTP通信: TableauHTTPClient
    - XML解析: XMLResponseParser
    - 资源管理: 各种Manager类
    """
    
    def __init__(self, product: str = 'Aries'):
        # 解析产品类型
        try:
            product_type = ProductType(product)
        except ValueError:
            raise ValueError(f'未知产品: {product}')
        
        # 初始化各个组件
        self.config = ConfigManager.get_config(product_type)
        self.auth_manager = AuthenticationManager(self.config)
        self.http_client = TableauHTTPClient(self.config, self.auth_manager)
        
        # 初始化资源管理器
        self.projects = ProjectManager(self.http_client, self.auth_manager)
        self.views = ViewManager(self.http_client, self.auth_manager)
        self.workbooks = WorkbookManager(self.http_client, self.auth_manager)
        self.datasources = DataSourceManager(self.http_client, self.auth_manager)
        self.jobs = JobManager(self.http_client, self.auth_manager)
        
        # 设置WorkbookManager的依赖
        self.workbooks.set_managers(self.projects, self.views)
    
    def __enter__(self):
        """上下文管理器入口"""
        self.auth_manager.sign_in()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出处理"""
        if exc_type is not None:
            raise Exception(f"{exc_val}")
        self.auth_manager.sign_out()
    
    # ==================== 向后兼容的方法 ====================
    
    def get_resource_id_by_name(self, resource_type: str, resource_name: str) -> str:
        """根据名称获取资源ID - 兼容性方法"""
        if resource_type in ['workbook']:
            return self.workbooks.get_resource_id_by_name(resource_type, resource_name)
        elif resource_type in ['datasource']:
            return self.datasources.get_resource_id_by_name(resource_type, resource_name)
        elif resource_type in ['view']:
            return self.views.get_resource_id_by_name(resource_type, resource_name)
        else:
            raise ValueError(f"不支持的资源类型: {resource_type}")
    
    def get_view_image_by_id(self, view_id: str, high_resolution: bool = True, 
                           filters: Optional[Dict] = None) -> bytes:
        """获取视图图片 - 兼容性方法"""
        return self.views.get_view_image_by_id(view_id, high_resolution, filters)
    
    def populate_view_excel(self, view_id: str, filters: Optional[Dict] = None, 
                          header_rows: int = 1) -> pd.DataFrame:
        """获取视图Excel数据 - 兼容性方法"""
        return self.views.populate_view_excel(view_id, filters, header_rows)
    
    def extract_datasource(self, specific_datasource_id: Optional[str] = None) -> pd.DataFrame:
        """提取数据源信息 - 兼容性方法"""
        return self.datasources.extract_datasource(specific_datasource_id)
    
    def submit_datasource_refresh_job(self, datasource_id: str) -> Optional[str]:
        """提交数据源刷新作业 - 兼容性方法"""
        return self.jobs.submit_datasource_refresh_job(datasource_id)
    
    def wait_datasource_refresh(self, job_id: Optional[str]):
        """等待数据源刷新完成 - 兼容性方法"""
        return self.jobs.wait_datasource_refresh(job_id)
    
    def get_job_by_id(self, job_id: str) -> Dict[str, Any]:
        """获取作业信息 - 兼容性方法"""
        return self.jobs.get_job_by_id(job_id)
    
    def download_workbook(self, workbook_id: str, is_include_extract: bool = True) -> str:
        """下载工作簿 - 兼容性方法"""
        return self.workbooks.download_workbook(workbook_id, is_include_extract)

    def backup_workbooks(self, specific_workbook_id: Optional[str] = None):
        """备份工作簿 - 兼容性方法"""
        return self.workbooks.backup_workbooks(specific_workbook_id)
    
    def extract_jobs(self, filters: Optional[Dict[str, Tuple[str, str]]] = None,
                     sorted_by: Optional[Dict[str, str]] = None) -> pd.DataFrame:
        """提取作业信息 - 兼容性方法"""
        return self.jobs.extract_jobs(filters, sorted_by)



# ==================== 使用示例 ====================
# if __name__ == "__main__":
#     # 使用方式1：直接创建客户端
#     with TableauServerClientV2('Aries') as client:
#         # 获取数据源信息
#         df = client.extract_datasource()
#         print(f"提取到 {len(df)} 个数据源")
        
#         # 获取视图图片
#         view_id = client.get_resource_id_by_name('view', '视图名称')
#         image = client.get_view_image_by_id(view_id)
#         print(f"获取图片大小: {len(image)} 字节")
