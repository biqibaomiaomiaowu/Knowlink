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
import '../../shared/models/review_models.dart';
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
        onResumeCourse: _resumeCourse,
        onSwitchCourse: _switchCourse,
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
    ref.read(playerStateProvider.notifier).state = PlayerState(
      positionSec: progress?.lastPositionSec ?? 0,
    );
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
}

class _HomeBody extends StatelessWidget {
  const _HomeBody({
    required this.state,
    required this.onRetry,
    required this.onResumeCourse,
    required this.onSwitchCourse,
  });

  final HomeState state;
  final VoidCallback onRetry;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;

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
                onResumeCourse: onResumeCourse,
                onSwitchCourse: onSwitchCourse,
              )
            : _HomeNarrowLayout(
                dashboard: dashboard,
                progressByCourseId: state.progressByCourseId,
                isSwitchingCourse: state.currentCourseSwitch.isLoading,
                onResumeCourse: onResumeCourse,
                onSwitchCourse: onSwitchCourse,
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
    required this.onResumeCourse,
    required this.onSwitchCourse,
  });

  final HomeDashboardModel? dashboard;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _HeroActionCard(
                icon: Icons.cloud_upload_outlined,
                title: '自主导入',
                description: '支持上传课程视频与学习资料，快速构建你的专属学习库。',
                onTap: () => context.go('/import'),
              ),
            ),
            const SizedBox(width: 32),
            Expanded(
              child: _HeroActionCard(
                icon: Icons.star_border_rounded,
                title: '智能课程推荐',
                description: '基于学习目标和学习记录，为你推荐合适的课程内容。',
                onTap: dashboard?.recommendationEntryEnabled == false
                    ? null
                    : () => context.go('/recommend'),
                tint: const Color(0xFF6366F1),
              ),
            ),
          ],
        ),
        const SizedBox(height: 30),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _RecentLearningCard(
                recentCourses: dashboard?.recentCourses ?? const [],
                progressByCourseId: progressByCourseId,
                isSwitchingCourse: isSwitchingCourse,
                onResumeCourse: onResumeCourse,
                onSwitchCourse: onSwitchCourse,
              ),
            ),
            const SizedBox(width: 32),
            Expanded(
              child: _KnowledgeListCard(
                items: dashboard?.dailyRecommendedKnowledgePoints ?? const [],
              ),
            ),
          ],
        ),
        const SizedBox(height: 30),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _StatsCard(stats: dashboard?.learningStats),
            ),
            const SizedBox(width: 32),
            Expanded(
              child: _ReviewPromptCard(
                tasks: dashboard?.topReviewTasks ?? const [],
                courseId: _firstRecentCourseId(dashboard),
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
    required this.onResumeCourse,
    required this.onSwitchCourse,
  });

  final HomeDashboardModel? dashboard;
  final Map<int, AsyncValue<CourseProgressModel>> progressByCourseId;
  final bool isSwitchingCourse;
  final Future<void> Function(CourseSummaryModel course) onResumeCourse;
  final Future<void> Function(CourseSummaryModel course) onSwitchCourse;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _HeroActionCard(
          icon: Icons.cloud_upload_outlined,
          title: '自主导入',
          description: '支持上传课程视频与学习资料，快速构建你的专属学习库。',
          onTap: () => context.go('/import'),
        ),
        const SizedBox(height: 16),
        _HeroActionCard(
          icon: Icons.star_border_rounded,
          title: '智能课程推荐',
          description: '基于学习目标和学习记录，为你推荐合适的课程内容。',
          onTap: dashboard?.recommendationEntryEnabled == false
              ? null
              : () => context.go('/recommend'),
          tint: const Color(0xFF6366F1),
        ),
        const SizedBox(height: 16),
        _RecentLearningCard(
          recentCourses: dashboard?.recentCourses ?? const [],
          progressByCourseId: progressByCourseId,
          isSwitchingCourse: isSwitchingCourse,
          onResumeCourse: onResumeCourse,
          onSwitchCourse: onSwitchCourse,
        ),
        const SizedBox(height: 16),
        _KnowledgeListCard(
          items: dashboard?.dailyRecommendedKnowledgePoints ?? const [],
        ),
        const SizedBox(height: 16),
        _StatsCard(stats: dashboard?.learningStats),
        const SizedBox(height: 16),
        _ReviewPromptCard(
          tasks: dashboard?.topReviewTasks ?? const [],
          courseId: _firstRecentCourseId(dashboard),
        ),
      ],
    );
  }
}

class _HeroActionCard extends StatelessWidget {
  const _HeroActionCard({
    required this.icon,
    required this.title,
    required this.description,
    this.onTap,
    this.tint = AppTheme.brandBlue,
  });

  final IconData icon;
  final String title;
  final String description;
  final VoidCallback? onTap;
  final Color tint;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 560;
        return SectionCard(
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 20 : 32,
            vertical: compact ? 20 : 26,
          ),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(8),
            child: Row(
              children: [
                SoftIcon(icon: icon, color: tint, size: compact ? 62 : 86),
                SizedBox(width: compact ? 16 : 24),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppTheme.ink,
                          fontSize: compact ? 22 : 28,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        description,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppTheme.muted,
                          height: 1.45,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Icon(
                  Icons.chevron_right_rounded,
                  color: onTap == null ? AppTheme.line : AppTheme.muted,
                  size: 34,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _RecentLearningCard extends StatelessWidget {
  const _RecentLearningCard({
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
    final course = recentCourses.isEmpty ? null : recentCourses.first;
    final progress = course == null
        ? null
        : progressByCourseId[course.courseId]?.valueOrNull;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '最近学习'),
          const SizedBox(height: 18),
          if (course == null)
            const _EmptyText('暂无最近学习课程。')
          else
            _RecentLearningDetails(
              course: course,
              progress: progress,
              progressState: progressByCourseId[course.courseId],
              isSwitching: isSwitchingCourse,
              onResume: () => onResumeCourse(course),
              onSwitch: () => onSwitchCourse(course),
            ),
        ],
      ),
    );
  }
}

class _RecentLearningDetails extends StatelessWidget {
  const _RecentLearningDetails({
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
    final resumeText = _resumeText(progress);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          course.title,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: AppTheme.ink,
            fontSize: 22,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 12),
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
        const SizedBox(height: 16),
        if (progressState?.isLoading ?? false)
          const Text(
            '正在读取最近学习位置...',
            style:
                TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w600),
          )
        else
          Text(
            resumeText,
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
              height: 1.5,
            ),
          ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              '更新：${_formatDate(course.updatedAt)}',
              style: const TextStyle(
                color: AppTheme.muted,
                fontWeight: FontWeight.w600,
              ),
            ),
            OutlinedButton.icon(
              onPressed: onResume,
              icon: const Icon(Icons.play_arrow_rounded),
              label: const Text('继续学习'),
            ),
            OutlinedButton.icon(
              onPressed: isSwitching ? null : onSwitch,
              icon: const Icon(Icons.check_circle_outline),
              label: Text(isSwitching ? '正在切换' : '设为当前课程'),
            ),
          ],
        ),
      ],
    );
  }
}

class _KnowledgeListCard extends StatelessWidget {
  const _KnowledgeListCard({
    required this.items,
  });

  final List<DailyRecommendedKnowledgePointModel> items;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '今日推荐知识点'),
          const SizedBox(height: 12),
          if (items.isEmpty)
            const _EmptyText('暂无今日推荐知识点。')
          else
            for (final item in items.take(3))
              _KnowledgeRow(
                title: item.knowledgePoint,
                meta: item.reason,
                targetCourseId: item.targetCourseId,
              ),
        ],
      ),
    );
  }
}

class _KnowledgeRow extends StatelessWidget {
  const _KnowledgeRow({
    required this.title,
    required this.meta,
    required this.targetCourseId,
  });

  final String title;
  final String meta;
  final int? targetCourseId;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          const SoftIcon(icon: Icons.auto_awesome_outlined, size: 54),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  meta,
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
          if (targetCourseId != null)
            IconButton(
              tooltip: '打开课程',
              onPressed: () => context.go('/courses/$targetCourseId/handout'),
              icon: const Icon(Icons.chevron_right_rounded),
            ),
        ],
      ),
    );
  }
}

class _StatsCard extends StatelessWidget {
  const _StatsCard({
    required this.stats,
  });

  final LearningStatsModel? stats;

  @override
  Widget build(BuildContext context) {
    final value = stats ??
        const LearningStatsModel(
          streakDays: 0,
          completedCourses: 0,
          reviewTasksCompleted: 0,
          totalLearningMinutes: 0,
        );
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: '学习统计'),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              MetricBox(
                icon: Icons.local_fire_department_outlined,
                label: '连续学习',
                value: '${value.streakDays} 天',
              ),
              MetricBox(
                icon: Icons.schedule_rounded,
                label: '总学习时长',
                value: '${value.totalLearningMinutes} 分钟',
              ),
              MetricBox(
                icon: Icons.menu_book_outlined,
                label: '完成课程',
                value: '${value.completedCourses}',
                color: const Color(0xFF22C55E),
              ),
              MetricBox(
                icon: Icons.check_circle_outline,
                label: '完成复习',
                value: '${value.reviewTasksCompleted}',
                color: const Color(0xFF8B5CF6),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ReviewPromptCard extends StatelessWidget {
  const _ReviewPromptCard({
    required this.tasks,
    required this.courseId,
  });

  final List<ReviewTaskModel> tasks;
  final int? courseId;

  @override
  Widget build(BuildContext context) {
    final topTasks = tasks.take(3).toList();
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionHeader(title: 'AI 复习推荐'),
          const SizedBox(height: 12),
          if (topTasks.isEmpty)
            const _EmptyText('完成测验后会在这里展示 Top3 复习任务。')
          else
            for (final task in topTasks)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _ReviewTaskRow(task: task),
              ),
          const SizedBox(height: 10),
          GradientButton(
            label: '去复习',
            icon: Icons.calendar_today_outlined,
            onPressed: courseId == null
                ? null
                : () => context.go('/courses/$courseId/review'),
          ),
        ],
      ),
    );
  }
}

class _ReviewTaskRow extends StatelessWidget {
  const _ReviewTaskRow({
    required this.task,
  });

  final ReviewTaskModel task;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          StatusPill(label: '${task.reviewOrder ?? '-'}'),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              task.reasonText,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.ink,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          StatusPill(
            label: '${task.priorityScore}',
            color: const Color(0xFFF97316),
          ),
        ],
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

String _resumeText(CourseProgressModel? progress) {
  if (progress == null || !progress.hasResumeTarget) {
    return '还没有最近学习位置，点击继续学习会进入讲义页。';
  }
  final parts = <String>[];
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

String _formatDate(DateTime value) {
  final local = value.toLocal();
  return '${local.year}-${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}

int? _firstRecentCourseId(HomeDashboardModel? dashboard) {
  final courses = dashboard?.recentCourses ?? const <CourseSummaryModel>[];
  return courses.isEmpty ? null : courses.first.courseId;
}
