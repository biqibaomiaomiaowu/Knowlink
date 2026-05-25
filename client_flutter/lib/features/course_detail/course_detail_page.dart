import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_summary.dart';
import '../../shared/providers/course_detail_provider.dart';

class CourseDetailPage extends ConsumerStatefulWidget {
  const CourseDetailPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<CourseDetailPage> createState() => _CourseDetailPageState();
}

class _CourseDetailPageState extends ConsumerState<CourseDetailPage> {
  String? _loadedCourseId;

  @override
  void initState() {
    super.initState();
    _scheduleLoad();
  }

  @override
  void didUpdateWidget(covariant CourseDetailPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleLoad();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(courseDetailProvider);
    final course = state.course.valueOrNull;

    return AppScaffold(
      title: '课程详情',
      activeTab: KnowLinkTab.home,
      courseId: widget.courseId,
      body: course == null && !state.course.hasError
          ? const AppLoadingView(label: '正在加载课程详情')
          : state.course.hasError
              ? AppErrorView(
                  message: '课程详情加载失败：${state.course.error}',
                  onRetry: () => ref
                      .read(courseDetailProvider.notifier)
                      .load(widget.courseId),
                )
              : _CourseDetailBody(
                  course: course!,
                  isCurrent: state.currentCourse.valueOrNull?.courseId ==
                      course.courseId,
                  isSwitching: state.currentCourseSwitch.isLoading,
                  onSwitch: () => ref
                      .read(courseDetailProvider.notifier)
                      .switchCurrentCourse(widget.courseId),
                ),
    );
  }

  void _scheduleLoad() {
    if (_loadedCourseId == widget.courseId) {
      return;
    }
    _loadedCourseId = widget.courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(courseDetailProvider.notifier).load(widget.courseId);
    });
  }
}

class _CourseDetailBody extends StatelessWidget {
  const _CourseDetailBody({
    required this.course,
    required this.isCurrent,
    required this.isSwitching,
    required this.onSwitch,
  });

  final CourseSummaryModel course;
  final bool isCurrent;
  final bool isSwitching;
  final VoidCallback onSwitch;

  @override
  Widget build(BuildContext context) {
    final courseId = course.courseId.toString();

    return ListView(
      children: [
        PageTitle(
          title: course.title,
          subtitle: 'courseId: $courseId',
          icon: Icons.school_outlined,
        ),
        SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  StatusPill(label: course.lifecycleStatus),
                  StatusPill(label: course.pipelineStage),
                  StatusPill(label: course.pipelineStatus),
                  if (isCurrent)
                    const StatusPill(
                      label: '当前课程',
                      color: Color(0xFF16A34A),
                    ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                '入口：${course.entryType}',
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  FilledButton.icon(
                    onPressed: isCurrent || isSwitching ? null : onSwitch,
                    icon: const Icon(Icons.check_circle_outline),
                    label: Text(isSwitching ? '正在切换' : '设为当前课程'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => context.go('/import?courseId=$courseId'),
                    icon: const Icon(Icons.upload_file_outlined),
                    label: const Text('进入导入'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => context.go('/courses/$courseId/progress'),
                    icon: const Icon(Icons.manage_search),
                    label: const Text('进入解析'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => context.go('/courses/$courseId/handout'),
                    icon: const Icon(Icons.menu_book_outlined),
                    label: const Text('进入讲义'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => context.go('/courses/$courseId/quiz'),
                    icon: const Icon(Icons.quiz_outlined),
                    label: const Text('进入测验'),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => context.go('/courses/$courseId/review'),
                    icon: const Icon(Icons.refresh),
                    label: const Text('进入复习'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}
