# KnowLink Error Codes

## Auth

- `auth.token_missing`: 缺少 Bearer token
- `auth.token_invalid`: Bearer token 不匹配 demo token

## Common

- `common.validation_error`: 请求体字段校验失败
- `common.not_found`: 资源不存在
- `common.idempotency_replay`: 命中幂等回放

## Recommendation

- `recommendation.catalog_not_found`: 推荐目录项不存在
- `recommendation.no_match`: 当前筛选条件下没有推荐结果

## Course And Resource

- `course.not_found`: 课程不存在
- `resource.not_found`: 资源不存在
- `resource.invalid_payload`: 上传完成回调字段不完整

## Bilibili

- `bilibili.not_implemented`: B 站导入与扫码登录接口已预留，但当前服务尚未接通

## Pipeline

- `pipeline.not_ready`: 当前课程状态不允许发起解析
- `pipeline.parse_run_not_found`: 解析版本不存在

## Inquiry And Handout

- `inquiry.course_not_ready`: 课程尚未进入问询阶段
- `handout.not_found`: 讲义版本不存在
- `handout.no_active_version`: 当前课程没有可用讲义

## QA / Quiz / Review

- `qa.block_not_found`: 讲义块不存在
- `quiz.not_found`: 测验不存在
- `review.run_not_found`: 复习任务重算记录不存在
