import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/course_library_provider.dart';

class CourseLibraryPage extends ConsumerWidget {
  const CourseLibraryPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courses = ref.watch(courseLibraryProvider);
    return AppScaffold(
      title: '课程库',
      activeTab: KnowLinkTab.library,
      body: courses.when(
        loading: () => const AppLoadingView(label: '正在加载课程库'),
        error: (error, _) => AppErrorView(
          message: '课程库加载失败：$error',
          onRetry: () => ref.invalidate(courseLibraryProvider),
        ),
        data: (items) => _CourseLibraryBody(items: items),
      ),
    );
  }
}

class _CourseLibraryBody extends StatelessWidget {
  const _CourseLibraryBody({required this.items});

  final List<CourseLibraryItemModel> items;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        const PageTitle(
          title: '课程库',
          subtitle: '按最近活动查看全部课程，进入课程工作台继续学习。',
          icon: Icons.library_books_outlined,
        ),
        if (items.isEmpty)
          const SectionCard(child: Text('暂无课程。'))
        else
          ...items.map((item) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: _CourseTile(item: item),
              )),
      ],
    );
  }
}

class _CourseTile extends ConsumerWidget {
  const _CourseTile({required this.item});

  final CourseLibraryItemModel item;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mastery = item.overallMasteryScore == null
        ? '掌握度 --'
        : '掌握度 ${(item.overallMasteryScore! * 100).round()}%';
    final masteryValue = item.overallMasteryScore?.clamp(0, 1).toDouble();
    final progressLabel = '生成进度：${item.pipelineStage} / ${item.pipelineStatus}';
    return SectionCard(
      child: InkWell(
        onTap: () => _openWorkbench(context, ref),
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(2),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      item.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppTheme.ink,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  if (item.isCurrent)
                    const StatusPill(
                      label: '当前课程',
                      color: Color(0xFF16A34A),
                      icon: Icons.check_circle_outline,
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  StatusPill(label: '学习状态：${item.learningStatus}'),
                  StatusPill(label: item.entryType),
                ],
              ),
              const SizedBox(height: 14),
              LayoutBuilder(
                builder: (context, constraints) {
                  final compact = constraints.maxWidth < 760;
                  final metrics = [
                    _MetricTile(
                      icon: Icons.video_library_outlined,
                      label: '课时',
                      value: '${item.lessonCount}',
                    ),
                    _MetricTile(
                      icon: Icons.folder_outlined,
                      label: '课程资料',
                      value: '${item.courseResourceCount}',
                    ),
                    _MetricTile(
                      icon: Icons.event_repeat_outlined,
                      label: '待复习',
                      value: '${item.pendingReviewCount}',
                    ),
                  ];
                  if (compact) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: metrics
                          .map(
                            (metric) => Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: metric,
                            ),
                          )
                          .toList(),
                    );
                  }
                  return Row(
                    children: metrics
                        .map(
                          (metric) => Expanded(
                            child: Padding(
                              padding: const EdgeInsets.only(right: 10),
                              child: metric,
                            ),
                          ),
                        )
                        .toList(),
                  );
                },
              ),
              const SizedBox(height: 14),
              _ProgressSummary(
                progressLabel: progressLabel,
                masteryLabel: mastery,
                masteryValue: masteryValue,
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 18,
                runSpacing: 8,
                children: [
                  _InlineMetric('最近活动：${_formatDate(item.lastActivityAt)}'),
                  _InlineMetric(
                    '当前课时：${item.currentLessonTitle ?? '未选择'}',
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  FilledButton.icon(
                    onPressed: () => _continueLearning(context, ref),
                    icon: const Icon(Icons.play_arrow_outlined),
                    label: const Text('继续学习'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => _openWorkbench(context, ref),
                    icon: const Icon(Icons.dashboard_outlined),
                    label: const Text('进入工作台'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _continueLearning(BuildContext context, WidgetRef ref) {
    ref.read(courseFlowProvider.notifier).startCourse(item.courseId);
    final lessonId = item.currentLessonId;
    if (lessonId == null) {
      _go(context, '/courses/${item.courseId}');
      return;
    }
    ref.read(activeLessonProvider.notifier).state = LessonResumeTarget(
          courseId: item.courseId,
          lessonId: lessonId,
        );
    _go(context, '/courses/${item.courseId}/lessons/$lessonId/handout');
  }

  void _openWorkbench(BuildContext context, WidgetRef ref) {
    ref.read(courseFlowProvider.notifier).startCourse(item.courseId);
    _go(context, '/courses/${item.courseId}');
  }

  void _go(BuildContext context, String path) {
    try {
      context.go(path);
    } catch (_) {
      // Widget tests can mount this page without a router.
    }
  }
}

class _InlineMetric extends StatelessWidget {
  const _InlineMetric(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        color: AppTheme.muted,
        fontWeight: FontWeight.w700,
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 76),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.panel,
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppTheme.brandBlue, size: 24),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '$label $value',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 18,
                letterSpacing: 0,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Icon(
            Icons.chevron_right,
            color: AppTheme.muted.withValues(alpha: 0.6),
            size: 18,
          ),
        ],
      ),
    );
  }
}

class _ProgressSummary extends StatelessWidget {
  const _ProgressSummary({
    required this.progressLabel,
    required this.masteryLabel,
    required this.masteryValue,
  });

  final String progressLabel;
  final String masteryLabel;
  final double? masteryValue;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 18,
            runSpacing: 8,
            children: [
              _InlineMetric(progressLabel),
              _InlineMetric(masteryLabel),
            ],
          ),
          const SizedBox(height: 10),
          ProgressRail(
            value: masteryValue ?? 0,
            color: masteryValue == null
                ? const Color(0xFF94A3B8)
                : AppTheme.brandBlue,
          ),
        ],
      ),
    );
  }
}

String _formatDate(DateTime? value) {
  if (value == null) {
    return '--';
  }
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}
