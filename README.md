# 接口自动化测试框架（AeroTest）

接口测试用例全部写在 YAML 文件里，框架自动执行：发请求、检查返回结果对不对、跑前自动造数据、跑完自动清理。加一条用例就是加一个 YAML 文件，不用写 Python 代码。

数据由配套的测试数据工厂（另一个项目）提供：造的数据带批次号，跑完按批次删掉，哪怕用例失败了也保证清理。

## 主要功能

- **用例与代码分离**：请求地址、参数、预期结果都写在 YAML 里，测试同学改用例不用碰代码
- **一份用例测多组数据**：YAML 里写一个 `params` 列表，每组数据展开成一条用例
- **用例之间能传数据**：上一个接口返回的 token 可以提取出来，给下一个用例用
- **发请求**：统一处理超时、多环境切换、请求日志。查询类请求失败会自动重试，下单类请求失败不重试（避免重复下单）
- **检查结果**：内置 6 种检查方式——状态码、JSON 字段值、包含、正则格式、响应耗时、直接查数据库核对。加新检查方式就是加一个函数
- **自动造数和清理**：用例里声明要什么数据，框架自动调造数服务拿数据填给用例；造数服务挂了也不影响，自动改用本地准备好的数据文件
- **CI 质量门禁**：核心用例只要有一条没过，代码就不允许合并

## 环境要求

- Python 3.10+
- 被测的接口服务（示例用例打 httpbin.org）
- 测试数据工厂服务（只有用例声明了造数时才需要；挂了自动降级，不阻塞）

## 安装

```bash
pip install -r requirements.txt
cp config/config.example.yaml config/envs/test.yaml   # 填被测系统的地址
```

数据库密码这类敏感信息只写在本地配置里，不会提交到仓库。

## 框架自己的测试

```bash
python -m pytest tests -v          # 42 个单元测试，不用联网
```

默认只跑框架自身的测试；跑接口用例要加 `-m suite`。

## 跑接口用例

```bash
python -m pytest -m suite -v                        # 跑全部 YAML 用例
python -m pytest -m suite -v --env test             # 指定环境配置
python -m pytest -m suite --alluredir=allure-results   # 生成 Allure 报告
```

### 用例怎么写

```yaml
name: 查询用户
setup:                              # 跑之前先造数据（可选）
  - template: user                  # 用造数服务的哪个模板
    count: 1
    var: user_rows                  # 造出来的数据存到这个变量里
request:
  method: GET
  path: /user
  params:
    id: "${uid}"
extract:                            # 从返回结果里取值存下来（可选）
  token: $.data.token
assertions:                         # 预期结果，至少写一条
  - type: status_eq
    expected: 200
  - type: json_eq
    path: $.data.id
    expected: 42
params:                             # 多组数据，每组跑一遍（可选）
  - uid: 42
  - uid: 43
```

用例文件在启动时会先被检查一遍：请求方法是不是规定的五种、检查方式的名字写没写错、用到的 `${变量}` 有没有数据来源——写错了启动时就报错，不会跑到一半才挂。写了 `params` 的用例会按组数展开成多条，报告里名字带编号（如 `查询用户[0]`）。

## 配置文件

`config/envs/环境名.yaml`（模板见 `config/config.example.yaml`）：

```yaml
base_url: "https://httpbin.org"     # 被测系统地址
timeout: 10
retry: 2                            # 查询类请求最多重试几次
headers:
  Content-Type: "application/json"

data_factory:
  base_url: "http://127.0.0.1:8000"         # 造数服务地址
  fallback_dir: "testcases/fallback_data"   # 降级时用的本地数据目录

db:                                  # 查数据库核对用
  host: "127.0.0.1"
  port: 3306
  user: "root"
  password: ""
  database: "test"
```

## CI 质量门禁

```bash
python -m pytest -m suite --junitxml=reports/junit-suite.xml
python scripts/quality_gate.py reports/junit-suite.xml --min-rate 1.0
```

脚本解析测试报告，通过率不达标就返回失败状态，流水线据此拦下代码合并。GitLab CI 和 Jenkins 的参考配置在 `.gitlab-ci.yml` 和 `Jenkinsfile`。

## 项目结构

```
├── conftest.py            # pytest 集成：命令行选项、收集 YAML 用例、公共 fixtures
├── pytest.ini             # 默认跑框架测试，-m suite 跑接口用例
├── core/
│   ├── context.py         # 变量池：存变量、替换 ${}、从返回结果取值
│   ├── http_client.py     # 发请求：Session、重试、日志
│   ├── case_loader.py     # 读 YAML 用例、检查、按组展开
│   ├── assertions.py      # 各种检查方式的对照表
│   ├── data_provider.py   # 调造数服务、失败降级、回滚
│   ├── runner.py          # 串起一条用例的完整流程
│   ├── config.py          # 读环境配置
│   └── jsonpath.py        # 按路径从 JSON 里取值
├── testcases/             # YAML 用例 + 降级用的本地数据
├── tests/                 # 框架自身的 42 个单元测试
└── scripts/quality_gate.py
```

## 目前做不到的

- 查数据库的断言读的是 `config/config.yaml`，这个文件不存在时报错信息不够友好
- 造数联动依赖测试数据工厂服务在线，用例目前是串行执行的
- JSON 路径只支持 `$.a.b.0.c` 这种点号写法，不支持复杂的过滤语法
