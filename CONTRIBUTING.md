# KnowLink 提交规范

本仓库统一使用严格的 Conventional Commits 规范，目标是让每次提交都能一眼看出改动类型、影响范围和具体内容。

适用范围：

- `server/`
- `client_flutter/`
- `schemas/`
- `docs/`
- 仓库根目录配置文件

## 1. 提交格式

统一格式：

```text
<type>(<scope>): <subject>
```

要求：

- `type` 必填，使用英文小写。
- `scope` 必填，使用英文小写。
- `subject` 必须使用中文，写清楚“做了什么”，不加句号。
- 标题保持简洁，尽量控制在一行内，不写无意义前缀和口语化描述。

示例：

```text
fix(api): 修正 progress 请求体中的重复 courseId
feat(flutter): 增加课程导入页资源列表展示
docs(docs): 补充 review task 完成接口说明
```

## 2. type 取值

只允许使用以下 `type`：

| type | 用途 |
|---|---|
| `feat` | 新增功能或新增可见能力 |
| `fix` | 修复 bug、兼容性问题或错误行为 |
| `docs` | 仅修改文档，不改业务逻辑 |
| `refactor` | 重构代码结构，不改变对外行为 |
| `test` | 新增或调整测试 |
| `chore` | 杂项维护，例如脚手架、小配置、依赖整理 |
| `build` | 构建系统、依赖构建、打包行为相关修改 |
| `ci` | CI 工作流、检查脚本、自动化流程相关修改 |

禁止使用：

- `update`
- `modify`
- `bugfix`
- `misc`
- `tmp`

## 3. scope 取值

`scope` 必填，并且必须落在明确的仓库模块内。

推荐取值：

| scope | 对应范围 |
|---|---|
| `api` | `server/api/**` 路由、依赖、响应封装 |
| `domain` | `server/domain/**` 服务、模型、仓储协议 |
| `schemas` | `server/schemas/**` 和请求/响应 DTO |
| `tasks` | `server/tasks/**` 异步任务、payload、worker |
| `infra` | `server/infra/**` 存储、认证、仓储实现、基础设施接入 |
| `ai` | `server/ai/**` AI pipeline、生成策略、schema 对接 |
| `parsers` | `server/parsers/**` 文档解析、归一化、抽取流程 |
| `flutter` | `client_flutter/**` 页面、Provider、路由、主题、网络层 |
| `docs` | `README.md`、`ARCHITECTURE.md`、`docs/**`、`TEAM_DIVISION.md` 等文档 |
| `repo` | 仓库级配置，例如 `.env.example`、`pyproject.toml`、`docker-compose.yml` |

选择规则：

- 只改一个模块时，使用最直接的 `scope`。
- 同时跨多个后端子模块但属于同一类行为时，优先用影响最大的 `scope`。
- 无法归入单一模块、且确实是仓库级改动时，使用 `repo`。
- 不要把页面名、类名、接口名直接当成 `scope`。

## 4. subject 写法

`subject` 必须满足以下规则：

- 使用中文动宾短句，例如“补充”“修正”“新增”“重构”“统一”。
- 只描述本次提交真正完成的事情。
- 不写“修改一下”“继续完善”“临时处理”“试试”这类模糊表达。
- 不重复 `type` 的含义，例如不要写 `fix(api): 修复 bug`。

推荐写法：

- `fix(api): 修正资源删除接口的不存在错误码`
- `refactor(domain): 拆分讲义生成状态聚合逻辑`
- `test(schemas): 补充 progress DTO 边界用例`

不推荐写法：

- `fix(api): 修复 bug`
- `chore(repo): 更新代码`
- `feat(flutter): 页面优化`

## 5. 正文与 Breaking Change

小改动允许只写标题。

以下情况必须补正文：

- 涉及多个文件且单看标题无法说明原因
- 改动影响现有接口、字段、任务状态或页面行为
- 需要说明兼容性、迁移方式或上下游影响

正文建议结构：

```text
<type>(<scope>): <subject>

改动：
- ...
- ...

原因：
- ...
```

存在破坏性变更时，必须显式标记：

```text
feat(schemas)!: 调整 progress 请求体字段结构

BREAKING CHANGE: POST /api/v1/courses/{courseId}/progress 不再接收 courseId 字段
```

## 6. 提交拆分原则

一个 commit 只做一类事情，不把无关内容混在一起。

必须遵守：

- 功能改动和纯文档改动分开提交
- 功能改动和纯测试改动尽量分开提交
- 重构和行为修复不要混成一个 commit
- 不要把批量换行符、空格、格式化噪音混入功能提交
- 不要顺手夹带无关文件修改

推荐做法：

- 先提交 DTO 或 contract 变更，再提交实现
- 前后端需要同步调整时，按一个清晰目标拆分，而不是按“谁改的文件”拆分
- 如果某次改动无法用一句话准确概括，说明它应该继续拆 commit

## 7. 合规示例

```text
feat(api): 增加课程资源列表查询接口
fix(schemas): 移除 progress 请求体中的重复 courseId
docs(docs): 补充 qa 会话消息查询接口说明
refactor(domain): 统一课程流程状态聚合入口
test(api): 补充资源删除失败场景测试
chore(repo): 补充本地开发环境示例配置
ci(repo): 增加后端测试工作流
build(repo): 调整 Docker 镜像启动命令
```

## 8. 不合规示例

以下写法不允许使用：

```text
update: 改了一些接口
fix: 修复 bug
feat(qa_page): 新增页面逻辑
docs: 更新文档
tmp(repo): 先这样
```

原因：

- 缺少 `scope`
- `type` 不在允许列表中
- `scope` 过细或不属于约定模块
- `subject` 过于模糊，无法说明真实改动

## 9. 提交前自检

提交前至少确认以下几点：

- commit 标题是否满足 `<type>(<scope>): <subject>`
- `type` 和 `scope` 是否来自允许列表
- 标题是否是中文且能准确表达改动
- 是否混入了无关文件、换行符噪音或临时调试内容
- 涉及接口、DTO、页面行为变化时，是否需要补正文或拆分提交

如果拿不准，优先把 commit 拆小，再写标题。
