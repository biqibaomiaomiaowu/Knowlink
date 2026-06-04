import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/services/course_lesson_api.dart';

class CourseExportsPage extends ConsumerStatefulWidget {
  const CourseExportsPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<CourseExportsPage> createState() => _CourseExportsPageState();
}

class _CourseExportsPageState extends ConsumerState<CourseExportsPage> {
  late Future<PlaceholderEntryModel> _placeholderFuture;

  @override
  void initState() {
    super.initState();
    _loadPlaceholder();
  }

  @override
  void didUpdateWidget(covariant CourseExportsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _loadPlaceholder();
    }
  }

  void _loadPlaceholder() {
    _placeholderFuture = ref
        .read(courseLessonApiProvider)
        .fetchCourseExportPlaceholder(widget.courseId);
  }

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: '课程导出',
      activeTab: KnowLinkTab.home,
      courseId: widget.courseId,
      body: FutureBuilder<PlaceholderEntryModel>(
        future: _placeholderFuture,
        builder: (context, snapshot) {
          final placeholder = snapshot.data ??
              PlaceholderEntryModel(
                key: 'export',
                title: '课程导出',
                status: snapshot.connectionState == ConnectionState.waiting
                    ? 'generating'
                    : 'placeholder',
                message: snapshot.error?.toString() ?? '导出暂未启用',
              );
          return ListView(
            children: [
              PageTitle(
                title: placeholder.title,
                subtitle: 'course:${widget.courseId}',
                icon: Icons.download_outlined,
              ),
              SectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    StatusPill(label: placeholder.status),
                    const SizedBox(height: 14),
                    Text(
                      placeholder.message,
                      style: const TextStyle(
                        color: AppTheme.muted,
                        fontWeight: FontWeight.w700,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      '可用类型预留：课程总结、课时总结、QA 记录、测验报告、复习计划。',
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
