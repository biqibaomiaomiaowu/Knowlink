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
        _QuickEntryGrid(courseId: course.courseId, entries: model.quickEntries),
        const SizedBox(height: 14),
        _LessonList(courseId: course.courseId, lessons: model.lessons),
        const SizedBox(height: 14),
        _ResourceList(resources: model.courseResources),
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
                detail: '${course.lessonCount} 节课',
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
                label: '当前节课',
                value: course.currentLessonTitle ?? '未选择',
                detail: model.currentLesson?.nextAction?.reason,
              ),
            ],
          ),
          if (model.nextActions.isNotEmpty) ...[
            const SizedBox(height: 16),
            ...model.nextActions.map(
              (action) => _NextActionRow(action: action),
            ),
          ],
        ],
      ),
    );
  }
}

class _QuickEntryGrid extends StatelessWidget {
  const _QuickEntryGrid({
    required this.courseId,
    required this.entries,
  });

  final String courseId;
  final List<PlaceholderEntryModel> entries;

  @override
  Widget build(BuildContext context) {
    final visible = entries.isEmpty ? _fallbackEntries(courseId) : entries;
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('课程入口'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: visible
                .map(
                  (entry) => _EntryButton(
                    entry: entry,
                    onTap: () => _goEntry(context, courseId, entry.key),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }

  List<PlaceholderEntryModel> _fallbackEntries(String courseId) {
    return [
      const PlaceholderEntryModel(
        key: 'course_qa',
        title: '全课程 QA',
        status: 'placeholder',
        message: '基于全部节课提问',
      ),
      const PlaceholderEntryModel(
        key: 'course_graph',
        title: '课程图谱',
        status: 'placeholder',
        message: '图谱生成暂未启用',
      ),
      const PlaceholderEntryModel(
        key: 'comprehensive_quiz',
        title: '综合测验',
        status: 'placeholder',
        message: '综合测验等待生成',
      ),
      const PlaceholderEntryModel(
        key: 'course_review',
        title: '课程总复习',
        status: 'placeholder',
        message: '复习计划等待生成',
      ),
      const PlaceholderEntryModel(
        key: 'report',
        title: '学习报告',
        status: 'placeholder',
        message: '报告暂未启用',
      ),
      const PlaceholderEntryModel(
        key: 'export',
        title: '课程导出',
        status: 'placeholder',
        message: '导出暂未启用',
      ),
      const PlaceholderEntryModel(
        key: 'settings',
        title: '课程设置',
        status: 'ready',
        message: '调整课程信息',
      ),
    ];
  }

  void _goEntry(BuildContext context, String courseId, String key) {
    final path = switch (key) {
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
    context.go(path);
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
          const _SectionLabel('节课列表'),
          const SizedBox(height: 12),
          if (lessons.isEmpty)
            const Text('暂无节课。')
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
                  '/courses/$courseId/lessons/${lesson.lessonId}',
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
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onTap,
      icon: Icon(_iconFor(entry.key)),
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
