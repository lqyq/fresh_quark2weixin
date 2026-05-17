import requests
import asyncio
import random
import time
import json
import os
import sys
import traceback
import re
import httpx
import functools
import inspect
from typing import Union, Dict, Any, List, Tuple
from datetime import datetime
from colorama import Fore, Style
from retrying import retry

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path)  # 加载 .env 文件中的环境变量
    print("成功加载 .env 文件")
except ImportError:
    print("未安装 python-dotenv，跳过 .env 文件加载")
except Exception as e:
    print(f"加载 .env 文件失败: {e}")

# 从环境变量读取配置
WEBHOOK_URL = os.getenv('WECHAT_WEBHOOK_URL', '')
QUARK_COOKIES = os.getenv('QUARK_COOKIES', '')
DEFAULT_COUNT = int(os.getenv('COUNT', '5'))
KUAKE_CLI = os.getenv('KUAKE_CLI', 'kuake1.exe')
CACHE_EXPIRE_HOURS = float(os.getenv('CACHE_EXPIRE_HOURS', '24'))

# 配置目录
CONFIG_DIR = './config'
# API数据缓存文件
CACHE_FILE = './cache/api_cache.json'
os.makedirs(CONFIG_DIR, exist_ok=True)

# 日志文件
LOG_FILE = "function_runtime.log"


def setup_logging():
    """Initialize log file with header"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting new logging session\n")
        f.write(f"{'='*80}\n")


def log_function_call(func):
    """
    Decorator to log function inputs and outputs
    """
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_name = func.__name__
        start_time = time.time()

        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        args_str = ', '.join([f"{k}={v!r}" for k, v in bound_args.arguments.items()])
        log_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Calling {func_name}({args_str})"

        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")

        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time

            success_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {func_name} completed successfully in {duration:.4f}s"
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(success_msg + "\n")
                if result is not None:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {func_name} returned: {result!r}" + "\n")

            return result

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {func_name} failed after {duration:.4f}s with error: {e!r}"
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(error_msg + "\n")

            raise

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = func.__name__
        start_time = time.time()

        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        args_str = ', '.join([f"{k}={v!r}" for k, v in bound_args.arguments.items()])
        log_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Calling async {func_name}({args_str})"

        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")

        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time

            success_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] async {func_name} completed successfully in {duration:.4f}s"
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(success_msg + "\n")
                if result is not None:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] async {func_name} returned: {result!r}" + "\n")

            return result

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] async {func_name} failed after {duration:.4f}s with error: {e!r}"
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(error_msg + "\n")

            raise

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def get_datetime(timestamp: Union[int, float, None] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if timestamp is None or not isinstance(timestamp, (int, float)):
        return datetime.today().strftime(fmt)
    else:
        dt = datetime.fromtimestamp(timestamp)
        formatted_time = dt.strftime(fmt)
        return formatted_time


def custom_print(message, error_msg=False) -> None:
    if error_msg:
        print(Fore.RED + f'[{get_datetime()}] {message}' + Style.RESET_ALL)
    else:
        print(f'[{get_datetime()}] {message}')


def get_timestamp(length: int) -> int:
    if length == 13:
        return int(time.time()) * 1000
    else:
        return int(time.time())


def save_config(path: str, content: str, mode: str = 'w'):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, mode, encoding='utf-8') as f:
        f.write(content)


def read_config(path: str, read_type: str = None, mode: str = 'r') -> Union[dict, str, None]:
    try:
        with open(path, mode, encoding='utf-8') as config_file:
            if read_type != 'json':
                return config_file.read()
            else:
                return json.load(config_file)
    except FileNotFoundError:
        return None


def safe_copy(src, dst):
    import shutil
    if not os.path.exists(src):
        print(f"源文件不存在，跳过复制：{src}")
        return

    if os.path.exists(dst):
        os.remove(dst)
        print(f"目标文件已存在，已删除：{dst}")

    try:
        shutil.copy(src, dst)
        print(f"文件已复制到：{dst}")
    except Exception as e:
        print('备份share_url.txt文件错误，', e)


def generate_random_code(length=4):
    import string
    characters = string.ascii_letters + string.digits
    random_code = ''.join(random.choice(characters) for _ in range(length))
    return random_code


def format_size(size_bytes):
    KB = 1024
    MB = 1024 * KB
    GB = 1024 * MB
    TB = 1024 * GB

    if size_bytes >= TB:
        return f"{size_bytes / TB:.1f}TB"
    elif size_bytes >= GB:
        return f"{size_bytes / GB:.1f}GB"
    elif size_bytes >= MB:
        return f"{size_bytes / MB:.1f}MB"
    elif size_bytes >= KB:
        return f"{size_bytes / KB:.1f}KB"
    else:
        return f"{size_bytes}B"


class QuarkLogin:
    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self.context = None

    @staticmethod
    def save_cookies(page) -> None:
        cookie = page.context.cookies()

        with open(f'{CONFIG_DIR}/cookies.txt', 'w', encoding='utf-8') as f:
            f.write(str(cookie))

    @retry
    def login(self) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            self.context = p.chromium.launch_persistent_context(
                './web_browser_data',
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=['--start-maximized'],
                no_viewport=True
            )
            page = self.context.pages[0]
            page.goto('https://pan.quark.cn/')

            input("请在弹出的浏览器中登录夸克，登录成功后请勿手动关闭浏览器，回到本界面按 Enter 键继续...")
            self.save_cookies(page)

    @staticmethod
    def cookies_str_to_dict(cookies_str: str) -> Dict[str, str]:
        cookies_dict = {}
        cookies_list = cookies_str.split('; ')
        for cookie in cookies_list:
            key, value = cookie.split('=', 1)
            cookies_dict[key] = value
        return cookies_dict

    @staticmethod
    def transfer_cookies(cookies_list: List[Dict[str, Union[str, int]]]) -> Dict[str, str]:
        cookies_dict = {}
        for cookie in cookies_list:
            if 'quark' in cookie['domain']:
                cookies_dict[cookie['name']] = cookie['value']
        return cookies_dict

    @staticmethod
    def dict_to_cookie_str(cookies_dict: Dict[str, str]) -> str:
        cookie_str = '; '.join([f"{key}={value}" for key, value in cookies_dict.items()])
        return cookie_str

    def check_cookies(self) -> Union[None, Union[Dict[str, str], str]]:
        try:
            with open(f'{CONFIG_DIR}/cookies.txt', 'r') as f:
                content = f.read()

            if content and '[' in content:
                saved_cookies = eval(content)
                cookies_dict = self.transfer_cookies(saved_cookies)
                timestamp = int(time.time())
                if 'expires' in cookies_dict and timestamp > int(cookies_dict['expires']):
                    return None
                return cookies_dict
            else:
                return content.strip()
        except Exception as e:
            print(f"Error checking cookies: {e}")
            return None

    def get_cookies(self) -> Union[str, None]:
        # 优先使用环境变量中的 Cookie
        if QUARK_COOKIES:
            log_print("使用环境变量中的 QUARK_COOKIES", "INFO")
            return QUARK_COOKIES

        cookie = self.check_cookies()
        if not cookie:
            print('没有登录')
            with open(f'{CONFIG_DIR}/cookies.txt', 'r') as f:
                content = f.read()
                if not content:
                    return
                saved_cookies = eval(content)
            cookies_dict = self.transfer_cookies(saved_cookies)
            return self.dict_to_cookie_str(cookies_dict)

        elif isinstance(cookie, dict):
            return self.dict_to_cookie_str(cookie)
        elif isinstance(cookie, str):
            return cookie


class QuarkPanFileManager:
    """
    夸克网盘文件管理核心类
    功能：登录验证、文件转存、下载、分享链接生成、目录管理等
    """
    def __init__(self, headless: bool = False, slow_mo: int = 0) -> None:
        """
        类初始化：配置基础参数、获取登录Cookie、设置HTTP请求头
        :param headless: 是否无头模式运行浏览器（登录用），False=显示浏览器
        :param slow_mo: 浏览器操作延迟（毫秒），避免触发反爬
        """
        self.headless: bool = headless
        self.slow_mo: int = slow_mo
        self.folder_id: Union[str, None] = None
        self.user: Union[str, None] = '用户A'
        self.pdir_id: Union[str, None] = '0'
        self.dir_name: Union[str, None] = '根目录'
        self.cookies: str = self.get_cookies()
        self.headers: Dict[str, str] = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)'
                          ' Chrome/94.0.4606.71 Safari/537.36 Core/1.94.225.400 QQBrowser/12.2.5544.400',
            'origin': 'https://pan.quark.cn',
            'referer': 'https://pan.quark.cn/',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cookie': self.cookies,
        }

    @log_function_call
    def get_cookies(self) -> str:
        """
        调用QuarkLogin类获取登录Cookie（无Cookie则触发浏览器登录）
        :return: 格式化后的Cookie字符串（用于HTTP请求）
        """
        quark_login = QuarkLogin(headless=self.headless, slow_mo=self.slow_mo)
        cookies: str = quark_login.get_cookies()
        return cookies

    @staticmethod
    @log_function_call
    def get_pwd_id(share_url: str) -> str:
        """
        从分享链接中提取关键标识pwd_id
        """
        return share_url.split('?')[0].split('/s/')[-1]

    @log_function_call
    async def get_stoken(self, pwd_id: str, password: str = '') -> str:
        """
        向夸克API请求分享访问令牌stoken
        """
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': '',
            '__dt': random.randint(100, 9999),
            '__t': get_timestamp(13),
        }
        api = "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token"
        data = {"pwd_id": pwd_id, "passcode": password}

        async with httpx.AsyncClient() as client:
            timeout = httpx.Timeout(60.0, connect=60.0)
            response = await client.post(api, json=data, params=params, headers=self.headers, timeout=timeout)
            json_data = response.json()
            if json_data['status'] == 200 and json_data['data']:
                stoken = json_data["data"]["stoken"]
            else:
                stoken = ''
                custom_print(f"文件转存失败，{json_data['message']}")
            return stoken

    @log_function_call
    async def get_detail(self, pwd_id: str, stoken: str, pdir_fid: str = '0') -> Tuple[
        str, List[Dict[str, Union[int, str]]]]:
        """
        分页获取分享链接中的文件/文件夹详情列表
        """
        api = "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail"
        page = 1
        file_list: List[Dict[str, Union[int, str]]] = []

        async with httpx.AsyncClient() as client:
            while True:
                params = {
                    'pr': 'ucpro',
                    'fr': 'pc',
                    'uc_param_str': '',
                    "pwd_id": pwd_id,
                    "stoken": stoken,
                    'pdir_fid': pdir_fid,
                    'force': '0',
                    "_page": str(page),
                    '_size': '50',
                    '_sort': 'file_type:asc,updated_at:desc',
                    '__dt': random.randint(200, 9999),
                    '__t': get_timestamp(13),
                }

                timeout = httpx.Timeout(60.0, connect=60.0)
                response = await client.get(api, headers=self.headers, params=params, timeout=timeout)
                json_data = response.json()

                is_owner = json_data['data']['is_owner']
                _total = json_data['metadata']['_total']
                if _total < 1:
                    return is_owner, file_list

                _size = json_data['metadata']['_size']
                _count = json_data['metadata']['_count']
                _list = json_data["data"]["list"]

                for file in _list:
                    d: Dict[str, Union[int, str]] = {
                        "fid": file["fid"],
                        "file_name": file["file_name"],
                        "file_type": file["file_type"],
                        "dir": file["dir"],
                        "pdir_fid": file["pdir_fid"],
                        "include_items": file["include_items"] if "include_items" in file else '',
                        "share_fid_token": file["share_fid_token"],
                        "status": file["status"]
                    }
                    file_list.append(d)

                if _total <= _size or _count < _size:
                    return is_owner, file_list

                page += 1

    @log_function_call
    async def run(self, input_line: str, folder_id: Union[str, None] = None, download: bool = False) -> Dict:
        """
        核心执行方法：根据download参数切换「转存」或「下载」模式
        """
        self.folder_id = folder_id
        share_url = input_line.strip()
        custom_print(f'文件分享链接：{share_url}')

        match_password = re.search("pwd=(.*?)(?=$|&)", share_url)
        password = match_password.group(1) if match_password else ""
        pwd_id = self.get_pwd_id(input_line).split("#")[0]

        if not pwd_id:
            custom_print(f'文件分享链接不可为空！', error_msg=True)
            return

        stoken = await self.get_stoken(pwd_id, password)
        if not stoken:
            return

        is_owner, data_list = await self.get_detail(pwd_id, stoken)

        files_count = 0
        folders_count = 0
        files_list: List[str] = []
        folders_list: List[str] = []
        folders_map = {}
        files_id_list = []

        if data_list:
            total_files_count = len(data_list)
            for data in data_list:
                if data['dir']:
                    folders_count += 1
                    folders_list.append(data["file_name"])
                    folders_map[data["fid"]] = {
                        "file_name": data["file_name"],
                        "pdir_fid": data["pdir_fid"]
                    }
                else:
                    files_count += 1
                    files_list.append(data["file_name"])
                    files_id_list.append((data["fid"], data["file_name"]))

            custom_print(f'转存总数：{total_files_count}，文件数：{files_count}，文件夹数：{folders_count} | 支持嵌套')
            custom_print(f'文件转存列表：{files_list}')
            custom_print(f'文件夹转存列表：{folders_list}')

            fid_list = [i["fid"] for i in data_list]
            share_fid_token_list = [i["share_fid_token"] for i in data_list]

            if not self.folder_id:
                custom_print('保存目录ID不合法，请重新获取，如果无法获取，请输入0作为文件夹ID')
                return

            if download:
                if is_owner == 0:
                    custom_print(
                        '下载文件必须是自己的网盘内文件，请先将文件转存至网盘中，然后再从自己网盘中获取分享地址进行下载')
                    return
                return
            else:
                if is_owner == 1:
                    custom_print('网盘中已经存在该文件，无需再次转存')
                    return

                task_id = await self.get_share_save_task_id(pwd_id, stoken, fid_list, share_fid_token_list,
                                                            to_pdir_fid=self.folder_id)
                result = await self.submit_task(task_id)
                return result

    @log_function_call
    async def get_share_save_task_id(self, pwd_id: str, stoken: str, first_ids: List[str], share_fid_tokens: List[str],
                                     to_pdir_fid: str = '0') -> str:
        """
        生成文件转存的任务ID
        """
        task_url = "https://drive.quark.cn/1/clouddrive/share/sharepage/save"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "__dt": random.randint(600, 9999),
            "__t": get_timestamp(13),
        }
        data = {"fid_list": first_ids,
                "fid_token_list": share_fid_tokens,
                "to_pdir_fid": to_pdir_fid,
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": "0",
                "scene": "link"}

        async with httpx.AsyncClient() as client:
            timeout = httpx.Timeout(60.0, connect=60.0)
            response = await client.post(task_url, json=data, headers=self.headers, params=params, timeout=timeout)
            json_data = response.json()
            task_id = json_data['data']['task_id']
            custom_print(f'获取任务ID：{task_id}')
            return task_id

    @log_function_call
    async def submit_task(self, task_id: str, retry: int = 10) -> Union[
        bool, Dict[str, Union[str, Dict[str, Union[int, str]]]]]:
        """
        提交转存任务（带重试机制）
        """
        for i in range(retry):
            await asyncio.sleep(random.randint(1, 2))
            custom_print(f'第{i + 1}次提交任务')
            submit_url = (f"https://drive-pc.quark.cn/1/clouddrive/task?pr=ucpro&fr=pc&uc_param_str=&task_id={task_id}"
                          f"&retry_index={i}&__dt=21192&__t={get_timestamp(13)}")

            async with httpx.AsyncClient() as client:
                timeout = httpx.Timeout(60.0, connect=60.0)
                response = await client.get(submit_url, headers=self.headers, timeout=timeout)
                json_data = response.json()

            if json_data['message'] == 'ok':
                if json_data['data']['status'] == 2:
                    if 'to_pdir_name' in json_data['data']['save_as']:
                        folder_name = json_data['data']['save_as']['to_pdir_name']
                    else:
                        folder_name = '根目录'

                    if json_data['data']['task_title'] == '分享-转存':
                        custom_print(f"结束任务ID：{task_id}")
                        custom_print(f'文件保存位置：{folder_name} 文件夹')
                    return json_data
            else:
                if json_data['code'] == 32003 and 'capacity limit' in json_data['message']:
                    custom_print("转存失败，网盘容量不足！请注意当前已成功保存的个数，避免重复保存", error_msg=True)
                elif json_data['code'] == 41013:
                    custom_print(f"网盘文件夹不存在，请重新运行按3切换保存目录后重试！", error_msg=True)
                else:
                    custom_print(f"错误信息：{json_data['message']}", error_msg=True)
                input(f'[{get_datetime()}] 已退出程序')
                sys.exit()

    @log_function_call
    async def get_share_task_id(self, fid: str, file_name: str, url_type: int = 1, expired_type: int = 2,
                                password: str = '') -> str:
        """
        生成文件夹分享的任务ID
        """
        json_data = {
            "fid_list": fid,
            "title": file_name,
            "url_type": url_type,
            "expired_type": expired_type
        }
        if url_type == 2:
            if password:
                json_data["passcode"] = password
            else:
                json_data["passcode"] = generate_random_code()

        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': '',
        }

        async with httpx.AsyncClient() as client:
            timeout = httpx.Timeout(60.0, connect=60.0)
            response = await client.post('https://drive-pc.quark.cn/1/clouddrive/share', params=params,
                                         json=json_data, headers=self.headers, timeout=timeout)
            json_data = response.json()
            return json_data['data']['task_id']

    @log_function_call
    async def get_share_id(self, task_id: str) -> str:
        """
        根据分享任务ID获取分享标识share_id
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                print(f'开始执行get_share_id，第{retry_count + 1}次尝试')
                params = {
                    'pr': 'ucpro',
                    'fr': 'pc',
                    'uc_param_str': '',
                    'task_id': task_id,
                    'retry_index': str(retry_count),
                }

                async with httpx.AsyncClient() as client:
                    timeout = httpx.Timeout(60.0, connect=60.0)
                    response = await client.get(
                        'https://drive-pc.quark.cn/1/clouddrive/task',
                        params=params,
                        headers=self.headers,
                        timeout=timeout
                    )
                    response.raise_for_status()

                    json_data = response.json()

                    if not json_data.get('data') or not json_data['data'].get('share_id'):
                        raise ValueError("获取的share_id为空或不存在")

                    share_id = json_data['data']['share_id']
                    return share_id

            except Exception as e:
                retry_count += 1
                print(f'第{retry_count}次尝试失败: {str(e)}')

                if retry_count < max_retries:
                    await asyncio.sleep(2)
                else:
                    raise Exception(f"经过{max_retries}次重试后仍无法获取有效的share_id") from e

    @log_function_call
    async def submit_share(self, share_id: str) -> tuple:
        """
        根据share_id生成最终的分享链接
        """
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': '',
        }

        json_data = {
            'share_id': share_id,
        }
        async with httpx.AsyncClient() as client:
            timeout = httpx.Timeout(60.0, connect=60.0)
            response = await client.post('https://drive-pc.quark.cn/1/clouddrive/share/password', params=params,
                                         json=json_data, headers=self.headers, timeout=timeout)
            json_data = response.json()
            share_url = json_data['data']['share_url']
            title = json_data['data']['title']
            size = json_data['data']['size']
            size = format_size(size)

            if 'passcode' in json_data['data']:
                share_url = share_url + f"?pwd={json_data['data']['passcode']}"
            return share_url, title, size

    @log_function_call
    async def share_run(self, share_fid: str, folder_id: Union[str, None] = None, url_type: int = 1,
                        expired_type: int = 2, password: str = '', traverse_depth: int = 2):
        """
        批量生成文件夹分享链接（支持多级目录遍历）
        """
        first_dir = ''
        second_dir = ''
        try:
            self.folder_id = folder_id
            custom_print(f'准备分享的fid：{share_fid}')
            pwd_id = share_fid
            first_page = 1
            n = 0
            error = 0
            os.makedirs('share', exist_ok=True)
            save_share_path = 'share/share_url.txt'
            save_share_total_path = 'share/share_total.txt'

            safe_copy(save_share_path, 'share/share_url_backup.txt')
            with open(save_share_path, 'w+', encoding='utf-8'):
                pass

            if traverse_depth == 0:
                try:
                    custom_print('开始分享页面中所有根目录')
                    custom_print(pwd_id)
                    task_id = await self.get_share_task_id(pwd_id, "根目录", url_type=url_type,
                                                           expired_type=expired_type,
                                                           password=password)
                    share_id = await self.get_share_id(task_id)
                    share_url, title, size = await self.submit_share(share_id)

                    with open(save_share_path, 'w+', encoding='utf-8') as f:
                        content = f'1 | {title} | {share_url}'
                        f.write(content + '\n')
                        custom_print(f'分享 {title} 成功')
                    return {'title': title, 'share_url': share_url, 'size': size}
                except Exception as e:
                    print('分享失败：', e)
                    return

            while True:
                json_data = await self.get_sorted_file_list(pwd_id, page=str(first_page), size='50', fetch_total='1',
                                                            sort='file_type:asc,file_name:asc')
                for i1 in json_data['data']['list']:
                    if i1['dir']:
                        first_dir = i1['file_name']

                        if traverse_depth == 1:
                            n += 1
                            share_success = False
                            share_error_msg = ''
                            fid = ''

                            for i in range(3):
                                try:
                                    custom_print(f'{n}.开始分享 {first_dir} 文件夹')
                                    random_time = random.choice([0.5, 1, 1.5, 2])
                                    await asyncio.sleep(random_time)
                                    fid = i1['fid']

                                    task_id = await self.get_share_task_id(fid, first_dir, url_type=url_type,
                                                                           expired_type=expired_type,
                                                                           password=password)
                                    share_id = await self.get_share_id(task_id)
                                    share_url, title, size = await self.submit_share(share_id)

                                    with open(save_share_path, 'a', encoding='utf-8') as f:
                                        content = f'{n} | {first_dir} | {share_url}'
                                        f.write(content + '\n')
                                        custom_print(f'{n}.分享成功 {first_dir} 文件夹')
                                        share_success = True
                                        break
                                    with open(save_share_total_path, 'a', encoding='utf-8') as f:
                                        content = f'{n} | {first_dir} | {share_url}'
                                        f.write(content + '\n')
                                except Exception as e:
                                    share_error_msg = e
                                    error += 1

                            if not share_success:
                                print('分享失败：', share_error_msg)
                                save_config('./share/share_error.txt',
                                            content=f'{error}.{first_dir} 文件夹\n', mode='a')
                                save_config('./share/retry.txt',
                                            content=f'{n} | {first_dir} | {fid}\n', mode='a')
                            continue

                        second_page = 1
                        while True:
                            json_data2 = await self.get_sorted_file_list(i1['fid'], page=str(second_page),
                                                                         size='50', fetch_total='1',
                                                                         sort='file_type:asc,file_name:asc')
                            for i2 in json_data2['data']['list']:
                                if i2['dir']:
                                    n += 1
                                    share_success = False
                                    share_error_msg = ''
                                    fid = ''

                                    for i in range(3):
                                        try:
                                            second_dir = i2['file_name']
                                            custom_print(f'{n}.开始分享 {first_dir}/{second_dir} 文件夹')
                                            random_time = random.choice([0.5, 1, 1.5, 2])
                                            await asyncio.sleep(random_time)
                                            fid = i2['fid']

                                            task_id = await self.get_share_task_id(fid, second_dir, url_type=url_type,
                                                                                   expired_type=expired_type,
                                                                                   password=password)
                                            share_id = await self.get_share_id(task_id)
                                            share_url, title, size = await self.submit_share(share_id)

                                            with open(save_share_path, 'a', encoding='utf-8') as f:
                                                content = f'{n} | {first_dir} | {second_dir} | {share_url}'
                                                f.write(content + '\n')
                                                custom_print(f'{n}.分享成功 {first_dir}/{second_dir} 文件夹')
                                                share_success = True
                                                break
                                            with open(save_share_total_path, 'a', encoding='utf-8') as f:
                                                content = f'{n} | {first_dir} | {share_url}'
                                                f.write(content + '\n')
                                        except Exception as e:
                                            share_error_msg = e
                                            error += 1

                                    if not share_success:
                                        print('分享失败：', share_error_msg)
                                        save_config('./share/share_error.txt',
                                                    content=f'{error}.{first_dir}/{second_dir} 文件夹\n', mode='a')
                                        save_config('./share/retry.txt',
                                                    content=f'{n} | {first_dir} | {second_dir} | {fid}\n', mode='a')

                            second_total = json_data2['metadata']['_total']
                            second_size = json_data2['metadata']['_size']
                            second_page = json_data2['metadata']['_page']
                            if second_size * second_page >= second_total:
                                break
                            second_page += 1

                second_total = json_data['metadata']['_total']
                second_size = json_data['metadata']['_size']
                second_page = json_data['metadata']['_page']
                if second_size * second_page >= second_total:
                    break
                first_page += 1

            custom_print(f"总共分享了 {n} 个文件夹，已经保存至 {save_share_path}")

        except Exception as e:
            print('分享失败：', e)
            with open('./share/share_error.txt', 'a', encoding='utf-8') as f:
                f.write(f'{first_dir}/{second_dir} 文件夹')

    async def get_sorted_file_list(self, pdir_fid='0', page='1', size='100', fetch_total='false',
                                   sort='') -> Dict[str, Any]:
        """
        获取个人网盘中的文件/文件夹列表
        """
        params = {
            'pr': 'ucpro',
            'fr': 'pc',
            'uc_param_str': '',
            'pdir_fid': pdir_fid,
            '_page': page,
            '_size': size,
            '_fetch_total': fetch_total,
            '_fetch_sub_dirs': '1',
            '_sort': sort,
            '__dt': random.randint(100, 9999),
            '__t': get_timestamp(13),
        }

        async with httpx.AsyncClient() as client:
            timeout = httpx.Timeout(60.0, connect=60.0)
            response = await client.get('https://drive-pc.quark.cn/1/clouddrive/file/sort', params=params,
                                        headers=self.headers, timeout=timeout)
            json_data = response.json()
            return json_data


def log_print(message, level="INFO"):
    """带时间戳的日志打印函数"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_message = f"[{timestamp}] [{level}] {message}"
    print(log_message)
    return log_message


def load_config():
    """加载配置"""
    log_print("开始加载配置...")
    try:
        json_data = read_config(f'{CONFIG_DIR}/config.json', 'json')
        if json_data:
            log_print(f"配置文件加载成功", "DEBUG")
        else:
            log_print("配置文件为空或不存在", "WARNING")
    except Exception as e:
        log_print(f"加载配置失败: {str(e)}", "ERROR")


def save_api_cache(data):
    """保存API数据到缓存"""
    try:
        cache_dir = os.path.dirname(CACHE_FILE)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        cache_data = {
            'timestamp': time.time(),
            'data': data
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        log_print(f"API数据已缓存到 {CACHE_FILE}", "DEBUG")
    except Exception as e:
        log_print(f"保存API缓存失败: {str(e)}", "WARNING")


def is_cache_expired(cache_file):
    """检查缓存是否过期"""
    try:
        if not os.path.exists(cache_file):
            return True
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        if 'timestamp' not in cache_data:
            return True
        cache_age_hours = (time.time() - cache_data['timestamp']) / 3600
        is_expired = cache_age_hours > CACHE_EXPIRE_HOURS
        if is_expired:
            log_print(f"缓存已过期（{cache_age_hours:.1f}小时 > {CACHE_EXPIRE_HOURS}小时），将重新获取", "INFO")
        else:
            log_print(f"缓存有效（{cache_age_hours:.1f}小时 < {CACHE_EXPIRE_HOURS}小时）", "DEBUG")
        return is_expired
    except Exception as e:
        log_print(f"检查缓存过期时间失败: {str(e)}", "WARNING")
        return True


def load_api_cache():
    """从缓存加载API数据"""
    try:
        if not os.path.exists(CACHE_FILE):
            log_print(f"缓存文件不存在: {CACHE_FILE}", "WARNING")
            return None
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        if 'data' in cache_data:
            data = cache_data['data']
            log_print(f"已从缓存加载API数据，共 {len(data)} 条记录", "INFO")
            return data
        else:
            log_print("缓存格式不正确", "WARNING")
            return None
    except Exception as e:
        log_print(f"加载API缓存失败: {str(e)}", "WARNING")
        return None


def fetch_api_data(force_refresh=False):
    """获取API数据，优先使用本地缓存"""
    log_print("开始获取API数据...")

    # 优先使用本地缓存
    if not force_refresh:
        if not is_cache_expired(CACHE_FILE):
            cached_data = load_api_cache()
            if cached_data:
                log_print(f"优先使用本地缓存，共 {len(cached_data)} 条记录", "SUCCESS")
                return cached_data
            else:
                log_print("本地缓存不存在或为空，尝试请求API", "INFO")
        else:
            log_print("缓存已过期，将重新获取", "INFO")

    # 缓存不可用或强制刷新时，请求API
    try:
        log_print("正在请求 https://api.iyuns.com/api/wpysso ...")
        response = requests.get('https://api.iyuns.com/api/wpysso', timeout=30)
        response.raise_for_status()
        api_data = response.json()

        if api_data.get('code') == 0:
            quark_data = api_data.get('data', {}).get('merged_by_type', {}).get('quark', [])
            if quark_data:
                log_print(f"API请求成功，获取到 {len(quark_data)} 条夸克链接", "SUCCESS")
                save_api_cache(quark_data)
                return quark_data
            else:
                log_print("API返回数据为空", "WARNING")
                # 尝试返回缓存（虽然之前已经检查过，但以防缓存被更新）
                cached_data = load_api_cache()
                if cached_data:
                    log_print(f"回退到本地缓存，共 {len(cached_data)} 条记录", "INFO")
                    return cached_data
        else:
            log_print(f"API返回错误码: {api_data.get('code')}", "WARNING")
            cached_data = load_api_cache()
            if cached_data:
                log_print(f"回退到本地缓存，共 {len(cached_data)} 条记录", "INFO")
                return cached_data
    except requests.exceptions.Timeout:
        log_print("API请求超时", "WARNING")
        cached_data = load_api_cache()
        if cached_data:
            log_print(f"回退到本地缓存，共 {len(cached_data)} 条记录", "INFO")
            return cached_data
    except requests.exceptions.RequestException as e:
        log_print(f"API请求失败: {str(e)}", "WARNING")
        cached_data = load_api_cache()
        if cached_data:
            log_print(f"回退到本地缓存，共 {len(cached_data)} 条记录", "INFO")
            return cached_data
    except Exception as e:
        log_print(f"API解析失败: {str(e)}", "WARNING")
        cached_data = load_api_cache()
        if cached_data:
            log_print(f"回退到本地缓存，共 {len(cached_data)} 条记录", "INFO")
            return cached_data

    log_print("API和缓存都不可用", "ERROR")
    return None


def send_wechat_notification(webhook_url, shares):
    """发送企业微信通知 - 每个note对应一个url"""
    log_print(f"准备发送企业微信通知，分享数量: {len(shares)}")

    if not webhook_url:
        msg = '未提供企业微信webhook地址'
        log_print(msg, "WARNING")
        return {'success': False, 'message': msg}

    if not shares:
        msg = '没有成功分享的链接'
        log_print(msg, "WARNING")
        return {'success': False, 'message': msg}

    content_lines = []
    content_lines.append("【夸克网盘转存分享通知】")
    content_lines.append("")
    content_lines.append(f"本次共转存 {len(shares)} 个文件：")
    content_lines.append("")

    for i, share in enumerate(shares, 1):
        note = share.get('note', '未知标题')
        share_url = share.get('share_url', '')
        content_lines.append(f"{i}. {note}")
        content_lines.append(f"   {share_url}")
        content_lines.append("")

    content = "\n".join(content_lines)

    log_print("=" * 60)
    log_print("即将发送到企业微信的内容:")
    print(content)
    log_print("=" * 60)

    wechat_data = {
        "msgtype": "text",
        "text": {
            "content": content.strip()
        }
    }

    try:
        log_print(f"正在发送企业微信通知到: {webhook_url[:50]}...")
        response = requests.post(webhook_url, json=wechat_data, timeout=10)
        response.raise_for_status()
        msg = '企业微信通知发送成功'
        log_print(msg, "SUCCESS")
        return {'success': True, 'message': msg}
    except Exception as e:
        msg = f'企业微信通知发送失败: {str(e)}'
        log_print(msg, "ERROR")
        return {'success': False, 'message': msg}


async def batch_save_and_share(count=5, wechat_webhook_url=WEBHOOK_URL):
    """
    从 https://api.iyuns.com/api/wpysso 获取链接，随机选取n个转存到根目录并分享
    """
    log_print("=" * 60)
    log_print("开始执行批量转存分享任务")
    log_print(f"选取数量: {count}")
    log_print(f"企业微信Webhook: {'已配置' if wechat_webhook_url else '未配置'}")
    log_print("=" * 60)

    os.makedirs(CONFIG_DIR, exist_ok=True)
    load_config()

    log_print("初始化夸克文件管理器...")
    try:
        quark_file_manager = QuarkPanFileManager(headless=False, slow_mo=500)
        log_print("夸克文件管理器初始化成功")
    except Exception as e:
        log_print(f"初始化夸克文件管理器失败: {str(e)}", "ERROR")
        return {
            'code': 500,
            'message': f'初始化失败: {str(e)}'
        }

    try:
        quark_data = fetch_api_data()
        if not quark_data:
            msg = '无法获取API数据且缓存不可用'
            log_print(msg, "ERROR")
            return {
                'code': 400,
                'message': msg
            }

        if len(quark_data) < count:
            log_print(f"链接数量不足，调整选取数量为: {len(quark_data)}", "WARNING")
            count = len(quark_data)

        selected_items = random.sample(quark_data, count)
        log_print(f"随机选取了 {count} 个链接，列表如下:")
        for i, item in enumerate(selected_items, 1):
            log_print(f"  [{i}] {item.get('note', '无标题')} - {item['url'][:50]}...")

        log_print("=" * 60)
        log_print("开始转存文件到根目录...")
        save_results = []
        success_count = 0

        for index, item in enumerate(selected_items):
            url = item['url']
            note = item.get('note', '')
            try:
                log_print(f"转存中 [{index+1}/{count}]: {note}")
                result = await quark_file_manager.run(url.strip(), '0')
                file_ids = result['data']['save_as']['save_as_top_fids']
                save_results.append({
                    "index": index + 1,
                    "url": url,
                    "note": note,
                    "status": "success",
                    "result": result,
                    "file_id": file_ids
                })
                success_count += 1
                log_print(f"转存成功 [{index+1}/{count}]: {note} - 文件ID: {file_ids}", "SUCCESS")
            except Exception as e:
                save_results.append({
                    "index": index + 1,
                    "url": url,
                    "note": note,
                    "status": "error",
                    "message": str(e),
                    "file_id": None
                })
                log_print(f"转存失败 [{index+1}/{count}]: {note} - {str(e)}", "ERROR")

        log_print(f"转存完成，成功: {success_count}/{count}")

        successful_file_ids = [
            fid
            for item in save_results
            if item['status'] == 'success' and isinstance(item['file_id'], list) and item['file_id'] is not None
            for fid in item['file_id']
        ]

        if not successful_file_ids:
            msg = '所有文件转存失败，无法生成分享链接'
            log_print(msg, "ERROR")
            return {
                'code': 400,
                'message': msg,
                'save_results': save_results
            }

        log_print(f"共收集到 {len(successful_file_ids)} 个成功转存的文件ID")

        log_print("=" * 60)
        log_print("开始生成分享链接...")
        share_results = []
        share_success_count = 0

        for save_result in save_results:
            try:
                if save_result['status'] == 'error':
                    share_results.append({
                        'index': save_result['index'],
                        'note': save_result['note'],
                        'url': save_result['url'],
                        'status': 'error',
                        'message': '转存失败，无法生成分享链接'
                    })
                    continue

                file_id = save_result['result']['data']['save_as']['save_as_top_fids']
                original_file_count = len(file_id)

                delay = random.random() * 4
                log_print(f"[{save_result['index']}] 等待 {delay:.2f} 秒后生成分享链接")
                time.sleep(delay)

                log_print(f"[{save_result['index']}] 正在生成分享链接，文件数量: {len(file_id)}")
                result = await quark_file_manager.share_run(
                    file_id,
                    folder_id='0',
                    url_type=1,
                    expired_type=4,
                    password='',
                    traverse_depth=0
                )

                if isinstance(result, dict):
                    result['index'] = save_result['index']
                    result['note'] = save_result['note']
                    result['original_url'] = save_result['url']

                share_results.append(result)
                share_success_count += 1

                title = result.get('title', save_result['note'])
                share_url = result.get('share_url', '')
                log_print(f"分享成功 [{save_result['index']}]: {title} - {share_url}", "SUCCESS")

                os.system(f'{KUAKE_CLI} upload "333333.pdf" "/{title}/333333.pdf"')

                try:
                    os.makedirs('share', exist_ok=True)
                    with open('share/share_url_total.txt', 'a', encoding='utf-8') as file:
                        file.write(f"{title}  |  {share_url}\n")
                    log_print(f"分享结果已保存到 share/share_url_total.txt", "DEBUG")
                except Exception as e:
                    log_print(f"保存分享结果失败: {str(e)}", "WARNING")

            except Exception as e:
                share_results.append({
                    'index': save_result.get('index', len(share_results) + 1),
                    'note': save_result.get('note', ''),
                    'url': save_result.get('url', 'unknown'),
                    'status': 'error',
                    'message': f'生成分享链接失败: {str(e)}'
                })
                log_print(f"分享失败 [{save_result.get('index', len(share_results))}]: {save_result.get('note', '')} - {str(e)}", "ERROR")

        log_print(f"分享完成，成功: {share_success_count}/{len(save_results)}")

        log_print("=" * 60)
        wechat_result = None
        if wechat_webhook_url:
            success_shares = [r for r in share_results if isinstance(r, dict) and 'share_url' in r]
            wechat_result = send_wechat_notification(wechat_webhook_url, success_shares)
        else:
            log_print("未配置企业微信webhook，跳过通知", "INFO")

        log_print("=" * 60)
        log_print("批量转存分享任务完成")
        log_print(f"选取数量: {count}")
        log_print(f"转存成功: {success_count}")
        log_print(f"分享成功: {share_success_count}")
        if wechat_result:
            log_print(f"企业微信通知: {'成功' if wechat_result['success'] else '失败'} - {wechat_result['message']}")
        log_print("=" * 60)

        return {
            'code': 200,
            'message': '批量转存分享操作完成',
            'total_selected': count,
            'save_success_count': success_count,
            'share_success_count': share_success_count,
            'save_results': save_results,
            'share_results': share_results,
            'wechat_result': wechat_result
        }

    except Exception as e:
        log_print(f"批量转存分享失败: {str(e)}", "ERROR")
        log_print(f"异常堆栈:\n{traceback.format_exc()}", "ERROR")
        return {
            'code': 500,
            'message': f'服务器错误: {str(e)}'
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='批量转存分享夸克网盘链接')
    parser.add_argument('--count', type=int, default=DEFAULT_COUNT, help='随机选取的文件数量')
    parser.add_argument('--wechat-url', type=str, default=WEBHOOK_URL, help='企业微信webhook地址')
    args = parser.parse_args()

    log_print(f"启动批量转存分享脚本，选取 {args.count} 个文件")
    result = asyncio.run(batch_save_and_share(count=args.count, wechat_webhook_url=args.wechat_url))

    print("\n" + "=" * 60)
    print("【最终结果摘要】")
    print(f"状态码: {result['code']}")
    print(f"消息: {result['message']}")
    print(f"选取数量: {result['total_selected']}")
    print(f"转存成功: {result['save_success_count']}")
    print(f"分享成功: {result['share_success_count']}")
    if result.get('wechat_result'):
        print(f"企业微信: {'✓ 成功' if result['wechat_result']['success'] else '✗ 失败'}")
        print(f"         {result['wechat_result']['message']}")
    print("=" * 60)
