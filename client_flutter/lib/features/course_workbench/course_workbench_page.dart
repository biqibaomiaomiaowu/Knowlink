import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/soft_ui_models.dart';
import '../../shared/providers/soft_ui_provider.dart';

class CourseWorkbenchPage extends ConsumerStatefulWidget {
  const CourseWorkbenchPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<CourseWorkbenchPage> createState() =>
      _CourseWorkbenchPageState();
}

class _CourseWorkbenchPageState extends ConsumerState<CourseWorkbenchPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(softUiProvider.notifier).selectCourse(widget.courseId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(softUiProvider);
    final course = state.courses.firstWhere(
      (item) => item.id == widget.courseId,
      orElse: () => state.activeCourse,
    );
    final lessons = state.lessons[course.id] ?? const <SoftLesson>[];
    final materials =
        state.courseMaterials[course.id] ?? const <SoftMaterial>[];
    final lessonId = lessons.isEmpty ? state.activeLessonId : lessons.first.id;
    return AppScaffold(
      title: '课程工作区',
      activeTab: KnowLinkTab.workspace,
      courseId: course.id,
      lessonId: lessonId,
      body: ListView(
        children: [
          PageTitle(
            title: course.title,
            subtitle: '课程工作区 · 上传课程资料、管理课时并进入问答。',
            icon: Icons.dashboard_customize_outlined,
            actions: [
              SoftButton(
                label: '上传课程资料',
                icon: Icons.upload_file_outlined,
                onPressed: () => _pickCourseMaterials(course.id),
              ),
              SoftButton(
                label: '新建课时',
                icon: Icons.add_rounded,
                primary: true,
                onPressed: () => _showLessonCreateModal(context, ref, course.id),
              ),
              SoftButton(
                label: '进入 AI 问答',
                icon: Icons.forum_outlined,
                onPressed: () => context.go('/courses/${course.id}/chat'),
              ),
            ],
          ),
          _CourseSummaryCard(course: course),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 980;
              final lessonList = _LessonList(courseId: course.id, lessons: lessons);
              final materialList = _MaterialList(
                materials: materials,
                onUpload: () => _pickCourseMaterials(course.id),
              );
              if (!wide) {
                return Column(
                  children: [
                    lessonList,
                    const SizedBox(height: 16),
                    materialList,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 3, child: lessonList),
                  const SizedBox(width: 16),
                  Expanded(flex: 2, child: materialList),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Future<void> _pickCourseMaterials(String courseId) async {
    final files = await openFiles();
    if (!mounted) {
      return;
    }
    if (files.isEmpty) {
      ref
          .read(softUiProvider.notifier)
          .addCourseMaterial(courseId, 'new-course-material.pdf');
      return;
    }
    for (final file in files) {
      ref.read(softUiProvider.notifier).addCourseMaterial(courseId, file.name);
    }
  }
}

class _CourseSummaryCard extends StatelessWidget {
  const _CourseSummaryCard({required this.course});

  final SoftCourse course;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              MetricCard(
                icon: Icons.timeline_outlined,
                label: '学习进度',
                value: '${(course.progress * 100).round()}%',
                detail: course.status,
              ),
              MetricCard(
                icon: Icons.play_lesson_outlined,
                label: '课时数量',
                value: '${course.lessonCount}',
                color: AppTheme.success,
              ),
              MetricCard(
                icon: Icons.folder_copy_outlined,
                label: '课程资料',
                value: '${course.materialCount}',
                color: AppTheme.accentLight,
              ),
            ],
          ),
          const SizedBox(height: 18),
          ProgressRail(value: course.progress),
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
  final List<SoftLesson> lessons;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('课时列表'),
          const SizedBox(height: 12),
          if (lessons.isEmpty)
            const Text('暂无课时。')
          else
            ...lessons.map(
              (lesson) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: SectionCard(
                  inset: true,
                  padding: const EdgeInsets.all(16),
                  onTap: () =>
                      context.go('/courses/$courseId/lessons/${lesson.id}'),
                  child: Row(
                    children: [
                      const SoftIcon(icon: Icons.play_circle_outline),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              lesson.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: AppTheme.text,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              '${lesson.status} · ${lesson.materials.length} 份资料',
                              style: const TextStyle(
                                color: AppTheme.muted,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 8),
                            ProgressRail(value: lesson.progress),
                          ],
                        ),
                      ),
                      const SizedBox(width: 10),
                      const Icon(Icons.chevron_right_rounded),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MaterialList extends StatelessWidget {
  const _MaterialList({
    required this.materials,
    required this.onUpload,
  });

  final List<SoftMaterial> materials;
  final VoidCallback onUpload;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(child: _SectionTitle('课程资料')),
              SoftButton(
                label: '上传',
                icon: Icons.upload_file_outlined,
                onPressed: onUpload,
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (materials.isEmpty)
            const Text(
              '暂无课程级资料。',
              style: TextStyle(color: AppTheme.muted),
            )
          else
            ...materials.map(
              (material) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: MaterialRow(
                  name: material.name,
                  type: material.type,
                  meta: material.sourceScope == 'course' ? '课程资料' : '课时资料',
                  citationEnabled: material.citationEnabled,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: const TextStyle(
        color: AppTheme.text,
        fontSize: 22,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

Future<void> _showLessonCreateModal(
  BuildContext context,
  WidgetRef ref,
  String courseId,
) async {
  final titleController = TextEditingController();
  final materialController = TextEditingController();
  final formKey = GlobalKey<FormState>();
  final created = await showDialog<bool>(
    context: context,
    builder: (context) {
      return AlertDialog(
        backgroundColor: AppTheme.surface,
        surfaceTintColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(32)),
        title: const Text('新建课时'),
        content: SizedBox(
          width: 460,
          child: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: titleController,
                  decoration: const InputDecoration(hintText: '课时名称'),
                  validator: (value) => value == null || value.trim().isEmpty
                      ? '请输入课时名称'
                      : null,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: materialController,
                  decoration: const InputDecoration(
                    hintText: '资料文件名，可用逗号分隔',
                  ),
                ),
              ],
            ),
          ),
        ),
        actions: [
          SoftButton(
            label: '取消',
            onPressed: () => Navigator.of(context).pop(false),
          ),
          SoftButton(
            label: '创建课时',
            primary: true,
            onPressed: () {
              if (!formKey.currentState!.validate()) {
                return;
              }
              final materialNames = materialController.text
                  .split(RegExp(r'[,，]'))
                  .map((item) => item.trim())
                  .where((item) => item.isNotEmpty)
                  .toList();
              ref.read(softUiProvider.notifier).createLesson(
                    courseId: courseId,
                    title: titleController.text,
                    materialNames: materialNames,
                  );
              Navigator.of(context).pop(true);
            },
          ),
        ],
      );
    },
  );
  titleController.dispose();
  materialController.dispose();
  if (created == true && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('课时已创建')),
    );
  }
}
