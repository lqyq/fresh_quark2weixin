# 夸克网盘批量转存分享工具

这是一个用于批量转存夸克网盘链接并生成分享链接的工具，支持自动发送企业微信通知。

## 功能特性

- 从 API 获取夸克网盘分享链接
- 随机选取指定数量的链接进行转存
- 自动生成分享链接
- 支持配置引流文件
- 发送企业微信通知
- API 数据缓存机制（当 API 不可用时使用缓存）

## 环境要求

- Python 3.8+
- 依赖包：见 `requirements.txt`

## 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 playwright 浏览器
playwright install chromium
```

## 配置

### 方式一：环境变量

设置以下环境变量：

```bash
# 企业微信 Webhook URL（必填）
export WECHAT_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key"

# 引流文件概率（可选，默认 0）
export PROBABILITY=0.3

# 引流文件 ID（可选）
export YINLIU_FILE_ID="your_file_id"
```

### 方式二：配置文件

创建 `config/config.json` 文件：

```json
{
    "wechat_webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key",
    "probability": 0.3,
    "yinliufileid": "your_file_id"
}
```

### 方式三：命令行参数

```bash
python batch_share.py --count 5 --wechat-url "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key"
```

## 使用

### 首次使用（需要登录）

```bash
# 运行脚本，首次运行会弹出浏览器要求登录
python batch_share.py --count 5
```

### 命令行参数

```bash
python batch_share.py [选项]

选项：
  --count N        随机选取的文件数量（默认 5）
  --wechat-url URL 企业微信 Webhook 地址
  --probability P  引流文件添加概率（0-1，默认 0）
  --yinliu-id ID   引流文件 ID
```

## 项目结构

```
.
├── batch_share.py      # 主程序
├── requirements.txt    # 依赖列表
├── .gitignore         # Git 忽略配置
├── README.md          # 项目说明
├── config/            # 配置目录（自动创建）
│   └── config.json    # 配置文件
│   └── cookies.txt    # Cookie 文件（登录后自动生成）
├── cache/             # 缓存目录（自动创建）
│   └── api_cache.json # API 数据缓存
└── .github/
    └── workflows/
        └── daily-run.yml  # GitHub Actions 定时任务
```

## GitHub Actions 配置

项目包含一个 GitHub Actions Workflow，用于定时执行转存任务。

### 配置 Secrets

在 GitHub 仓库的 `Settings > Secrets and variables > Actions` 中添加以下 secrets：

- `WECHAT_WEBHOOK_URL` - 企业微信 Webhook 地址
- `QUARK_COOKIES` - 夸克网盘登录 Cookie（可选，用于无浏览器环境）

### Workflow 说明

- 每天 UTC 时间 00:00 自动执行
- 也可手动触发
- 执行结果会通过企业微信通知

## 注意事项

1. 首次运行需要在弹出的浏览器中登录夸克网盘
2. Cookie 会自动保存到 `config/cookies.txt`
3. 建议定期更新 Cookie（Cookie 过期后需要重新登录）
4. 请勿将 Cookie 或 Webhook URL 提交到版本控制系统

## License

MIT
