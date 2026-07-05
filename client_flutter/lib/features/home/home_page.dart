import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_progress_models.dart';
import '../../shared/models/course_summary.dart';
import '../../shared/models/home_dashboard_models.dart';
import '../../shared/models/home_state.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/home_provider.dart';

class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  var _loaded = false;

  @override
  void initState() {
    super.initState();
    _scheduleLoad();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(homeProvider);
    return AppScaffold(
      title: 'KnowLink',
      activeTab: KnowLinkTab.home,
      body: _HomeBody(
        state: state,
        onRetry: () => ref.read(homeProvider.notifier).loadDashboard(),
        onContinueLearning: _continueLearning,
        onResumeCourse: _resumeCourse,
        onSwitchCourse: _switchCourse,
        onOpenRoute: _openRoute,
      ),
    );
  }

  void _scheduleLoad() {
    if (_loaded) {
      return;
    }
    _loaded = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(homeProvider.notifier).loadDashboard();
    });
  }

  Future<void> _continueLearning(HomeDashboardModel dashboard) async {
    final currentCourse = dashboard.currentCourse;
    final currentLesson = dashboard.currentLesson;
    final target = dashboard.continueLearning ?? dashboard.nextStep;
    final courseId = target?.courseId ?? currentCourse?.courseId;
    final lessonId = target?.lessonId ?? currentLesson?.lessonId;
    if (courseId == null) {
      return;
    }

    ref.read(courseFlowProvider.notifier).startCourse(courseId.toString());
    ref.read(activeBlockProvider.notifier).state =
        target?.lastHandoutBlockId ?? currentLesson?.lastHandoutBlockId;
    ref.read(handoutResumeTargetProvider.notifier).state =
        _handoutResumeTarget(courseId, target, currentLesson);
    ref.read(playerStateProvider.notifier).state = PlayerState(
      positionSec: target?.lastPositionSec ??
          currentLesson?.lastPositionSec ??
          currentCourse?.lastPositionSec ??
          0,
    );

    if (lessonId != null && lessonId.isNotEmpty) {
      ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
        courseId: courseId.toString(),
        lessonId: lessonId,
        positionSec: target?.lastPositionSec ??
            currentLesson?.lastPositionSec ??
            currentCourse?.lastPositionSec ??
            0,
      );
      if (!mounted) {
        return;
      }
      context.go(
        target?.nextRoute ?? '/courses/$courseId/lessons/$lessonId/handout',
      );
      return;
    }

    if (!mounted) {
      return;
    }
    context.go('/courses/$courseId/handout');
  }

  Future<void> _resumeCourse(CourseSummaryModel course) async {
    final notifier = ref.read(homeProvider.notifier);
    final cached =
        ref.read(homeProvider).progressByCourseId[course.courseId]?.valueOrNull;
    final progress = cached ?? await notifier.fetchProgress(course.courseId);
    if (!mounted) {
      return;
    }
    ref
        .read(courseFlowProvider.notifier)
        .startCourse(course.courseId.toString());
    final blockId = progress?.lastHandoutBlockId;
    ref.read(activeBlockProvider.notifier).state = blockId;
    ref.read(handoutResumeTargetProvider.notifier).state = blockId == null
        ? null
        : HandoutResumeTarget(
            courseId: course.courseId.toString(),
            blockId: blockId,
          );
    final positionSec = progress?.lastPositionSec ?? course.lastPositionSec ?? 0;
    ref.read(playerStateProvider.notifier).state = PlayerState(
      positionSec: positionSec,
    );
    final lessonId = progress?.currentLessonId ?? course.currentLessonId;
    if (lessonId != null && lessonId.isNotEmpty) {
      ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
        courseId: course.courseId.toString(),
        lessonId: lessonId,
        positionSec: positionSec,
      );
      context.go('/courses/${course.courseId}/lessons/$lessonId/handout');
      return;
    }
    context.go('/courses/${course.courseId}/handout');
  }

  Future<void> _switchCourse(CourseSummaryModel course) async {
    final switched = await ref
        .read(homeProvider.notifier)
        .switchCurrentCourse(course.courseId);
    if (!mounted || switched == null) {
      if (mounted && ref.read(homeProvider).currentCourseSwitch.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('切换当前课程失败')),
        );
      }
      return;
    }
    ref
        .read(courseFlowProvider.notifier)
        .startCourse(switched.courseId.toString());
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('当前课程已切换')),
    );
  }

  void _openRoute(String? route) {
    if (route == null || route.isEmpty) {
      return;
    }
    context.go(route);
  }
}

class _HomeBody extends StatelessWidget {
  const _HomeBody({
    required this.state,
    required this.onRetry,
    required this.onContinueLearning,
    required this.onResumeCourse,
    required this.onSwitchCourse,
    required this.onOpenRoute,
  });

  final HomeState state;
  final VoidCallback onRetry;
  final Future<void> Function(HomeDashboardModel dashboard) onContinueLearning;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    if (state.dashboard.isLoading && state.dashboardValue == null) {
      return const AppLoadingView(label: '正在加载首页...');
    }
    if (state.dashboard.hasError) {
      return AppErrorView(
        message: '首页加载失败：${state.dashboard.error}',
        onRetry: onRetry,
      );
    }

    final dashboard = state.dashboardValue;
    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= 920;
        final content = isWide
            ? _HomeWideLayout(
                dashboard: dashboard,
                progressByCourseId: state.progressByCourseId,
                isSwitchingCourse: state.currentCourseSwitch.isLoading,
                onContinueLearning: onContinueLearning,
                onResumeCourse: onResumeCourse,
                onSwitchCourse: onSwitchCourse,
                onOpenRoute: onOpenRoute,
              )
            : _HomeNarrowLayout(
                dashboard: dashboard,
                progressByCourseId: state.progressByCourseId,
                isSwitchingCourse: state.currentCourseSwitch.isLoading,
                onContinueLearning: onContinueLearning,
                onResumeCourse: onResumeCourse,
                onSwitchCourse: onSwitchCourse,
                onOpenRoute: onOpenRoute,
              );
        return RefreshIndicator(
          onRefresh: () async => onRetry(),
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: content,
          ),
        );
      },
    );
  }
}

class _HomeWideLayout extends StatelessWidget {
  const _HomeWideLayout({
    required this.dashboard,
    required this.progressByCourseId,
    required this.isSwitchingCourse,
    required this.onContinueLearning,
    required this.onResumeCourse,
    required this.onSwitchCourse,
    required this.onOpenRoute,
  });

  final HomeDashboardModel? dashboard;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final Future<void> Function(HomeDashboardModel dashboard) onContinueLearning;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _CurrentLearningCard(
          dashboard: dashboard,
          onContinueLearning: onContinueLearning,
          onOpenRoute: onOpenRoute,
        ),
        const SizedBox(height: 24),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: _StatsCard(dashboard: dashboard)),
            const SizedBox(width: 24),
            Expanded(
              child: _NextStepCard(
                dashboard: dashboard,
                onOpenRoute: onOpenRoute,
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _TodayReviewCard(
                tasks: dashboard?.todayReviewTasks ?? const [],
                onOpenRoute: onOpenRoute,
              ),
            ),
            const SizedBox(width: 24),
            Expanded(
              child: _RecentCoursesCard(
                recentCourses: dashboard?.recentCourses ?? const [],
                progressByCourseId: progressByCourseId,
                isSwitchingCourse: isSwitchingCourse,
                onResumeCourse: onResumeCourse,
                onSwitchCourse: onSwitchCourse,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _HomeNarrowLayout extends StatelessWidget {
  const _HomeNarrowLayout({
    required this.dashboard,
    required this.progressByCourseId,
    required this.isSwitchingCourse,
    required this.onContinueLearning,
    required this.onResumeCourse,
    required this.onSwitchCourse,
    required this.onOpenRoute,
  });

  final HomeDashboardModel? dashboard;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final Future<void> Function(HomeDashboardModel dashboard) onContinueLearning;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _CurrentLearningCard(
          dashboard: dashboard,
          onContinueLearning: onContinueLearning,
          onOpenRoute: onOpenRoute,
        ),
        const SizedBox(height: 16),
        _StatsCard(dashboard: dashboard),
        const SizedBox(height: 16),
        _NextStepCard(
          dashboard: dashboard,
          onOpenRoute: onOpenRoute,
        ),
        const SizedBox(height: 16),
        _TodayReviewCard(
          tasks: dashboard?.todayReviewTasks ?? const [],
          onOpenRoute: onOpenRoute,
        ),
        const SizedBox(height: 16),
        _RecentCoursesCard(
          recentCourses: dashboard?.recentCourses ?? const [],
          progressByCourseId: progressByCourseId,
          isSwitchingCourse: isSwitchingCourse,
          onResumeCourse: onResumeCourse,
          onSwitchCourse: onSwitchCourse,
        ),
      ],
    );
  }
}

class _CurrentLearningCard extends StatelessWidget {
  const _CurrentLearningCard({
    required this.dashboard,
    required this.onContinueLearning,
    required this.onOpenRoute,
  });

  final HomeDashboardModel? dashboard;
  final Future<void> Function(HomeDashboardModel dashboard) onContinueLearning;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    final value = dashboard;
    final course = value?.currentCourse;
    final lesson = value?.currentLesson;
    final target = value?.continueLearning ?? value?.nextStep;
    final canContinue = value != null && course != null && target != null;

    return SectionCard(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '今天继续什么'),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 680;
              final summary = [
                _SummaryTile(
                  label: '当前课程',
                  value: course?.title ?? '还没有当前课程',
                  icon: Icons.school_outlined,
                  color: AppTheme.brandBlue,
                ),
                _SummaryTile(
                  label: '当前课时',
                  value: lesson?.title ?? '还没有当前课时',
                  icon: Icons.play_lesson_outlined,
                  color: const Color(0xFF16A34A),
                ),
                _SummaryTile(
                  label: '学习位置',
                  value: _continueMeta(target, lesson),
                  icon: Icons.place_outlined,
                  color: const Color(0xFFF97316),
                ),
              ];
              if (compact) {
                return Column(
                  children: [
                    for (final item in summary) ...[
                      item,
                      if (item != summary.last) const SizedBox(height: 12),
                    ],
                  ],
                );
              }
              return Row(
                children: [
                  for (final item in summary) ...[
                    Expanded(child: item),
                    if (item != summary.last) const SizedBox(width: 12),
                  ],
                ],
              );
            },
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 12,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              FilledButton.icon(
                onPressed: canContinue ? () => onContinueLearning(value) : null,
                icon: const Icon(Icons.play_arrow_rounded),
                label: const Text('继续学习'),
              ),
              if (target?.nextAction?.label != null)
                StatusPill(
                  label: target!.nextAction!.label!,
                  color: const Color(0xFF16A34A),
                ),
              if (value?.courseQuickEntries.isNotEmpty ?? false)
                for (final entry in value!.courseQuickEntries
                    .where((item) => item.enabled)
                    .take(3))
                  ActionChip(
                    avatar: const Icon(Icons.open_in_new_rounded, size: 18),
                    label: Text(entry.title),
                    onPressed: () => onOpenRoute(entry.route ?? entry.target),
                    side: const BorderSide(color: AppTheme.line),
                  ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StatsCard extends StatelessWidget {
  const _StatsCard({
    required this.dashboard,
  });

  final HomeDashboardModel? dashboard;

  @override
  Widget build(BuildContext context) {
    final stats = dashboard?.learningStats ??
        const LearningStatsModel(
          streakDays: 0,
          completedCourses: 0,
          reviewTasksCompleted: 0,
          totalLearningMinutes: 0,
        );
    final lesson = dashboard?.currentLesson;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '进度摘要'),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              MetricBox(
                icon: Icons.percent_rounded,
                label: '当前课时讲义',
                value: lesson?.handoutReadPercent == null
                    ? '0%'
                    : '${lesson!.handoutReadPercent}%',
              ),
              MetricBox(
                icon: Icons.schedule_rounded,
                label: '累计学习',
                value: '${stats.totalLearningMinutes} 分钟',
              ),
              MetricBox(
                icon: Icons.local_fire_department_outlined,
                label: '连续学习',
                value: '${stats.streakDays} 天',
                color: const Color(0xFFF97316),
              ),
              MetricBox(
                icon: Icons.check_circle_outline,
                label: '完成复习',
                value: '${stats.reviewTasksCompleted}',
                color: const Color(0xFF16A34A),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _NextStepCard extends StatelessWidget {
  const _NextStepCard({
    required this.dashboard,
    required this.onOpenRoute,
  });

  final HomeDashboardModel? dashboard;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    final items = [
      dashboard?.nextStep,
      dashboard?.recommendedNextLesson,
      dashboard?.recommendedStageQuiz,
    ].whereType<HomeRouteTargetModel>().toList();

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '推荐下一步'),
          const SizedBox(height: 12),
          if (items.isEmpty)
            const _EmptyText('暂无推荐下一步')
          else
            for (final item in items.take(3)) ...[
              _RouteTargetRow(
                target: item,
                fallbackTitle: _targetFallbackTitle(item),
                onOpenRoute: onOpenRoute,
              ),
              if (item != items.take(3).last) const Divider(height: 20),
            ],
        ],
      ),
    );
  }
}

class _TodayReviewCard extends StatelessWidget {
  const _TodayReviewCard({
    required this.tasks,
    required this.onOpenRoute,
  });

  final List<HomeReviewTaskModel> tasks;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    final visibleTasks = tasks.take(3).toList();
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '今日复习任务'),
          const SizedBox(height: 12),
          if (visibleTasks.isEmpty)
            const _EmptyText('今天没有到期复习任务')
          else
            for (final task in visibleTasks) ...[
              _ReviewTaskRow(
                task: task,
                onOpenRoute: onOpenRoute,
              ),
              if (task != visibleTasks.last) const Divider(height: 20),
            ],
        ],
      ),
    );
  }
}

class _RecentCoursesCard extends StatelessWidget {
  const _RecentCoursesCard({
    required this.recentCourses,
    required this.progressByCourseId,
    required this.isSwitchingCourse,
    required this.onResumeCourse,
    required this.onSwitchCourse,
  });

  final List<CourseSummaryModel> recentCourses;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;

  @override
  Widget build(BuildContext context) {
    final visibleCourses = recentCourses.take(3).toList();
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '最近课程'),
          const SizedBox(height: 18),
          if (visibleCourses.isEmpty)
            const _EmptyText('暂无最近课程')
          else
            for (final course in visibleCourses) ...[
              _RecentCourseDetails(
                course: course,
                progress: progressByCourseId[course.courseId]?.valueOrNull,
                progressState: progressByCourseId[course.courseId],
                isSwitching: isSwitchingCourse,
                onResume: () => onResumeCourse(course),
                onSwitch: () => onSwitchCourse(course),
              ),
              if (course != visibleCourses.last) const Divider(height: 28),
            ],
        ],
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  const _SummaryTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.panel,
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          SoftIcon(icon: icon, color: color, size: 48),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 6),
                Text(
                  value,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RouteTargetRow extends StatelessWidget {
  const _RouteTargetRow({
    required this.target,
    required this.fallbackTitle,
    required this.onOpenRoute,
  });

  final HomeRouteTargetModel target;
  final String fallbackTitle;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SoftIcon(
            icon: _targetIcon(target),
            color: _targetColor(target),
            size: 48,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  target.title ?? fallbackTitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (target.reason != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    target.reason!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.muted,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
          IconButton(
            tooltip: '打开',
            onPressed: target.nextRoute == null
                ? null
                : () => onOpenRoute(target.nextRoute),
            icon: const Icon(Icons.chevron_right_rounded),
          ),
        ],
      ),
    );
  }
}

class _ReviewTaskRow extends StatelessWidget {
  const _ReviewTaskRow({
    required this.task,
    required this.onOpenRoute,
  });

  final HomeReviewTaskModel task;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          StatusPill(
            label: '${task.priorityScore}',
            color: const Color(0xFFF97316),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  task.title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  task.reasonText,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed:
                task.nextRoute == null ? null : () => onOpenRoute(task.nextRoute),
            child: const Text('复习'),
          ),
        ],
      ),
    );
  }
}

class _RecentCourseDetails extends StatelessWidget {
  const _RecentCourseDetails({
    required this.course,
    required this.progress,
    required this.progressState,
    required this.isSwitching,
    required this.onResume,
    required this.onSwitch,
  });

  final CourseSummaryModel course;
  final CourseProgressModel? progress;
  final AsyncValue<CourseProgressModel>? progressState;
  final bool isSwitching;
  final VoidCallback onResume;
  final VoidCallback onSwitch;

  @override
  Widget build(BuildContext context) {
    final resumeText = _resumeText(progress, course);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          course.title,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: AppTheme.ink,
            fontSize: 20,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 10,
          runSpacing: 8,
          children: [
            StatusPill(label: _pipelineLabel(course.pipelineStatus)),
            StatusPill(
              label: _lifecycleLabel(course.lifecycleStatus),
              color: const Color(0xFF64748B),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (progressState?.isLoading ?? false)
          const Text(
            '正在读取最近学习位置...',
            style:
                TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w600),
          )
        else
          Text(
            resumeText,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
              height: 1.5,
            ),
          ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            OutlinedButton.icon(
              onPressed: onResume,
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('继续'),
            ),
            OutlinedButton.icon(
              onPressed: isSwitching ? null : onSwitch,
              icon: const Icon(Icons.check_circle_outline),
              label: Text(isSwitching ? '正在切换' : '设为当前'),
            ),
            OutlinedButton.icon(
              onPressed: () => context.go('/courses/${course.courseId}'),
              icon: const Icon(Icons.info_outline),
              label: const Text('课程详情'),
            ),
          ],
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
  });

  final String title;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: AppTheme.ink,
        fontSize: 22,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

class _EmptyText extends StatelessWidget {
  const _EmptyText(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        color: AppTheme.muted,
        fontWeight: FontWeight.w700,
        height: 1.45,
      ),
    );
  }
}

HandoutResumeTarget? _handoutResumeTarget(
  int courseId,
  HomeRouteTargetModel? target,
  HomeLessonModel? lesson,
) {
  final blockId = target?.lastHandoutBlockId ?? lesson?.lastHandoutBlockId;
  if (blockId == null) {
    return null;
  }
  return HandoutResumeTarget(
    courseId: courseId.toString(),
    blockId: blockId,
  );
}

String _continueMeta(
  HomeRouteTargetModel? target,
  HomeLessonModel? lesson,
) {
  final parts = <String>[];
  final positionSec = target?.lastPositionSec ?? lesson?.lastPositionSec;
  final blockId = target?.lastHandoutBlockId ?? lesson?.lastHandoutBlockId;
  if (blockId != null) {
    parts.add('讲义块 $blockId');
  }
  if (positionSec != null && positionSec > 0) {
    parts.add('视频 ${_formatSec(positionSec)}');
  }
  if (parts.isEmpty) {
    return '准备开始';
  }
  return parts.join(' · ');
}

String _resumeText(CourseProgressModel? progress, CourseSummaryModel course) {
  final lessonTitle = progress?.currentLessonTitle ?? course.currentLessonTitle;
  if (progress == null || !progress.hasResumeTarget) {
    if (lessonTitle != null && lessonTitle.isNotEmpty) {
      return '上次学习：$lessonTitle';
    }
    return '还没有最近学习位置';
  }
  final parts = <String>[];
  if (lessonTitle != null && lessonTitle.isNotEmpty) {
    parts.add(lessonTitle);
  }
  if (progress.lastHandoutBlockId != null) {
    parts.add('讲义块 ${progress.lastHandoutBlockId}');
  }
  if (progress.lastPositionSec != null) {
    parts.add('视频 ${_formatSec(progress.lastPositionSec!)}');
  }
  if (progress.lastPageNo != null) {
    parts.add('文档第 ${progress.lastPageNo} 页');
  }
  if (progress.lastSlideNo != null) {
    parts.add('PPT 第 ${progress.lastSlideNo} 页');
  }
  if (progress.lastAnchorKey != null && progress.lastAnchorKey!.isNotEmpty) {
    parts.add(progress.lastAnchorKey!);
  }
  return '上次学习：${parts.join(' · ')}';
}

String _pipelineLabel(String status) {
  return switch (status) {
    'succeeded' => '已完成',
    'running' => '进行中',
    'queued' => '排队中',
    'failed' => '失败',
    'partial_success' => '部分完成',
    _ => '状态待确认',
  };
}

String _lifecycleLabel(String status) {
  return switch (status) {
    'draft' => '草稿',
    'resource_ready' => '资料就绪',
    'inquiry_ready' => '问询就绪',
    'learning_ready' => '学习就绪',
    'archived' => '已归档',
    'failed' => '失败',
    _ => '状态待确认',
  };
}

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}

String _targetFallbackTitle(HomeRouteTargetModel target) {
  return switch (target.type) {
    'stage_quiz' => '生成阶段测验',
    'next_lesson' => '继续下一课时',
    'continue_lesson' => '继续当前课时',
    _ => '打开下一步',
  };
}

IconData _targetIcon(HomeRouteTargetModel target) {
  return switch (target.type) {
    'stage_quiz' => Icons.quiz_outlined,
    'next_lesson' => Icons.next_plan_outlined,
    'continue_lesson' => Icons.play_lesson_outlined,
    _ => Icons.arrow_forward_rounded,
  };
}

Color _targetColor(HomeRouteTargetModel target) {
  return switch (target.type) {
    'stage_quiz' => const Color(0xFF8B5CF6),
    'next_lesson' => const Color(0xFF16A34A),
    'continue_lesson' => AppTheme.brandBlue,
    _ => const Color(0xFF64748B),
  };
}
