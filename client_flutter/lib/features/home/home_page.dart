import 'dart:async';

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
import '../course_import/course_create_dialog.dart';

const _newCourseModalRoute = '__new_course_modal__';

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
    final positionSec =
        progress?.lastPositionSec ?? course.lastPositionSec ?? 0;
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
    if (route == _newCourseModalRoute) {
      unawaited(_openCourseCreateDialog());
      return;
    }
    context.go(route);
  }

  Future<void> _openCourseCreateDialog() async {
    final course = await showCourseCreateDialog(context);
    if (!mounted || course == null) {
      return;
    }
    context.go('/courses/${course.courseId}');
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
                availableHeight: constraints.maxHeight,
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
        if (isWide) {
          return SizedBox(
            height: constraints.maxHeight,
            child: content,
          );
        }
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

class _HomePrototypeTitle extends StatelessWidget {
  const _HomePrototypeTitle({
    required this.onOpenRoute,
    this.dense = false,
  });

  final void Function(String? route) onOpenRoute;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 640;
        final title = Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SoftIcon(icon: Icons.home_outlined, size: dense ? 42 : 46),
            const SizedBox(width: 14),
            Expanded(
              child: _HomePrototypeTitleText(dense: dense),
            ),
          ],
        );
        final actions = Wrap(
          spacing: 10,
          runSpacing: 10,
          alignment: compact ? WrapAlignment.start : WrapAlignment.end,
          children: [
            OutlinedButton(
              onPressed: () => onOpenRoute('/courses'),
              child: const Text('查看课程库'),
            ),
            FilledButton(
              onPressed: () => onOpenRoute(_newCourseModalRoute),
              child: const Text('新建课程'),
            ),
          ],
        );

        if (compact) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              title,
              const SizedBox(height: 14),
              actions,
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: title),
            const SizedBox(width: 16),
            actions,
          ],
        );
      },
    );
  }
}

class _HomePrototypeTitleText extends StatelessWidget {
  const _HomePrototypeTitleText({required this.dense});

  final bool dense;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'KnowLink / Study Center',
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: 12,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.1,
          ),
        ),
        const SizedBox(height: 4),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '学习总览',
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: dense ? 38 : 42,
                  fontWeight: FontWeight.w800,
                  height: 1.02,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _HomeHeroDashboard extends StatelessWidget {
  const _HomeHeroDashboard({
    required this.dashboard,
    required this.onContinueLearning,
    this.dense = false,
  });

  final HomeDashboardModel? dashboard;
  final Future<void> Function(HomeDashboardModel dashboard) onContinueLearning;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final value = dashboard;
    final course = value?.currentCourse;
    final lesson = value?.currentLesson;
    final percent = ((lesson?.handoutReadPercent ?? 0).clamp(0, 100)) / 100;
    final canContinue = value != null &&
        course != null &&
        (value.continueLearning != null || value.nextStep != null);
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 760;
        final heroHeight = dense ? 188.0 : 250.0;
        final heroPadding = dense ? 20.0 : 28.0;
        final heroContent = Stack(
          clipBehavior: Clip.none,
          children: [
            const Positioned(
              right: -52,
              top: -72,
              child: _HeroSoftOrb(size: 220, inset: true),
            ),
            const Positioned(
              right: 128,
              bottom: -70,
              child: _HeroSoftOrb(size: 150, inset: false),
            ),
            Padding(
              padding: EdgeInsets.all(heroPadding),
              child: compact
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _HeroCopy(
                          course: course,
                          lesson: lesson,
                          canContinue: canContinue,
                          dense: dense,
                          onContinue: value == null
                              ? null
                              : () => onContinueLearning(value),
                        ),
                        const SizedBox(height: 14),
                        _HeroProgressCard(
                          percent: percent,
                          completed: lesson?.orderIndex ?? 0,
                          dense: dense,
                        ),
                      ],
                    )
                  : Row(
                      children: [
                        Expanded(
                          flex: 6,
                          child: _HeroCopy(
                            course: course,
                            lesson: lesson,
                            canContinue: canContinue,
                            dense: dense,
                            onContinue: value == null
                                ? null
                                : () => onContinueLearning(value),
                          ),
                        ),
                        const SizedBox(width: 20),
                        Expanded(
                          flex: 4,
                          child: _HeroProgressCard(
                            percent: percent,
                            completed: lesson?.orderIndex ?? 0,
                            dense: dense,
                          ),
                        ),
                      ],
                    ),
            ),
          ],
        );
        final card = DecoratedBox(
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(32),
            boxShadow: AppTheme.shadowRaised,
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(32),
            child: ColoredBox(
              color: AppTheme.surface,
              child: heroContent,
            ),
          ),
        );
        return compact ? card : SizedBox(height: heroHeight, child: card);
      },
    );
  }
}

class _HeroCopy extends StatelessWidget {
  const _HeroCopy({
    required this.course,
    required this.lesson,
    required this.canContinue,
    required this.dense,
    required this.onContinue,
  });

  final CourseSummaryModel? course;
  final HomeLessonModel? lesson;
  final bool canContinue;
  final bool dense;
  final VoidCallback? onContinue;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const _PrototypePill(label: '今日学习计划'),
        SizedBox(height: dense ? 8 : 14),
        Text(
          lesson == null
              ? '准备开始你的第一节课'
              : '继续学习「${course?.title ?? '当前课程'}」：${lesson!.title}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: AppTheme.ink,
            fontSize: dense ? 24 : 34,
            fontWeight: FontWeight.w800,
            height: 1.08,
          ),
        ),
        SizedBox(height: dense ? 4 : 12),
        Text(
          lesson == null
              ? '系统会根据你的课程、资料和薄弱点组织讲义、测试与复习。'
              : '系统已根据上次进度、薄弱点和当前课时安排讲义学习、测试和错题复盘。',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: AppTheme.muted,
            fontSize: dense ? 14 : 15,
            fontWeight: FontWeight.w500,
            height: dense ? 1.45 : 1.7,
          ),
        ),
        SizedBox(height: dense ? 8 : 22),
        FilledButton(
          onPressed: canContinue ? onContinue : null,
          child: const Text('进入当前课时'),
        ),
      ],
    );
  }
}

class _HeroSoftOrb extends StatelessWidget {
  const _HeroSoftOrb({
    required this.size,
    required this.inset,
  });

  final double size;
  final bool inset;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(size / 2),
        boxShadow: inset ? AppTheme.shadowInsetLook : AppTheme.shadowSmall,
      ),
    );
  }
}

class _PrototypePill extends StatelessWidget {
  const _PrototypePill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    const color = AppTheme.brandBlue;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 260),
      child: Container(
        constraints: const BoxConstraints(minHeight: 30),
        padding: const EdgeInsets.symmetric(horizontal: 13),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(999),
          boxShadow: AppTheme.shadowInsetLook,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(999),
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.14),
                    blurRadius: 0,
                    spreadRadius: 5,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppTheme.ink,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  height: 1.2,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PrototypeProgressRail extends StatelessWidget {
  const _PrototypeProgressRail({required this.value});

  final double value;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 12,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(999),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: FractionallySizedBox(
        widthFactor: value.clamp(0, 1),
        alignment: Alignment.centerLeft,
        child: Container(
          decoration: BoxDecoration(
            color: AppTheme.brandBlue,
            borderRadius: BorderRadius.circular(999),
            boxShadow: const [
              BoxShadow(
                color: Color(0x3D544CD2),
                blurRadius: 6,
                offset: Offset(2, 2),
              ),
              BoxShadow(
                color: Color(0x52FFFFFF),
                blurRadius: 6,
                offset: Offset(-2, -2),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HeroProgressCard extends StatelessWidget {
  const _HeroProgressCard({
    required this.percent,
    required this.completed,
    required this.dense,
  });

  final double percent;
  final int completed;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final displayPercent = (percent * 100).round();
    return Container(
      constraints: BoxConstraints(minHeight: dense ? 120 : 150),
      padding: EdgeInsets.all(dense ? 14 : 22),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(32),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(
            right: 0,
            top: -4,
            child: Container(
              width: dense ? 56 : 82,
              height: dense ? 56 : 82,
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(999),
                boxShadow: AppTheme.shadowRaised,
              ),
            ),
          ),
          Positioned(
            right: dense ? 18 : 27,
            top: dense ? 14 : 23,
            child: Container(
              width: dense ? 18 : 28,
              height: dense ? 18 : 28,
              decoration: BoxDecoration(
                color: AppTheme.success,
                borderRadius: BorderRadius.circular(999),
                boxShadow: AppTheme.shadowSmall,
              ),
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '$displayPercent%',
                style: TextStyle(
                  color: AppTheme.brandBlue,
                  fontSize: dense ? 38 : 48,
                  fontWeight: FontWeight.w800,
                  height: 1,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                '课程整体进度',
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
              SizedBox(height: dense ? 6 : 16),
              Text(
                '已完成 $completed 个课时',
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
              SizedBox(height: dense ? 6 : 8),
              _PrototypeProgressRail(value: percent),
            ],
          ),
        ],
      ),
    );
  }
}

class _HomeWideLayout extends StatelessWidget {
  const _HomeWideLayout({
    required this.availableHeight,
    required this.dashboard,
    required this.progressByCourseId,
    required this.isSwitchingCourse,
    required this.onContinueLearning,
    required this.onResumeCourse,
    required this.onSwitchCourse,
    required this.onOpenRoute,
  });

  final double availableHeight;
  final HomeDashboardModel? dashboard;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final Future<void> Function(HomeDashboardModel dashboard) onContinueLearning;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    final dense = availableHeight.isFinite && availableHeight < 680;
    final content = Column(
      children: [
        _HomePrototypeTitle(
          onOpenRoute: onOpenRoute,
          dense: dense,
        ),
        SizedBox(height: dense ? 12 : 22),
        _HomeHeroDashboard(
          dashboard: dashboard,
          dense: dense,
          onContinueLearning: onContinueLearning,
        ),
        SizedBox(height: dense ? 12 : 16),
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(
                child: _TodayReviewCard(
                  tasks: dashboard?.todayReviewTasks ?? const [],
                  dense: dense,
                  onOpenRoute: onOpenRoute,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _RecentCoursesCard(
                  recentCourses: dashboard?.recentCourses ?? const [],
                  progressByCourseId: progressByCourseId,
                  isSwitchingCourse: isSwitchingCourse,
                  dense: dense,
                  onResumeCourse: onResumeCourse,
                  onSwitchCourse: onSwitchCourse,
                ),
              ),
            ],
          ),
        ),
      ],
    );
    if (!availableHeight.isFinite) {
      return content;
    }
    return SizedBox(height: availableHeight, child: content);
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
        _HomePrototypeTitle(onOpenRoute: onOpenRoute),
        const SizedBox(height: 16),
        _HomeHeroDashboard(
          dashboard: dashboard,
          onContinueLearning: onContinueLearning,
        ),
        const SizedBox(height: 16),
        _TodayReviewCard(
          tasks: dashboard?.todayReviewTasks ?? const [],
          dense: false,
          onOpenRoute: onOpenRoute,
        ),
        const SizedBox(height: 16),
        _RecentCoursesCard(
          recentCourses: dashboard?.recentCourses ?? const [],
          progressByCourseId: progressByCourseId,
          isSwitchingCourse: isSwitchingCourse,
          dense: false,
          onResumeCourse: onResumeCourse,
          onSwitchCourse: onSwitchCourse,
        ),
      ],
    );
  }
}

// ignore: unused_element
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

// ignore: unused_element
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

// ignore: unused_element
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
    required this.dense,
    required this.onOpenRoute,
  });

  final List<HomeReviewTaskModel> tasks;
  final bool dense;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    final visibleTasks = tasks.take(3).toList();
    return _PrototypeSectionCard(
      markColor: AppTheme.success,
      padding: EdgeInsets.all(dense ? 14 : 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '推荐复习'),
          SizedBox(height: dense ? 8 : 14),
          if (visibleTasks.isEmpty)
            const _EmptyText('今天没有到期复习任务')
          else
            for (var index = 0; index < visibleTasks.length; index++) ...[
              _ReviewTaskRow(
                index: index + 1,
                task: visibleTasks[index],
                dense: dense,
                onOpenRoute: onOpenRoute,
              ),
              if (index != visibleTasks.length - 1)
                SizedBox(height: dense ? 8 : 12),
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
    required this.dense,
    required this.onResumeCourse,
    required this.onSwitchCourse,
  });

  final List<CourseSummaryModel> recentCourses;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final bool dense;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;

  @override
  Widget build(BuildContext context) {
    final visibleCourses = recentCourses.take(2).toList();
    return _PrototypeSectionCard(
      markColor: AppTheme.accentLight,
      padding: EdgeInsets.all(dense ? 14 : 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '最近课程'),
          SizedBox(height: dense ? 8 : 14),
          if (visibleCourses.isEmpty)
            const _EmptyText('暂无最近课程')
          else
            for (final course in visibleCourses) ...[
              _RecentCourseTile(
                course: course,
                progress: progressByCourseId[course.courseId]?.valueOrNull,
                progressState: progressByCourseId[course.courseId],
                isSwitching: isSwitchingCourse,
                dense: dense,
                onResume: () => onResumeCourse(course),
                onSwitch: () => onSwitchCourse(course),
              ),
              if (course != visibleCourses.last)
                SizedBox(height: dense ? 8 : 12),
            ],
        ],
      ),
    );
  }
}

class _PrototypeSectionCard extends StatelessWidget {
  const _PrototypeSectionCard({
    required this.child,
    required this.markColor,
    required this.padding,
  });

  final Widget child;
  final Color markColor;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(32),
        boxShadow: AppTheme.shadowRaised,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(32),
        child: Stack(
          children: [
            Padding(
              padding: padding,
              child: child,
            ),
            Positioned(
              right: 22,
              top: 22,
              child: Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  color: markColor,
                  borderRadius: BorderRadius.circular(999),
                  boxShadow: AppTheme.shadowInsetLook,
                ),
              ),
            ),
          ],
        ),
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
    required this.index,
    required this.task,
    required this.dense,
    required this.onOpenRoute,
  });

  final int index;
  final HomeReviewTaskModel task;
  final bool dense;
  final void Function(String? route) onOpenRoute;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(dense ? 10 : 14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 430;
          final main = Row(
            children: [
              Container(
                width: dense ? 36 : 42,
                height: dense ? 36 : 42,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: AppTheme.shadowRaised,
                ),
                child: Text(
                  '$index',
                  style: TextStyle(
                    color: index == 2 ? AppTheme.success : AppTheme.brandBlue,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              SizedBox(width: dense ? 10 : 14),
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
                    const SizedBox(height: 3),
                    Text(
                      task.reasonText,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppTheme.muted,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
          final action = OutlinedButton(
            onPressed: task.nextRoute == null
                ? null
                : () => onOpenRoute(task.nextRoute),
            child: const Text('复习'),
          );
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                main,
                SizedBox(height: dense ? 8 : 10),
                action,
              ],
            );
          }
          return Row(
            children: [
              Expanded(child: main),
              SizedBox(width: dense ? 10 : 12),
              action,
            ],
          );
        },
      ),
    );
  }
}

class _RecentCourseTile extends StatelessWidget {
  const _RecentCourseTile({
    required this.course,
    required this.progress,
    required this.progressState,
    required this.isSwitching,
    required this.dense,
    required this.onResume,
    required this.onSwitch,
  });

  final CourseSummaryModel course;
  final CourseProgressModel? progress;
  final AsyncValue<CourseProgressModel>? progressState;
  final bool isSwitching;
  final bool dense;
  final VoidCallback onResume;
  final VoidCallback onSwitch;

  @override
  Widget build(BuildContext context) {
    final progressValue = (progressState?.isLoading ?? false)
        ? 0.0
        : _courseProgressValue(progress, course);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(28),
      child: InkWell(
        onTap: isSwitching ? null : onResume,
        onLongPress: isSwitching ? null : onSwitch,
        borderRadius: BorderRadius.circular(28),
        child: Container(
          key: Key('home_recent_course_tile_${course.courseId}'),
          width: double.infinity,
          padding: EdgeInsets.all(dense ? 12 : 18),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(28),
            boxShadow: AppTheme.shadowInsetLook,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                course.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: dense ? 16 : 20,
                  fontWeight: FontWeight.w800,
                  height: 1.15,
                ),
              ),
              SizedBox(height: dense ? 8 : 14),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  StatusPill(label: _pipelineLabel(course.pipelineStatus)),
                  StatusPill(
                    label: _lifecycleLabel(course.lifecycleStatus),
                    color: AppTheme.accentLight,
                  ),
                ],
              ),
              SizedBox(height: dense ? 8 : 14),
              _PrototypeProgressRail(value: progressValue),
            ],
          ),
        ),
      ),
    );
  }
}

// ignore: unused_element
class _RecentCourseDetails extends StatelessWidget {
  const _RecentCourseDetails({
    required this.course,
    required this.progress,
    required this.progressState,
    required this.isSwitching,
    required this.dense,
    required this.onResume,
    required this.onSwitch,
  });

  final CourseSummaryModel course;
  final CourseProgressModel? progress;
  final AsyncValue<CourseProgressModel>? progressState;
  final bool isSwitching;
  final bool dense;
  final VoidCallback onResume;
  final VoidCallback onSwitch;

  @override
  Widget build(BuildContext context) {
    final resumeText = _resumeText(progress, course);
    final progressValue = (progressState?.isLoading ?? false)
        ? 0.0
        : _courseProgressValue(progress, course);
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(28),
      child: InkWell(
        onTap: onResume,
        onLongPress: isSwitching ? null : onSwitch,
        borderRadius: BorderRadius.circular(28),
        child: Container(
          padding: EdgeInsets.all(dense ? 12 : 18),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(28),
            boxShadow: AppTheme.shadowInsetLook,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                course.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: AppTheme.ink,
                  fontSize: dense ? 16 : 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
              SizedBox(height: dense ? 8 : 14),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  StatusPill(label: _pipelineLabel(course.pipelineStatus)),
                  StatusPill(
                    label: _lifecycleLabel(course.lifecycleStatus),
                    color: AppTheme.accentLight,
                  ),
                ],
              ),
              if (!dense) ...[
                const SizedBox(height: 14),
                Text(
                  (progressState?.isLoading ?? false)
                      ? '正在读取最近学习位置...'
                      : resumeText,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    height: 1.35,
                  ),
                ),
              ],
              SizedBox(height: dense ? 8 : 10),
              _PrototypeProgressRail(value: progressValue),
            ],
          ),
        ),
      ),
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
    return Row(
      children: [
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(12),
            boxShadow: AppTheme.shadowInsetLook,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 22,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ],
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

double _courseProgressValue(
  CourseProgressModel? progress,
  CourseSummaryModel course,
) {
  if (course.pipelineStatus == 'succeeded') {
    return 1;
  }
  if (progress?.lastPositionSec != null && progress!.lastPositionSec! > 0) {
    return 0.45;
  }
  if (progress?.hasResumeTarget ?? false) {
    return 0.32;
  }
  if (course.currentLessonId != null) {
    return 0.18;
  }
  return 0;
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
