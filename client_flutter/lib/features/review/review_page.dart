import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/review_models.dart';
import '../../shared/models/review_state.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/review_provider.dart';

class ReviewPage extends ConsumerStatefulWidget {
  const ReviewPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<ReviewPage> createState() => _ReviewPageState();
}

class _ReviewPageState extends ConsumerState<ReviewPage> {
  String? _loadedCourseId;

  @override
  void initState() {
    super.initState();
    _scheduleLoad();
  }

  @override
  void didUpdateWidget(covariant ReviewPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleLoad();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(reviewProvider);
    return AppScaffold(
      title: 'AI 复习推荐',
      activeTab: KnowLinkTab.review,
      courseId: widget.courseId,
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Header(
              courseId: widget.courseId,
              state: state,
              onRefresh: () => ref.read(reviewProvider.notifier).load(
                    widget.courseId,
                  ),
              onRegenerate: () =>
                  ref.read(reviewProvider.notifier).regenerateAndPoll(
                        widget.courseId,
                        interval: const Duration(milliseconds: 20),
                      ),
            ),
            const SizedBox(height: 16),
            _ReviewBody(
              courseId: widget.courseId,
              state: state,
              onRetry: () => ref.read(reviewProvider.notifier).load(
                    widget.courseId,
                  ),
              onComplete: (taskId) =>
                  ref.read(reviewProvider.notifier).completeTask(
                        courseId: widget.courseId,
                        reviewTaskId: taskId,
                      ),
              onOpenSegment: (task) => _openSegment(task),
              onPractice: (entry) => _openPractice(entry),
            ),
          ],
        ),
      ),
    );
  }

  void _scheduleLoad() {
    if (_loadedCourseId == widget.courseId) {
      return;
    }
    _loadedCourseId = widget.courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(reviewProvider.notifier).load(widget.courseId);
    });
  }

  void _openSegment(ReviewTaskModel task) {
    final blockId = task.recommendedSegment?.blockId;
    if (blockId != null) {
      ref.read(activeBlockProvider.notifier).state = blockId;
      ref.read(handoutResumeTargetProvider.notifier).state =
          HandoutResumeTarget(
        courseId: widget.courseId,
        blockId: blockId,
      );
    } else {
      ref.read(handoutResumeTargetProvider.notifier).state = null;
    }
    context.go('/courses/${widget.courseId}/handout');
  }

  void _openPractice(PracticeEntryModel entry) {
    if (entry.type == 'quiz' && entry.targetId != null) {
      context.go('/quizzes/${entry.targetId}');
    }
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.courseId,
    required this.state,
    required this.onRefresh,
    required this.onRegenerate,
  });

  final String courseId;
  final ReviewState state;
  final VoidCallback onRefresh;
  final VoidCallback onRegenerate;

  @override
  Widget build(BuildContext context) {
    final runStatus = state.runStatusValue;
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const PageTitle(
            title: 'AI 复习推荐',
            subtitle: '根据测验结果、掌握度和可追溯来源，优先展示今天最值得处理的 Top3 复习任务。',
          ),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              StatusPill(label: '课程编号：$courseId'),
              if (runStatus != null)
                StatusPill(
                  label:
                      '生成 ${_statusLabel(runStatus.status)} · ${runStatus.generatedCount} 条',
                  color: _statusColor(runStatus.status),
                ),
              OutlinedButton.icon(
                onPressed: state.tasks.isLoading || state.isCompleting
                    ? null
                    : onRefresh,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
              FilledButton.icon(
                onPressed: state.isRegenerating || state.isCompleting
                    ? null
                    : onRegenerate,
                icon: state.isRegenerating
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.auto_awesome),
                label: Text(state.isRegenerating ? '生成中' : '重新生成复习'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ReviewBody extends StatelessWidget {
  const _ReviewBody({
    required this.courseId,
    required this.state,
    required this.onRetry,
    required this.onComplete,
    required this.onOpenSegment,
    required this.onPractice,
  });

  final String courseId;
  final ReviewState state;
  final VoidCallback onRetry;
  final void Function(int taskId) onComplete;
  final void Function(ReviewTaskModel task) onOpenSegment;
  final void Function(PracticeEntryModel entry) onPractice;

  @override
  Widget build(BuildContext context) {
    if (state.tasks.isLoading && state.tasksValue == null) {
      return const AppLoadingView(label: '正在加载复习任务...');
    }
    if (state.tasks.hasError) {
      return AppErrorView(
        message: '复习任务加载失败：${state.tasks.error}',
        onRetry: onRetry,
      );
    }
    if (state.regeneration.hasError) {
      return AppErrorView(
        message: '复习任务生成失败：${state.regeneration.error}',
        onRetry: onRetry,
      );
    }

    final tasks = state.tasksValue?.topThree ?? const <ReviewTaskModel>[];
    if (tasks.isEmpty) {
      return _EmptyReviewCard(courseId: courseId);
    }

    final wide = MediaQuery.sizeOf(context).width >= 980;
    final taskList = _TaskList(
      tasks: tasks,
      state: state,
      onComplete: onComplete,
      onOpenSegment: onOpenSegment,
      onPractice: onPractice,
    );
    final summary = _SummaryPanel(tasks: tasks, state: state);

    if (wide) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(flex: 3, child: taskList),
          const SizedBox(width: 16),
          Expanded(flex: 2, child: summary),
        ],
      );
    }

    return Column(
      children: [
        taskList,
        const SizedBox(height: 16),
        summary,
      ],
    );
  }
}

class _EmptyReviewCard extends StatelessWidget {
  const _EmptyReviewCard({
    required this.courseId,
  });

  final String courseId;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('暂无复习任务', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          Text(
            '课程 $courseId 还没有可展示的复习任务。完成测验后可生成 Top3 复习建议。',
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _TaskList extends StatelessWidget {
  const _TaskList({
    required this.tasks,
    required this.state,
    required this.onComplete,
    required this.onOpenSegment,
    required this.onPractice,
  });

  final List<ReviewTaskModel> tasks;
  final ReviewState state;
  final void Function(int taskId) onComplete;
  final void Function(ReviewTaskModel task) onOpenSegment;
  final void Function(PracticeEntryModel entry) onPractice;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('今日 Top3', style: Theme.of(context).textTheme.titleLarge),
              const Spacer(),
              StatusPill(label: '${tasks.length} 条'),
            ],
          ),
          const SizedBox(height: 16),
          for (var index = 0; index < tasks.length; index++) ...[
            _TaskCard(
              rank: index + 1,
              task: tasks[index],
              completing: state.completingTaskId == tasks[index].reviewTaskId,
              onComplete: () => onComplete(tasks[index].reviewTaskId),
              onOpenSegment: () => onOpenSegment(tasks[index]),
              onPractice: tasks[index].practiceEntry == null
                  ? null
                  : () => onPractice(tasks[index].practiceEntry!),
            ),
            if (index != tasks.length - 1) const SizedBox(height: 14),
          ],
          if (state.completion.hasError) ...[
            const SizedBox(height: 12),
            Text(
              '完成任务失败：${state.completion.error}',
              style: const TextStyle(
                color: Color(0xFFEF4444),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _TaskCard extends StatelessWidget {
  const _TaskCard({
    required this.rank,
    required this.task,
    required this.completing,
    required this.onComplete,
    required this.onOpenSegment,
    required this.onPractice,
  });

  final int rank;
  final ReviewTaskModel task;
  final bool completing;
  final VoidCallback onComplete;
  final VoidCallback onOpenSegment;
  final VoidCallback? onPractice;

  @override
  Widget build(BuildContext context) {
    final segment = task.recommendedSegment;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 10,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              StatusPill(label: '#$rank', color: _priorityColor(rank)),
              StatusPill(label: _taskTypeLabel(task.taskType)),
              StatusPill(label: '优先级 ${task.priorityScore}'),
              if (task.intensity != null)
                StatusPill(
                  label: _intensityLabel(task.intensity!),
                  color: const Color(0xFFF97316),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            task.reasonText.isEmpty ? '建议复习该知识点。' : task.reasonText,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 18,
              height: 1.45,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 12,
            runSpacing: 10,
            children: [
              SourceChip(
                icon: Icons.schedule,
                label: '建议 ${task.recommendedMinutes} 分钟',
              ),
              if (segment != null)
                SourceChip(
                  icon: Icons.play_circle_outline,
                  label: segment.displayText,
                  onTap: onOpenSegment,
                ),
              if (task.practiceEntry != null)
                SourceChip(
                  icon: Icons.quiz_outlined,
                  label: task.practiceEntry!.label ?? '再练',
                  color: const Color(0xFF8B5CF6),
                  onTap: onPractice,
                ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              OutlinedButton.icon(
                onPressed: segment == null ? null : onOpenSegment,
                icon: const Icon(Icons.menu_book_outlined),
                label: const Text('跳回讲义'),
              ),
              OutlinedButton.icon(
                onPressed: onPractice,
                icon: const Icon(Icons.quiz_outlined),
                label: const Text('再练'),
              ),
              FilledButton.icon(
                onPressed: completing ? null : onComplete,
                icon: completing
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check),
                label: Text(completing ? '提交中' : '完成任务'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryPanel extends StatelessWidget {
  const _SummaryPanel({
    required this.tasks,
    required this.state,
  });

  final List<ReviewTaskModel> tasks;
  final ReviewState state;

  @override
  Widget build(BuildContext context) {
    final totalMinutes = tasks.fold<int>(
      0,
      (sum, task) => sum + task.recommendedMinutes,
    );
    final top = tasks.isEmpty ? null : tasks.first;
    return SectionCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('复习概览', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              MetricBox(
                icon: Icons.flag_outlined,
                label: '任务数',
                value: '${tasks.length}',
                detail: '只展示 Top3',
              ),
              MetricBox(
                icon: Icons.timer_outlined,
                label: '建议用时',
                value: '$totalMinutes 分钟',
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (top != null) ...[
            Text('最高优先级', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Text(
              top.reasonText,
              style: const TextStyle(
                color: AppTheme.muted,
                height: 1.55,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (state.completion.valueOrNull?.completed ?? false) ...[
            const SizedBox(height: 14),
            const StatusPill(label: '已记录完成', color: Color(0xFF16A34A)),
          ],
        ],
      ),
    );
  }
}

String _statusLabel(String status) {
  return switch (status) {
    'ready' || 'succeeded' => '已就绪',
    'queued' => '排队中',
    'running' => '生成中',
    'failed' => '失败',
    'skipped' => '已跳过',
    _ => '状态待确认',
  };
}

Color _statusColor(String status) {
  return switch (status) {
    'ready' || 'succeeded' => const Color(0xFF16A34A),
    'failed' => const Color(0xFFEF4444),
    'queued' || 'running' => const Color(0xFFF97316),
    _ => const Color(0xFF64748B),
  };
}

String _taskTypeLabel(String taskType) {
  return switch (taskType) {
    'revisit_block' => '回看讲义',
    'redo_quiz' => '再练测验',
    'formula_drill' => '公式巩固',
    _ => '复习任务',
  };
}

String _intensityLabel(String intensity) {
  return switch (intensity) {
    'high' => '高强度',
    'medium' => '中强度',
    'low' => '轻量',
    _ => '强度待确认',
  };
}

Color _priorityColor(int rank) {
  return switch (rank) {
    1 => const Color(0xFFEF4444),
    2 => const Color(0xFFF97316),
    3 => const Color(0xFF8B5CF6),
    _ => AppTheme.brandBlue,
  };
}
