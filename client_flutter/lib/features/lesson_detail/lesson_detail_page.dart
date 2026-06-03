import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/providers/lesson_detail_provider.dart';

class LessonDetailPage extends ConsumerWidget {
  const LessonDetailPage({
    required this.courseId,
    required this.lessonId,
    super.key,
  });

  final String courseId;
  final String lessonId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final request = LessonDetailRequest(
      courseId: courseId,
      lessonId: lessonId,
    );
    final detail = ref.watch(lessonDetailProvider(request));
    return AppScaffold(
      title: '课时详情',
      activeTab: KnowLinkTab.handout,
      courseId: courseId,
      body: detail.when(
        loading: () => const AppLoadingView(label: '正在加载课时详情'),
        error: (error, _) => AppErrorView(
          message: '课时详情加载失败：$error',
          onRetry: () => ref.invalidate(lessonDetailProvider(request)),
        ),
        data: (model) => _LessonDetailBody(model: model),
      ),
    );
  }
}

class _LessonDetailBody extends StatelessWidget {
  const _LessonDetailBody({required this.model});

  final LessonDetailModel model;

  @override
  Widget build(BuildContext context) {
    final lesson = model.lesson;
    return ListView(
      children: [
        PageTitle(
          title: lesson.title,
          subtitle: '第 ${lesson.orderIndex} 课 · ${lesson.lessonStatus}',
          icon: Icons.play_lesson_outlined,
        ),
        _PrimaryVideoCard(model: model),
        const SizedBox(height: 14),
        _ArtifactGrid(model: model),
        const SizedBox(height: 14),
        _ResourceSection(resources: model.lessonResources),
        const SizedBox(height: 14),
        _CitationSection(citations: model.citations),
        const SizedBox(height: 14),
        _PlaceholderSection(
          title: '知识与薄弱点',
          items: [
            ...model.knowledgePointPlaceholders,
            ...model.weaknessPlaceholders,
          ],
        ),
      ],
    );
  }
}

class _PrimaryVideoCard extends StatelessWidget {
  const _PrimaryVideoCard({required this.model});

  final LessonDetailModel model;

  @override
  Widget build(BuildContext context) {
    final video = model.primaryVideo;
    final positionText = model.positionSec == null
        ? '进度 --'
        : '进度 ${_formatSeconds(model.positionSec!)}';
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('主视频'),
          const SizedBox(height: 12),
          Container(
            height: 150,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: const Color(0xFF0F172A),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(
                  Icons.play_circle_outline,
                  color: Colors.white,
                  size: 42,
                ),
                const SizedBox(height: 10),
                Text(
                  video?.originalName ?? '暂无主视频',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              StatusPill(label: positionText),
              StatusPill(label: '讲义 ${model.lesson.handoutStatus}'),
              StatusPill(label: '测验 ${model.lesson.quizStatus}'),
              StatusPill(label: '复习 ${model.lesson.reviewStatus}'),
            ],
          ),
          if (model.nextAction != null) ...[
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: model.nextAction?.route == null
                  ? null
                  : () => context.go(model.nextAction!.route!),
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(model.nextAction!.label),
            ),
          ],
        ],
      ),
    );
  }
}

class _ArtifactGrid extends StatelessWidget {
  const _ArtifactGrid({required this.model});

  final LessonDetailModel model;

  @override
  Widget build(BuildContext context) {
    final entries = [
      _artifactEntry(model, const ['handout', 'handout_version']) ??
          const PlaceholderEntryModel(
            key: 'handout',
            title: '本节讲义',
            status: 'not_generated',
            message: '等待生成',
          ),
      _artifactEntry(model, const ['qa', 'qa_session']) ??
          const PlaceholderEntryModel(
            key: 'qa',
            title: '本节 QA',
            status: 'placeholder',
            message: '暂无会话',
          ),
      _artifactEntry(model, const ['quiz']) ??
          const PlaceholderEntryModel(
            key: 'quiz',
            title: '本节测验',
            status: 'not_generated',
            message: '等待生成',
          ),
      _artifactEntry(model, const ['review', 'review_task_run']) ??
          const PlaceholderEntryModel(
            key: 'review',
            title: '本节复习',
            status: 'not_due',
            message: '暂无复习任务',
          ),
      _artifactEntry(model, const ['graph', 'graph_snapshot']) ??
          const PlaceholderEntryModel(
            key: 'graph',
            title: '本节图谱',
            status: 'placeholder',
            message: '图谱生成暂未启用',
          ),
    ];

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('学习产物'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: entries
                .map(
                  (entry) => _ArtifactTile(
                    entry: entry,
                    courseId: model.lesson.courseId,
                    lessonId: model.lesson.lessonId,
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }
}

PlaceholderEntryModel? _artifactEntry(
  LessonDetailModel model,
  List<String> keys,
) {
  final summaries = model.artifactSummaryByKey;
  for (final key in keys) {
    final entry = summaries[key];
    if (entry != null) {
      return entry;
    }
  }
  return null;
}

class _ArtifactTile extends StatelessWidget {
  const _ArtifactTile({
    required this.entry,
    required this.courseId,
    required this.lessonId,
  });

  final PlaceholderEntryModel entry;
  final String courseId;
  final String lessonId;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 220,
      child: OutlinedButton(
        onPressed: () => context.go(_pathFor(entry.key)),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(entry.title),
            const SizedBox(height: 4),
            Text(
              entry.status,
              style: const TextStyle(fontSize: 12, color: AppTheme.muted),
            ),
          ],
        ),
      ),
    );
  }

  String _pathFor(String key) {
    return switch (key) {
      'qa' || 'qa_session' => '/courses/$courseId/lessons/$lessonId/qa',
      'handout' ||
      'handout_version' =>
        '/courses/$courseId/lessons/$lessonId/handout',
      'review' ||
      'review_task_run' =>
        '/courses/$courseId/lessons/$lessonId/review',
      'graph' ||
      'graph_snapshot' =>
        '/courses/$courseId/lessons/$lessonId/graph',
      _ => '/courses/$courseId/lessons/$lessonId/review',
    };
  }
}

class _ResourceSection extends StatelessWidget {
  const _ResourceSection({required this.resources});

  final List<ScopedResourceModel> resources;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('课时资料'),
          const SizedBox(height: 12),
          if (resources.isEmpty)
            const Text('暂无课时资料。')
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

class _CitationSection extends StatelessWidget {
  const _CitationSection({required this.citations});

  final List<CitationModel> citations;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionLabel('引用证据'),
          const SizedBox(height: 12),
          if (citations.isEmpty)
            const Text('暂无引用。')
          else
            ...citations.map(
              (citation) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.format_quote_outlined),
                title: Text(citation.refLabel),
                subtitle: Text(
                  [
                    if (citation.lessonTitle != null) citation.lessonTitle!,
                    if (citation.resourceName != null) citation.resourceName!,
                  ].join(' · '),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PlaceholderSection extends StatelessWidget {
  const _PlaceholderSection({
    required this.title,
    required this.items,
  });

  final String title;
  final List<PlaceholderEntryModel> items;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionLabel(title),
          const SizedBox(height: 12),
          if (items.isEmpty)
            const Text('暂无占位信息。')
          else
            ...items.map(
              (item) => ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.pending_outlined),
                title: Text(item.title),
                subtitle: Text(item.message),
                trailing: StatusPill(label: item.status),
              ),
            ),
        ],
      ),
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

String _formatSeconds(int seconds) {
  final minutes = (seconds ~/ 60).toString().padLeft(2, '0');
  final secs = (seconds % 60).toString().padLeft(2, '0');
  return '$minutes:$secs';
}
