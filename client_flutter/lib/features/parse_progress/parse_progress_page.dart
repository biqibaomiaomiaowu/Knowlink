import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
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
      activeTab: KnowLinkTab.parse,
      courseId: widget.courseId,
      body: ListView(
        children: [
          _ParseHero(courseId: widget.courseId),
          const SizedBox(height: 20),
          _ParseCommandCard(
            hasStartError: state.startRequest.hasError,
            startError: state.startRequest.error,
            isBusy: state.isStarting || state.isPolling,
            isRefreshing: state.isRefreshing,
            onStart: () => notifier.startAndPoll(widget.courseId),
            onRefresh: () => notifier.refresh(widget.courseId),
          ),
          const SizedBox(height: 18),
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
                padding: EdgeInsets.all(22),
                child: Text('点击发起解析后，这里会显示资源校验、字幕提取、文档解析和向量化进度。'),
              ),
            )
          else ...[
            _StatusSummaryCard(status: status),
            const SizedBox(height: 18),
            _StepListCard(steps: status.steps),
            const SizedBox(height: 18),
            LayoutBuilder(
              builder: (context, constraints) {
                final output = _ParseOutputCard(status: status);
                final next = _NextActionCard(
                  courseId: widget.courseId,
                  status: status,
                );
                if (constraints.maxWidth < 900) {
                  return Column(
                    children: [
                      output,
                      const SizedBox(height: 16),
                      next,
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: output),
                    const SizedBox(width: 18),
                    Expanded(child: next),
                  ],
                );
              },
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

class _ParseHero extends StatelessWidget {
  const _ParseHero({required this.courseId});

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Row(
          children: [
            SizedBox(
              height: 38,
              child: VerticalDivider(
                color: AppTheme.brandBlue,
                width: 18,
                thickness: 4,
              ),
            ),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                '解析进度',
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: 34,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          '课程 $courseId · 系统已开始理解课程与资料内容，请稍候片刻。',
          style: const TextStyle(
            color: AppTheme.muted,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _ParseCommandCard extends StatelessWidget {
  const _ParseCommandCard({
    required this.hasStartError,
    required this.startError,
    required this.isBusy,
    required this.isRefreshing,
    required this.onStart,
    required this.onRefresh,
  });

  final bool hasStartError;
  final Object? startError;
  final bool isBusy;
  final bool isRefreshing;
  final VoidCallback onStart;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: hasStartError
            ? AppErrorView(
                message: '发起解析失败：$startError',
                onRetry: onStart,
              )
            : Wrap(
                spacing: 10,
                runSpacing: 10,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  FilledButton.icon(
                    onPressed: isBusy ? null : onStart,
                    icon: const Icon(Icons.play_arrow),
                    label: Text(isBusy ? '正在解析' : '发起解析'),
                  ),
                  OutlinedButton.icon(
                    onPressed: isRefreshing || isBusy ? null : onRefresh,
                    icon: const Icon(Icons.refresh),
                    label: const Text('刷新状态'),
                  ),
                ],
              ),
      ),
    );
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
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '总体完成度',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${status.progressPct}',
                  style: const TextStyle(
                    color: AppTheme.brandBlue,
                    fontSize: 48,
                    fontWeight: FontWeight.w800,
                    height: 0.95,
                  ),
                ),
                const Padding(
                  padding: EdgeInsets.only(left: 2, bottom: 5),
                  child: Text(
                    '%',
                    style: TextStyle(
                      color: AppTheme.brandBlue,
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: 34),
                Expanded(
                  child: Column(
                    children: [
                      ProgressRail(value: status.progressPct / 100),
                      const SizedBox(height: 14),
                      const Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('0%', style: TextStyle(color: AppTheme.muted)),
                          Text('25%', style: TextStyle(color: AppTheme.muted)),
                          Text('50%', style: TextStyle(color: AppTheme.muted)),
                          Text('75%', style: TextStyle(color: AppTheme.muted)),
                          Text('100%', style: TextStyle(color: AppTheme.muted)),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              '${status.courseStatus.pipelineStage} · ${status.courseStatus.pipelineStatus}',
              style: const TextStyle(
                color: AppTheme.muted,
                fontWeight: FontWeight.w700,
              ),
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
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '课程与资料解析结果',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 18),
            if (steps.isEmpty)
              const Text('暂无步骤数据。')
            else
              LayoutBuilder(
                builder: (context, constraints) {
                  final width = constraints.maxWidth;
                  final columns = width >= 1100
                      ? 4
                      : width >= 780
                          ? 2
                          : 1;
                  return GridView.builder(
                    itemCount: steps.length,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: columns,
                      mainAxisExtent: 240,
                      crossAxisSpacing: 16,
                      mainAxisSpacing: 16,
                    ),
                    itemBuilder: (context, index) {
                      final step = steps[index];
                      return _StepResultCard(
                        step: step,
                        icon: _iconForStepStatus(step.status),
                        trailingText: _stepTrailingText(step),
                      );
                    },
                  );
                },
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

class _StepResultCard extends StatelessWidget {
  const _StepResultCard({
    required this.step,
    required this.icon,
    required this.trailingText,
  });

  final PipelineStepModel step;
  final IconData icon;
  final String trailingText;

  @override
  Widget build(BuildContext context) {
    final progress = (step.progressPct ?? _statusProgress(step.status)) / 100;
    final color = _statusColor(step.status);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              SoftIcon(icon: icon, color: color, size: 56),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  step.label,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Flexible(child: _StepSubtitle(step: step)),
          const SizedBox(height: 10),
          Text(
            trailingText,
            style: TextStyle(
              color: color,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          ProgressRail(value: progress, color: color),
        ],
      ),
    );
  }

  static int _statusProgress(String status) {
    return switch (status) {
      'succeeded' => 100,
      'running' => 68,
      'failed' => 100,
      'skipped' => 0,
      _ => 0,
    };
  }

  static Color _statusColor(String status) {
    return switch (status) {
      'succeeded' => const Color(0xFF16A34A),
      'failed' => const Color(0xFFDC2626),
      'running' => AppTheme.brandBlue,
      'skipped' => const Color(0xFF94A3B8),
      _ => AppTheme.muted,
    };
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
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          step.code,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: AppTheme.muted,
            fontWeight: FontWeight.w700,
          ),
        ),
        if (step.message != null && step.message!.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            step.message!,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
        if (failedResourceIds.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text(
            '失败资源：${failedResourceIds.join(', ')}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
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
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '来源解析结果',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 14),
            if (source != null) ...[
              _SourceResultRow(
                icon: Icons.play_circle_fill,
                label: '视频',
                value: source.videoReady ? '已完成' : '待处理',
                detail: '${source.organizedSourceCount} 个来源',
                completed: source.videoReady,
              ),
              const SizedBox(height: 8),
              _SourceResultRow(
                icon: Icons.description,
                label: '文档',
                value: source.outlineReady ? '已完成' : '进行中',
                detail: source.docTypes.isEmpty
                    ? '未返回类型'
                    : source.docTypes.join('、'),
                completed: source.outlineReady,
              ),
            ],
            if (knowledge != null) ...[
              const SizedBox(height: 8),
              _SourceResultRow(
                icon: Icons.hub_outlined,
                label: '知识映射',
                value: knowledge.status,
                detail:
                    '${knowledge.segmentCount} segments / ${knowledge.knowledgePointCount} points',
                completed: knowledge.status == 'succeeded',
              ),
            ],
            if (outline != null) ...[
              const SizedBox(height: 8),
              _SourceResultRow(
                icon: Icons.menu_book_outlined,
                label: '讲义目录',
                value: outline.status,
                detail:
                    '${outline.outlineItemCount} 项 / ${outline.generatedBlockCount} 个 block',
                completed: outline.status == 'succeeded',
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
        padding: const EdgeInsets.all(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '下一步：补齐讲义与练习',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 18),
            Text(
              isFailed ? '解析失败，请返回导入页检查资料后重试。' : '下一步动作：${status.nextAction}',
              style: const TextStyle(
                color: AppTheme.muted,
                fontSize: 15,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 18),
            const Wrap(
              spacing: 16,
              runSpacing: 16,
              children: [
                _NextPreview(
                    icon: Icons.auto_stories,
                    title: '讲义分段生成',
                    detail: '将随讲义 block 逐段补齐'),
                _NextPreview(
                    icon: Icons.functions,
                    title: '来源引用绑定',
                    detail: '为讲义、问答和测验绑定来源'),
                _NextPreview(
                    icon: Icons.fact_check,
                    title: '测验生成准备',
                    detail: '待讲义完成后生成练习题'),
              ],
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.end,
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

class _SourceResultRow extends StatelessWidget {
  const _SourceResultRow({
    required this.icon,
    required this.label,
    required this.value,
    required this.detail,
    required this.completed,
  });

  final IconData icon;
  final String label;
  final String value;
  final String detail;
  final bool completed;

  @override
  Widget build(BuildContext context) {
    final color = completed ? const Color(0xFF16A34A) : AppTheme.brandBlue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 16,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Text(
            detail,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(width: 18),
          StatusPill(
            label: value,
            color: color,
            icon: completed ? Icons.check : Icons.sync,
          ),
        ],
      ),
    );
  }
}

class _NextPreview extends StatelessWidget {
  const _NextPreview({
    required this.icon,
    required this.title,
    required this.detail,
  });

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 180,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          border: Border.all(color: AppTheme.line),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          children: [
            SoftIcon(icon: icon, size: 46),
            const SizedBox(height: 10),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.ink,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              detail,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.muted,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
