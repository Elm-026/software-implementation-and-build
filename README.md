# 校园二手交易系统

实验三“软件实现与构建”的校园二手交易系统实现，包含桌面端和可直接浏览的 Web 端。

## 技术栈

- Python 3.12
- Tkinter 桌面界面
- Python 标准库 HTTP 服务、原生 HTML/CSS/JavaScript Web 界面
- SQLite 持久化存储
- `unittest`、`py_compile` 和标准库并发测试

## 运行

```powershell
python code/app.py
```

启动 Web 端（默认访问 `http://127.0.0.1:8080`）：

```powershell
python web_app.py
```

Web 端支持游客浏览商品、搜索筛选和查看详情；预约购买或发布闲置时再登录或注册。

## 测试

```powershell
python -m unittest discover -s code/tests -v
```

## 目录

- `code/campus_market/domain` 领域模型和枚举
- `code/campus_market/infra` SQLite 数据库和仓储
- `code/campus_market/services` 认证、商品、审核、预约交易、日志和统计服务
- `code/campus_market/ui` Tkinter 工作区
- `code/tests` 单元测试和并发测试
- `web` Web 端页面、样式和交互脚本
- `web_app.py` Web 端 HTTP 服务与 API 路由
- `UML` 实验二 UML 源文件与图像

