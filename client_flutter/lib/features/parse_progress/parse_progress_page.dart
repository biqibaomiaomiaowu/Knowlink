import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../shared/models/pipeline_status.dart';
import '../../shared/providers/parse_progress_provider.dart';

class ParseProgressPage extends ConsumerStatefulWidget {
  const ParseProgressPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<ParseProgressPage> createState() => _ParseProgressPageState();
}

class _ParseProgressPageState extends ConsumerState<ParseProgressPage> {
  String? _lastCourseId;

  @override
  void initState() {
    super.initState();
    _scheduleRefresh();
  }

  @override
  void didUpdateWidget(covariant ParseProgressPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleRefresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(parseProgressProvider);
    final notifier = ref.read(parseProgressProvider.notifier);
    final status = state.pipelineStatus.valueOrNull;

    return AppScaffold(
      title: '解析进度',
      body: ListView(
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    '课程 ${widget.courseId}',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (state.startRequest.hasError)
                    AppErrorView(
                      message: '发起解析失败：${state.startRequest.error}',
                      onRetry: () => notifier.startAndPoll(widget.courseId),
                    )
                  else
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        FilledButton.icon(
                          onPressed: state.isStarting || state.isPolling
                              ? null
                              : () => notifier.startAndPoll(widget.courseId),
                          icon: const Icon(Icons.play_arrow),
                          label: Text(
                            state.isPolling ? '正在解析' : '发起解析',
                          ),
                        ),
                        OutlinedButton.icon(
                          onPressed: state.isRefreshing || state.isPolling
                              ? null
                              : () => notifier.refresh(widget.courseId),
                          icon: const Icon(Icons.refresh),
                          label: const Text('刷新状态'),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          if (state.pipelineStatus.isLoading)
            const AppLoadingView(label: '正在读取解析状态')
          else if (state.pipelineStatus.hasError)
            AppErrorView(
              message: '解析状态暂不可用：${state.pipelineStatus.error}',
              onRetry: () => notifier.refresh(widget.courseId),
            )
          else if (status == null)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('点击发起解析后，这里会显示资源校验、字幕提取、文档解析和向量化进度。'),
              ),
            )
          else ...[
            _StatusSummaryCard(status: status),
            const SizedBox(height: 16),
            _StepListCard(steps: status.steps),
            const SizedBox(height: 16),
            _ParseOutputCard(status: status),
            const SizedBox(height: 16),
            _NextActionCard(
              courseId: widget.courseId,
              status: status,
            ),
          ],
        ],
      ),
    );
  }

  void _scheduleRefresh() {
    if (_lastCourseId == widget.courseId) {
      return;
    }
    _lastCourseId = widget.courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(parseProgressProvider.notifier).refresh(widget.courseId);
    });
  }
}

class _StatusSummaryCard extends StatelessWidget {
  const _StatusSummaryCard({
    required this.status,
  });

  final PipelineStatusModel status;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '当前状态',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(value: status.progressPct / 100),
            const SizedBox(height: 8),
            Text(
              '${status.progressPct}% · '
              '${status.courseStatus.pipelineStage} · '
              '${status.courseStatus.pipelineStatus}',
            ),
            if (status.highlightSummary?.items.isNotEmpty ?? false) ...[
              const SizedBox(height: 12),
              ...status.highlightSummary!.items.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.check, size: 18),
                      const SizedBox(width: 8),
                      Expanded(child: Text(item)),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StepListCard extends StatelessWidget {
  const _StepListCard({
    required this.steps,
  });

  final List<PipelineStepModel> steps;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '解析步骤',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            if (steps.isEmpty)
              const Text('暂无步骤数据。')
            else
              ...steps.map(
                (step) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(_iconForStepStatus(step.status)),
                  title: Text(step.label),
                  subtitle: _StepSubtitle(step: step),
                  trailing: Text(_stepTrailingText(step)),
                ),
              ),
          ],
        ),
      ),
    );
  }

  IconData _iconForStepStatus(String status) {
    switch (status) {
      case 'succeeded':
        return Icons.check_circle_outline;
      case 'running':
        return Icons.sync;
      case 'failed':
        return Icons.error_outline;
      case 'skipped':
        return Icons.skip_next_outlined;
      default:
        return Icons.radio_button_unchecked;
    }
  }

  String _stepTrailingText(PipelineStepModel step) {
    final progressPct = step.progressPct;
    if (progressPct == null) {
      return step.status;
    }
    return '${step.status} · $progressPct%';
  }
}

class _StepSubtitle extends StatelessWidget {
  const _StepSubtitle({
    required this.step,
  });

  final PipelineStepModel step;

  @override
  Widget build(BuildContext context) {
    final failedResourceIds = step.failedResourceIds;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(step.code),
        if (step.message != null && step.message!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(step.message!),
        ],
        if (failedResourceIds.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text('失败资源：${failedResourceIds.join(', ')}'),
        ],
      ],
    );
  }
}

class _ParseOutputCard extends StatelessWidget {
  const _ParseOutputCard({
    required this.status,
  });

  final PipelineStatusModel status;

  @override
  Widget build(BuildContext context) {
    final source = status.sourceOverview;
    final knowledge = status.knowledgeMap;
    final outline = status.handoutOutline;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '解析产物',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            if (source != null)
              Text(
                '视频可用：${source.videoReady ? '是' : '否'} · '
                '目录可用：${source.outlineReady ? '是' : '否'} · '
                '资料类型：${source.docTypes.join(', ')}',
              ),
            if (knowledge != null) ...[
              const SizedBox(height: 8),
              Text(
                '知识映射：${knowledge.status} · '
                'segment ${knowledge.segmentCount} · '
                'knowledge point ${knowledge.knowledgePointCount}',
              ),
            ],
            if (outline != null) ...[
              const SizedBox(height: 8),
              Text(
                '讲义目录：${outline.status} · '
                '${outline.outlineItemCount} 项 · '
                '已生成 ${outline.generatedBlockCount} 个 block',
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _NextActionCard extends StatelessWidget {
  const _NextActionCard({
    required this.courseId,
    required this.status,
  });

  final String courseId;
  final PipelineStatusModel status;

  @override
  Widget build(BuildContext context) {
    final isFailed = status.courseStatus.pipelineStatus == 'failed';
    final canContinue = status.canEnterInquiry || status.canEnterHandoutOutline;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '下一步',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              isFailed
                  ? '解析失败，请返回导入页检查资料后重试。'
                  : 'nextAction: ${status.nextAction}',
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: canContinue
                      ? () => context.go('/courses/$courseId/inquiry')
                      : null,
                  icon: const Icon(Icons.tune),
                  label: const Text('进入问询'),
                ),
                OutlinedButton.icon(
                  onPressed: status.canEnterHandoutOutline
                      ? () => context.go('/courses/$courseId/handout')
                      : null,
                  icon: const Icon(Icons.menu_book_outlined),
                  label: const Text('查看讲义目录'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
