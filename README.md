# 校园二手交易系统

实验三“软件实现与构建”的 Python 桌面应用实现。

## 技术栈

- Python 3.12
- Tkinter 桌面界面
- SQLite 持久化存储
- `unittest`、`py_compile` 和标准库并发测试

## 运行

```powershell
python code/app.py
```

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
- `UML` 实验二 UML 源文件与图像
