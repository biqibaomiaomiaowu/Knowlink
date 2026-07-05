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
  String? _loadKey;

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
      title: '复习中心',
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
              onOpenHandout: _openHandout,
              onEnterQuiz: _enterQuiz,
            ),
          ],
        ),
      ),
    );
  }

  void _scheduleLoad() {
    final courseFlow = ref.read(courseFlowProvider);
    final reviewTaskRunId = courseFlow.courseId == widget.courseId
        ? courseFlow.reviewTaskRunId
        : null;
    final loadKey = reviewTaskRunId == null
        ? '${widget.courseId}:load'
        : '${widget.courseId}:run:$reviewTaskRunId';
    if (_loadKey == loadKey) {
      return;
    }
    _loadKey = loadKey;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      if (reviewTaskRunId != null) {
        ref.read(courseFlowProvider.notifier).setReviewTaskRun(null);
        ref.read(reviewProvider.notifier).pollExistingRunAndLoad(
              widget.courseId,
              reviewTaskRunId,
            );
        return;
      }
      ref.read(reviewProvider.notifier).load(widget.courseId);
    });
  }

  void _openHandout(ReviewTaskModel task) {
    final route = task.jumpRoute;
    if (route == null || route.isEmpty) {
      return;
    }

    final blockId = task.linkedHandoutBlockId;
    if (blockId != null) {
      ref.read(activeBlockProvider.notifier).state = blockId;
      ref.read(handoutResumeTargetProvider.notifier).state =
          HandoutResumeTarget(
        courseId: widget.courseId,
        blockId: blockId,
      );
    } else {
      ref.read(activeBlockProvider.notifier).state = null;
      ref.read(handoutResumeTargetProvider.notifier).state = null;
    }
    context.go(route);
  }

  void _enterQuiz(ReviewTaskModel task) {
    final lessonId = task.lessonId ??
        task.practiceEntry?.lessonId ??
        task.sourceLesson?.lessonId;
    if (lessonId == null) {
      return;
    }
    ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
      courseId: widget.courseId,
      lessonId: lessonId.toString(),
    );
    context.go('/courses/${widget.courseId}/lessons/$lessonId/quiz');
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
    final review = state.reviewValue;
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const PageTitle(
            title: '复习中心',
            subtitle: '聚合今日任务、薄弱点、错题和掌握度，安排下一步可追溯复习。',
          ),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              StatusPill(label: '课程编号：$courseId'),
              if (review != null)
                StatusPill(
                  label: '复习 ${_reviewStatusLabel(review.status)}',
                  color: _reviewStatusColor(review.status),
                ),
              if (runStatus != null)
                StatusPill(
                  label:
                      '生成 ${_statusLabel(runStatus.status)} · ${runStatus.generatedCount} 条',
                  color: _statusColor(runStatus.status),
                ),
              OutlinedButton.icon(
                onPressed: state.review.isLoading || state.isCompleting
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
    required this.onOpenHandout,
    required this.onEnterQuiz,
  });

  final String courseId;
  final ReviewState state;
  final VoidCallback onRetry;
  final void Function(int taskId) onComplete;
  final void Function(ReviewTaskModel task) onOpenHandout;
  final void Function(ReviewTaskModel task) onEnterQuiz;

  @override
  Widget build(BuildContext context) {
    if (state.review.isLoading && state.reviewValue == null) {
      return const AppLoadingView(label: '正在加载复习中心...');
    }
    if (state.review.hasError) {
      return AppErrorView(
        message: '复习中心加载失败：${state.review.error}',
        onRetry: onRetry,
      );
    }
    if (state.regeneration.hasError) {
      return AppErrorView(
        message: '复习任务生成失败：${state.regeneration.error}',
        onRetry: onRetry,
      );
    }

    final review = state.reviewValue;
    if (review == null || !_hasReviewContent(review)) {
      return _EmptyReviewCard(courseId: courseId);
    }

    final tasks = _visibleTasks(review);
    final wide = MediaQuery.sizeOf(context).width >= 980;
    final taskList = _TaskList(
      tasks: tasks,
      totalTaskCount: review.todayTaskCount,
      state: state,
      onComplete: onComplete,
      onOpenHandout: onOpenHandout,
      onEnterQuiz: onEnterQuiz,
    );
    final summary = _SummaryPanel(review: review, tasks: tasks);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _OverviewGrid(review: review),
        const SizedBox(height: 16),
        if (wide)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(flex: 3, child: taskList),
              const SizedBox(width: 16),
              Expanded(flex: 2, child: summary),
            ],
          )
        else
          Column(
            children: [
              taskList,
              const SizedBox(height: 16),
              summary,
            ],
          ),
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
            '课程 $courseId 还没有可展示的复习任务。完成测验后可生成复习中心数据。',
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

class _OverviewGrid extends StatelessWidget {
  const _OverviewGrid({
    required this.review,
  });

  final CourseReviewModel review;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        SizedBox(
          width: 260,
          child: MetricBox(
            icon: Icons.task_alt_outlined,
            label: '今日任务',
            value: '${review.todayTaskCount}',
            detail: '待处理复习项',
            color: AppTheme.brandBlue,
          ),
        ),
        SizedBox(
          width: 260,
          child: MetricBox(
            icon: Icons.trending_down,
            label: '薄弱点',
            value: '${review.weakPointCount}',
            detail: '跨课时弱点',
            color: const Color(0xFFF97316),
          ),
        ),
        SizedBox(
          width: 260,
          child: MetricBox(
            icon: Icons.error_outline,
            label: '错题',
            value: '${review.mistakeCount}',
            detail: '需回看的题目线索',
            color: const Color(0xFFEF4444),
          ),
        ),
        SizedBox(
          width: 260,
          child: MetricBox(
            icon: Icons.speed_outlined,
            label: '掌握度',
            value: _formatMastery(review.masteryScore),
            detail: '当前课程掌握估计',
            color: const Color(0xFF16A34A),
          ),
        ),
      ],
    );
  }
}

class _TaskList extends StatelessWidget {
  const _TaskList({
    required this.tasks,
    required this.totalTaskCount,
    required this.state,
    required this.onComplete,
    required this.onOpenHandout,
    required this.onEnterQuiz,
  });

  final List<ReviewTaskModel> tasks;
  final int totalTaskCount;
  final ReviewState state;
  final void Function(int taskId) onComplete;
  final void Function(ReviewTaskModel task) onOpenHandout;
  final void Function(ReviewTaskModel task) onEnterQuiz;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('今日任务', style: Theme.of(context).textTheme.titleLarge),
              const Spacer(),
              StatusPill(label: '${tasks.length}/$totalTaskCount 条'),
            ],
          ),
          const SizedBox(height: 16),
          for (var index = 0; index < tasks.length; index++) ...[
            _TaskCard(
              rank: index + 1,
              task: tasks[index],
              completing: state.completingTaskId == tasks[index].reviewTaskId,
              onComplete: () => onComplete(tasks[index].reviewTaskId),
              onOpenHandout: () => onOpenHandout(tasks[index]),
              onEnterQuiz: () => onEnterQuiz(tasks[index]),
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
          if (state.completion.valueOrNull?.completed ?? false) ...[
            const SizedBox(height: 12),
            const StatusPill(label: '已记录完成', color: Color(0xFF16A34A)),
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
    required this.onOpenHandout,
    required this.onEnterQuiz,
  });

  final int rank;
  final ReviewTaskModel task;
  final bool completing;
  final VoidCallback onComplete;
  final VoidCallback onOpenHandout;
  final VoidCallback onEnterQuiz;

  @override
  Widget build(BuildContext context) {
    final lessonTitle = task.sourceLesson?.title;
    final blockTitle = task.recommendedHandoutBlock?.title;
    final canOpenHandout = task.jumpRoute != null && task.jumpRoute!.isNotEmpty;
    final canEnterQuiz = _lessonIdForQuiz(task) != null;
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
              if (!task.completionSupported)
                const StatusPill(
                  label: '无需手动完成',
                  color: Color(0xFF64748B),
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
              if (lessonTitle != null && lessonTitle.isNotEmpty)
                SourceChip(
                  icon: Icons.video_library_outlined,
                  label: lessonTitle,
                  color: const Color(0xFF0F766E),
                ),
              if (blockTitle != null && blockTitle.isNotEmpty)
                SourceChip(
                  icon: Icons.menu_book_outlined,
                  label: blockTitle,
                  onTap: canOpenHandout ? onOpenHandout : null,
                ),
              if (task.sourceQuestionKeys.isNotEmpty)
                SourceChip(
                  icon: Icons.fact_check_outlined,
                  label: '错题 ${task.sourceQuestionKeys.take(2).join('、')}',
                  color: const Color(0xFFEF4444),
                ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              OutlinedButton.icon(
                onPressed: canOpenHandout ? onOpenHandout : null,
                icon: const Icon(Icons.menu_book_outlined),
                label: const Text('回到讲义'),
              ),
              OutlinedButton.icon(
                onPressed: canEnterQuiz ? onEnterQuiz : null,
                icon: const Icon(Icons.quiz_outlined),
                label: const Text('进入测试'),
              ),
              FilledButton.icon(
                onPressed:
                    completing || !task.completionSupported ? null : onComplete,
                icon: completing
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.check),
                label: Text(completing ? '提交中' : '标记完成'),
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
    required this.review,
    required this.tasks,
  });

  final CourseReviewModel review;
  final List<ReviewTaskModel> tasks;

  @override
  Widget build(BuildContext context) {
    final totalMinutes = tasks.fold<int>(
      0,
      (sum, task) => sum + task.recommendedMinutes,
    );
    return SectionCard(
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('复习摘要', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          _SummaryBlock(
            title: '任务摘要',
            body: review.todayTaskCount == 0
                ? '今天暂无待处理任务。'
                : '今天共有 ${review.todayTaskCount} 个复习任务，当前展示 ${tasks.length} 个优先项，建议投入 $totalMinutes 分钟。',
          ),
          const SizedBox(height: 12),
          _SummaryBlock(
            title: '薄弱摘要',
            body: _weakSummary(review),
          ),
          const SizedBox(height: 12),
          _SummaryBlock(
            title: '错题摘要',
            body: _mistakeSummary(review, tasks),
          ),
          const SizedBox(height: 12),
          _SummaryBlock(
            title: '掌握摘要',
            body: _masterySummary(review),
          ),
        ],
      ),
    );
  }
}

class _SummaryBlock extends StatelessWidget {
  const _SummaryBlock({
    required this.title,
    required this.body,
  });

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.panel,
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          Text(
            body,
            style: const TextStyle(
              color: AppTheme.muted,
              height: 1.5,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

bool _hasReviewContent(CourseReviewModel review) {
  return review.todayTaskCount > 0 ||
      review.weakPointCount > 0 ||
      review.mistakeCount > 0 ||
      review.masteryScore != null ||
      review.items.isNotEmpty ||
      review.topTasks.isNotEmpty ||
      review.weakLessons.isNotEmpty ||
      review.crossLessonWeakPoints.isNotEmpty;
}

List<ReviewTaskModel> _visibleTasks(CourseReviewModel review) {
  if (review.topTasks.isNotEmpty) {
    return review.topTasks;
  }
  return review.items;
}

int? _lessonIdForQuiz(ReviewTaskModel task) {
  return task.lessonId ??
      task.practiceEntry?.lessonId ??
      task.sourceLesson?.lessonId;
}

String _weakSummary(CourseReviewModel review) {
  final lessonTitles = review.weakLessons
      .map((lesson) => lesson.title)
      .whereType<String>()
      .where((title) => title.isNotEmpty);
  final weakPointTitles = review.crossLessonWeakPoints
      .map((point) => point.title)
      .whereType<String>()
      .where((title) => title.isNotEmpty);
  final highlights = [...lessonTitles, ...weakPointTitles].take(3).toList();
  if (highlights.isEmpty) {
    return review.weakPointCount == 0
        ? '暂未识别跨课时薄弱点。'
        : '已识别 ${review.weakPointCount} 个薄弱点，优先按今日任务处理。';
  }
  return '已识别 ${review.weakPointCount} 个薄弱点：${highlights.join('、')}。';
}

String _mistakeSummary(
  CourseReviewModel review,
  List<ReviewTaskModel> tasks,
) {
  final questionKeys = tasks
      .expand((task) => task.sourceQuestionKeys)
      .where((key) => key.isNotEmpty)
      .take(4)
      .toList();
  if (questionKeys.isEmpty) {
    return review.mistakeCount == 0
        ? '暂无错题线索。'
        : '累计 ${review.mistakeCount} 道错题线索，建议先回看关联讲义后进入测试。';
  }
  return '累计 ${review.mistakeCount} 道错题线索，优先关注 ${questionKeys.join('、')}。';
}

String _masterySummary(CourseReviewModel review) {
  final mastery = _formatMastery(review.masteryScore);
  final weakestLesson = review.weakLessons
      .where((lesson) => lesson.masteryScore != null)
      .toList()
    ..sort((a, b) => a.masteryScore!.compareTo(b.masteryScore!));
  if (weakestLesson.isEmpty) {
    return '当前课程掌握度 $mastery，继续通过任务完成情况校准。';
  }
  final lesson = weakestLesson.first;
  final title = lesson.title == null || lesson.title!.isEmpty
      ? '课时 ${lesson.lessonId}'
      : lesson.title!;
  return '当前课程掌握度 $mastery，最低掌握课时为 $title（${_formatMastery(lesson.masteryScore)}）。';
}

String _formatMastery(double? score) {
  if (score == null) {
    return '--';
  }
  final normalized = score <= 1 ? score * 100 : score;
  return '${normalized.round()}%';
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

String _reviewStatusLabel(String status) {
  return switch (status) {
    'ready' || 'succeeded' => '已就绪',
    'empty' || 'placeholder' => '待生成',
    'running' => '生成中',
    'failed' => '失败',
    _ => status,
  };
}

Color _reviewStatusColor(String status) {
  return switch (status) {
    'ready' || 'succeeded' => const Color(0xFF16A34A),
    'failed' => const Color(0xFFEF4444),
    'running' => const Color(0xFFF97316),
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
