import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/providers/course_workbench_provider.dart';

class CourseWorkbenchPage extends ConsumerWidget {
  const CourseWorkbenchPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final workbench = ref.watch(courseWorkbenchProvider(courseId));
    return AppScaffold(
      title: '课程工作台',
      activeTab: KnowLinkTab.home,
      courseId: courseId,
      body: workbench.when(
        loading: () => const AppLoadingView(label: '正在加载课程工作台'),
        error: (error, _) => AppErrorView(
          message: '课程工作台加载失败：$error',
          onRetry: () => ref.invalidate(courseWorkbenchProvider(courseId)),
        ),
        data: (model) => _WorkbenchBody(model: model),
      ),
    );
  }
}

class _WorkbenchBody extends StatelessWidget {
  const _WorkbenchBody({required this.model});

  final CourseWorkbenchModel model;

  @override
  Widget build(BuildContext context) {
    final course = model.course;
    return ListView(
      children: [
        PageTitle(
          title: course.title,
          subtitle: '课程工作台 · ${course.learningStatus}',
          icon: Icons.school_outlined,
        ),
        _ProgressCard(model: model),
        const SizedBox(height: 14),
        _QuickEntryGrid(
          courseId: course.courseId,
          currentLessonId:
              model.currentLesson?.lessonId ?? course.currentLessonId,
          entries: model.quickEntries,
        ),
        const SizedBox(height: 14),
        _CurrentLessonCard(
          courseId: course.courseId,
          currentLesson: model.currentLesson,
          nextActions: model.nextActions,
        ),
        const SizedBox(height: 14),
        _ResourceList(resources: model.courseResources),
        const SizedBox(height: 14),
        _LessonList(courseId: course.courseId, lessons: model.lessons),
      ],
    );
  }
}

class _ProgressCard extends StatelessWidget {
  const _ProgressCard({required this.model});

  final CourseWorkbenchModel model;

  @override
  Widget build(BuildContext context) {
    final course = model.course;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              if (course.isCurrent)
                const StatusPill(
                  label: '当前课程',
                  color: Color(0xFF16A34A),
                ),
              StatusPill(label: course.pipelineStage),
              StatusPill(label: course.pipelineStatus),
              StatusPill(label: course.entryType),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              MetricBox(
                icon: Icons.timeline_outlined,
                label: '学习进度',
                value: '进度 ${model.progressPct}%',
                detail: '${course.lessonCount} 课时',
              ),
              MetricBox(
                icon: Icons.psychology_alt_outlined,
                label: '课程掌握',
                value: course.overallMasteryScore == null
                    ? '--'
                    : '${(course.overallMasteryScore! * 100).round()}%',
                detail: '待复习 ${course.pendingReviewCount}',
              ),
              MetricBox(
                icon: Icons.play_circle_outline,
                label: '当前课时',
                value: course.currentLessonTitle ?? '未选择',
                detail: model.currentLesson?.nextAction?.reason,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuickEntryGrid extends StatelessWidget {
  const _QuickEntryGrid({
    required this.courseId,
    required this.currentLessonId,
    required this.entries,
  });

  final String courseId;
  final String? currentLessonId;
  final List<PlaceholderEntryModel> entries;

  @override
  Widget build(BuildContext context) {
    final byKey = {for (final entry in entries) entry.key: entry};
    final primaryEntries = _primaryEntryKeys
        .map((key) => _primaryEntryForKey(byKey, key))
        .toList();
    final secondaryEntries = _secondaryEntryKeys
        .map((key) =>
            byKey[key] ?? (entries.isEmpty ? _secondaryFallback(key) : null))
        .whereType<PlaceholderEntryModel>()
        .map(_secondaryDisplayEntry)
        .toList();

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('主要入口'),
          const SizedBox(height: 12),
          Wrap(
            key: const Key('course_workbench_primary_entries'),
            spacing: 10,
            runSpacing: 10,
            children: primaryEntries
                .map(
                  (entry) => _EntryButton(
                    entry: entry,
                    onTap: entry.enabled
                        ? () => _goEntry(context, courseId, entry)
                        : null,
                  ),
                )
                .toList(),
          ),
          if (secondaryEntries.isNotEmpty) ...[
            const SizedBox(height: 18),
            const Divider(height: 1),
            const SizedBox(height: 14),
            const Text(
              '更多工具',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 14,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              key: const Key('course_workbench_secondary_entries'),
              spacing: 8,
              runSpacing: 8,
              children: secondaryEntries
                  .map(
                    (entry) => _SecondaryEntryButton(
                      entry: entry,
                      onTap: entry.enabled
                          ? () => _goEntry(context, courseId, entry)
                          : null,
                    ),
                  )
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  PlaceholderEntryModel _primaryEntryForKey(
    Map<String, PlaceholderEntryModel> byKey,
    String key,
  ) {
    final source = byKey[key];
    return PlaceholderEntryModel(
      key: key,
      title: _primaryEntryTitle(key),
      status: source?.status ?? _fallbackPrimaryStatus(key),
      message: source?.message ?? _primaryEntryMessage(key),
      enabled: source?.enabled ?? _fallbackPrimaryEnabled(key),
      target: source?.target,
      route: source?.route,
      action: source?.action,
      targetPath: source?.targetPath,
    );
  }

  bool _fallbackPrimaryEnabled(String key) {
    return key == 'lesson_study' && currentLessonId != null;
  }

  String _fallbackPrimaryStatus(String key) {
    return _fallbackPrimaryEnabled(key) ? 'ready' : 'placeholder';
  }

  PlaceholderEntryModel? _secondaryFallback(String key) {
    return switch (key) {
      'course_graph' => const PlaceholderEntryModel(
          key: 'course_graph',
          title: '课程图谱',
          status: 'placeholder',
          enabled: false,
          message: '图谱生成暂未启用',
        ),
      'report' => const PlaceholderEntryModel(
          key: 'report',
          title: '学习报告',
          status: 'placeholder',
          enabled: false,
          message: '报告暂未启用',
        ),
      'export' => const PlaceholderEntryModel(
          key: 'export',
          title: '课程导出',
          status: 'placeholder',
          enabled: false,
          message: '导出暂未启用',
        ),
      'settings' => const PlaceholderEntryModel(
          key: 'settings',
          title: '课程设置',
          status: 'ready',
          message: '调整课程信息',
        ),
      _ => null,
    };
  }

  PlaceholderEntryModel _secondaryDisplayEntry(PlaceholderEntryModel source) {
    return PlaceholderEntryModel(
      key: source.key,
      title: _secondaryEntryTitle(source.key),
      status: source.status,
      message: source.message,
      enabled: source.enabled,
      target: source.target,
      route: source.route,
      action: source.action,
      targetPath: source.targetPath,
    );
  }

  void _goEntry(
    BuildContext context,
    String courseId,
    PlaceholderEntryModel entry,
  ) {
    final path = entry.route ??
        entry.target ??
        entry.targetPath ??
        _fallbackEntryPath(
          courseId: courseId,
          currentLessonId: currentLessonId,
          key: entry.key,
        );
    context.go(path);
  }

  String _fallbackEntryPath({
    required String courseId,
    required String? currentLessonId,
    required String key,
  }) {
    return switch (key) {
      'lesson_study' when currentLessonId != null =>
        '/courses/$courseId/lessons/$currentLessonId/handout',
      'lesson_study' => '/courses/$courseId/handout',
      'course_qa' => '/courses/$courseId/qa',
      'course_graph' => '/courses/$courseId/graph',
      'comprehensive_quiz' =>
        '/courses/$courseId/review?kind=comprehensive_quiz',
      'course_review' => '/courses/$courseId/review',
      'report' => '/courses/$courseId/review?kind=report',
      'subjective_grading' =>
        '/courses/$courseId/review?kind=subjective_grading',
      'export' => '/courses/$courseId/exports',
      'settings' => '/courses/$courseId/settings',
      _ => '/courses/$courseId/review',
    };
  }
}

const _primaryEntryKeys = <String>[
  'lesson_study',
  'course_qa',
  'comprehensive_quiz',
  'course_review',
];

const _secondaryEntryKeys = <String>[
  'course_graph',
  'report',
  'export',
  'settings',
];

String _primaryEntryTitle(String key) {
  return switch (key) {
    'lesson_study' => '课时学习',
    'course_qa' => 'AI 问答',
    'comprehensive_quiz' => '测试中心',
    'course_review' => '复习中心',
    _ => '课程入口',
  };
}

String _primaryEntryMessage(String key) {
  return switch (key) {
    'lesson_study' => '进入当前课时视频与讲义',
    'course_qa' => '围绕整门课程提问',
    'comprehensive_quiz' => '生成或进入综合测验',
    'course_review' => '查看复习计划与待复习项',
    _ => '',
  };
}

String _secondaryEntryTitle(String key) {
  return switch (key) {
    'course_graph' => '课程图谱',
    'report' => '学习报告',
    'export' => '课程导出',
    'settings' => '课程设置',
    _ => '更多工具',
  };
}

class _CurrentLessonCard extends StatelessWidget {
  const _CurrentLessonCard({
    required this.courseId,
    required this.currentLesson,
    required this.nextActions,
  });

  final String courseId;
  final LessonSummaryModel? currentLesson;
  final List<NextActionModel> nextActions;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('正在学习'),
          const SizedBox(height: 12),
          if (currentLesson == null)
            const Text('还没有选择当前课时。')
          else ...[
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(
                backgroundColor: const Color(0xFFEFF6FF),
                foregroundColor: AppTheme.brandBlue,
                child: Text('${currentLesson!.orderIndex}'),
              ),
              title: Text(currentLesson!.title),
              subtitle: Text(
                '${currentLesson!.lessonStatus} · 讲义 '
                '${currentLesson!.handoutStatus} · 测验 '
                '${currentLesson!.quizStatus}',
              ),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () => context.go(
                '/courses/$courseId/lessons/${currentLesson!.lessonId}/handout',
              ),
            ),
            if (currentLesson!.nextAction?.reason != null) ...[
              const SizedBox(height: 4),
              Text(
                currentLesson!.nextAction!.reason!,
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ],
          if (nextActions.isNotEmpty) ...[
            const SizedBox(height: 10),
            ...nextActions.map(
              (action) => _NextActionRow(action: action),
            ),
          ],
        ],
      ),
    );
  }
}

class _LessonList extends StatelessWidget {
  const _LessonList({
    required this.courseId,
    required this.lessons,
  });

  final String courseId;
  final List<LessonSummaryModel> lessons;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('课时列表'),
          const SizedBox(height: 12),
          if (lessons.isEmpty)
            const Text('暂无课时。')
          else
            ...lessons.map(
              (lesson) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: CircleAvatar(
                  backgroundColor: const Color(0xFFEFF6FF),
                  foregroundColor: AppTheme.brandBlue,
                  child: Text('${lesson.orderIndex}'),
                ),
                title: Text('第 ${lesson.orderIndex} 课'),
                subtitle: Text(
                  '${lesson.title} · ${lesson.lessonStatus} · '
                  '讲义 ${lesson.handoutStatus}',
                ),
                trailing: const Icon(Icons.chevron_right_rounded),
                onTap: () => context.go(
                  '/courses/$courseId/lessons/${lesson.lessonId}/handout',
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ResourceList extends StatelessWidget {
  const _ResourceList({required this.resources});

  final List<ScopedResourceModel> resources;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('课程资料'),
          const SizedBox(height: 12),
          if (resources.isEmpty)
            const Text('暂无课程级资料。')
          else
            ...resources.map(
              (resource) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.insert_drive_file_outlined),
                title: Text(resource.originalName),
                subtitle: Text(
                  '${resource.scopeType} · ${resource.usageRole} · '
                  '${resource.resourceType}',
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _EntryButton extends StatelessWidget {
  const _EntryButton({
    required this.entry,
    required this.onTap,
  });

  final PlaceholderEntryModel entry;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 214,
      child: OutlinedButton.icon(
        onPressed: onTap,
        icon: Icon(_iconFor(entry.key)),
        label: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              entry.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            if (entry.message.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                entry.message,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SecondaryEntryButton extends StatelessWidget {
  const _SecondaryEntryButton({
    required this.entry,
    required this.onTap,
  });

  final PlaceholderEntryModel entry;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onTap,
      icon: Icon(_iconFor(entry.key), size: 18),
      label: Text(entry.title),
    );
  }
}

class _NextActionRow extends StatelessWidget {
  const _NextActionRow({required this.action});

  final NextActionModel action;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.play_arrow_rounded),
      title: Text(action.label),
      subtitle: action.reason == null ? null : Text(action.reason!),
      trailing: const Icon(Icons.chevron_right_rounded),
      onTap: action.route == null ? null : () => context.go(action.route!),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        color: AppTheme.ink,
        fontSize: 20,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

IconData _iconFor(String key) {
  return switch (key) {
    'lesson_study' => Icons.menu_book_outlined,
    'course_qa' => Icons.forum_outlined,
    'course_graph' => Icons.hub_outlined,
    'comprehensive_quiz' => Icons.quiz_outlined,
    'course_review' => Icons.refresh,
    'report' => Icons.assessment_outlined,
    'subjective_grading' => Icons.rate_review_outlined,
    'export' => Icons.download_outlined,
    'settings' => Icons.settings_outlined,
    _ => Icons.open_in_new,
  };
}
