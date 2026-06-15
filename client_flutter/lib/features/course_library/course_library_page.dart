import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/soft_ui_models.dart';
import '../../shared/providers/soft_ui_provider.dart';

class CourseLibraryPage extends ConsumerWidget {
  const CourseLibraryPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(softUiProvider);
    return AppScaffold(
      title: '课程库',
      activeTab: KnowLinkTab.library,
      courseId: state.activeCourseId,
      lessonId: state.activeLessonId,
      body: ListView(
        children: [
          PageTitle(
            title: '课程库',
            subtitle: '管理当前课程范围内的课时、资料和学习状态。',
            icon: Icons.library_books_outlined,
            actions: [
              SoftButton(
                label: '新建课程',
                icon: Icons.add_rounded,
                primary: true,
                onPressed: () => _showCourseCreateModal(context, ref),
              ),
            ],
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth >= 1120
                  ? 3
                  : constraints.maxWidth >= 720
                      ? 2
                      : 1;
              return GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: state.courses.length,
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: columns,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 16,
                  childAspectRatio: columns == 1 ? 1.55 : 1.18,
                ),
                itemBuilder: (context, index) {
                  final course = state.courses[index];
                  return _CourseTile(
                    course: course,
                    onContinue: () {
                      ref.read(softUiProvider.notifier).selectCourse(course.id);
                      context.go('/courses/${course.id}');
                    },
                  );
                },
              );
            },
          ),
        ],
      ),
    );
  }
}

class _CourseTile extends StatelessWidget {
  const _CourseTile({
    required this.course,
    required this.onContinue,
  });

  final SoftCourse course;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  course.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    height: 1.12,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              StatusPill(label: course.status, color: AppTheme.success),
            ],
          ),
          const SizedBox(height: 16),
          ProgressRail(value: course.progress),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusPill(label: '${(course.progress * 100).round()}%'),
              StatusPill(label: '${course.lessonCount} 课时'),
              StatusPill(label: '${course.materialCount} 资料'),
            ],
          ),
          const Spacer(),
          Text(
            '上次学习：${_formatDate(course.lastStudiedAt)}',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          Align(
            alignment: Alignment.centerLeft,
            child: SoftButton(
              label: '继续学习',
              icon: Icons.play_arrow_rounded,
              primary: true,
              onPressed: onContinue,
            ),
          ),
        ],
      ),
    );
  }
}

Future<void> _showCourseCreateModal(
  BuildContext context,
  WidgetRef ref,
) async {
  final controller = TextEditingController();
  final formKey = GlobalKey<FormState>();
  final created = await showDialog<SoftCourse>(
    context: context,
    builder: (context) {
      return AlertDialog(
        backgroundColor: AppTheme.surface,
        surfaceTintColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(32)),
        title: const Text('新建课程'),
        content: Form(
          key: formKey,
          child: TextFormField(
            controller: controller,
            decoration: const InputDecoration(hintText: '例如：计算机网络速通'),
            validator: (value) =>
                value == null || value.trim().isEmpty ? '请输入课程名称' : null,
          ),
        ),
        actions: [
          SoftButton(
            label: '取消',
            onPressed: () => Navigator.of(context).pop(),
          ),
          SoftButton(
            label: '创建课程',
            primary: true,
            onPressed: () {
              if (!formKey.currentState!.validate()) {
                return;
              }
              final course = ref
                  .read(softUiProvider.notifier)
                  .createCourse(controller.text);
              Navigator.of(context).pop(course);
            },
          ),
        ],
      );
    },
  );
  controller.dispose();
  if (created != null && context.mounted) {
    context.go('/courses/${created.id}');
  }
}

String _formatDate(DateTime value) {
  return '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')} '
      '${value.hour.toString().padLeft(2, '0')}:'
      '${value.minute.toString().padLeft(2, '0')}';
}
