import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/providers/course_library_provider.dart';

class CourseLibraryPage extends ConsumerWidget {
  const CourseLibraryPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final courses = ref.watch(courseLibraryProvider);
    return AppScaffold(
      title: '课程库',
      activeTab: KnowLinkTab.home,
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

class _CourseTile extends StatelessWidget {
  const _CourseTile({required this.item});

  final CourseLibraryItemModel item;

  @override
  Widget build(BuildContext context) {
    final mastery = item.overallMasteryScore == null
        ? '掌握度 --'
        : '掌握度 ${(item.overallMasteryScore! * 100).round()}%';
    return SectionCard(
      child: InkWell(
        onTap: () => context.go('/courses/${item.courseId}'),
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
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  StatusPill(label: '学习状态：${item.learningStatus}'),
                  StatusPill(
                    label: '${item.pipelineStage} / ${item.pipelineStatus}',
                    color: const Color(0xFF64748B),
                  ),
                  StatusPill(label: item.entryType),
                ],
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 18,
                runSpacing: 8,
                children: [
                  _InlineMetric('最近活动：${_formatDate(item.lastActivityAt)}'),
                  _InlineMetric('课时 ${item.lessonCount}'),
                  _InlineMetric('课程资料 ${item.courseResourceCount}'),
                  _InlineMetric(
                    '当前课时：${item.currentLessonTitle ?? '未选择'}',
                  ),
                  _InlineMetric(mastery),
                  _InlineMetric('待复习 ${item.pendingReviewCount}'),
                ],
              ),
            ],
          ),
        ),
      ),
    );
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

String _formatDate(DateTime? value) {
  if (value == null) {
    return '--';
  }
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  return '${value.year}-$month-$day';
}
