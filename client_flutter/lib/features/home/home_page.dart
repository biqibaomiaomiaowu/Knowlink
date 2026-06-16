import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/soft_ui_models.dart';
import '../../shared/providers/soft_ui_provider.dart';

class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(softUiProvider);
    final course = state.activeCourse;
    final lessons = state.activeCourseLessons;
    final activeLesson = lessons.isEmpty ? null : lessons.first;

    return AppScaffold(
      title: '学习总览',
      activeTab: KnowLinkTab.home,
      courseId: state.activeCourseId,
      lessonId: state.activeLessonId,
      body: ListView(
        children: [
          _StudyHeader(
            onOpenLibrary: () => context.go('/courses'),
            onCreateCourse: () => _showCourseCreateModal(context, ref),
          ),
          const SizedBox(height: 22),
          _StudyHero(course: course, lesson: activeLesson),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 920;
              final review = _RecommendedReview(
                tasks: state.reviewTasks,
                onReview: () => context.go('/courses/${course.id}/review'),
              );
              final recent = _RecentCourses(courses: state.courses);

              if (!wide) {
                return Column(
                  children: [
                    review,
                    const SizedBox(height: 16),
                    recent,
                  ],
                );
              }

              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 7, child: review),
                  const SizedBox(width: 16),
                  Expanded(flex: 5, child: recent),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _StudyHeader extends StatelessWidget {
  const _StudyHeader({
    required this.onOpenLibrary,
    required this.onCreateCourse,
  });

  final VoidCallback onOpenLibrary;
  final VoidCallback onCreateCourse;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 720;
        final title = Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const SoftIcon(icon: Icons.home_outlined, size: 46),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'KNOWLINK / STUDY CENTER',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.2,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '学习总览',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.displaySmall,
                  ),
                ],
              ),
            ),
          ],
        );
        final actions = Wrap(
          spacing: 10,
          runSpacing: 10,
          alignment: WrapAlignment.end,
          children: [
            SoftButton(
              label: '查看课程库',
              icon: Icons.chevron_right_rounded,
              onPressed: onOpenLibrary,
            ),
            SoftButton(
              label: '新建课程',
              icon: Icons.chevron_right_rounded,
              primary: true,
              onPressed: onCreateCourse,
            ),
          ],
        );

        if (compact) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              title,
              const SizedBox(height: 14),
              actions,
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(child: title),
            const SizedBox(width: 18),
            actions,
          ],
        );
      },
    );
  }
}

class _StudyHero extends StatelessWidget {
  const _StudyHero({
    required this.course,
    required this.lesson,
  });

  final SoftCourse course;
  final SoftLesson? lesson;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(24),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= 820;
          final copy = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const StatusPill(label: '今日学习计划', color: AppTheme.accent),
              const SizedBox(height: 14),
              Text(
                '继续学习「${_shortCourseTitle(course.title)}」第 4 课：栈与队列',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: AppTheme.text,
                  fontSize: 28,
                  fontWeight: FontWeight.w900,
                  height: 1.18,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '系统已根据上次进度、薄弱点和考试时间，安排 45 分钟视频讲义学习、5 分钟测验和 10 分钟错题复盘。',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: AppTheme.muted,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  height: 1.6,
                ),
              ),
              const SizedBox(height: 20),
              SoftButton(
                label: '进入当前课时',
                icon: Icons.chevron_right_rounded,
                primary: true,
                onPressed: () => context.go(
                  '/courses/${course.id}/lessons/${lesson?.id ?? 'lesson-1'}',
                ),
              ),
            ],
          );
          final progress = _HeroProgress(course: course);

          if (!wide) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                copy,
                const SizedBox(height: 16),
                progress,
              ],
            );
          }

          return Row(
            children: [
              Expanded(flex: 7, child: copy),
              const SizedBox(width: 24),
              Expanded(flex: 5, child: progress),
            ],
          );
        },
      ),
    );
  }
}

class _HeroProgress extends StatelessWidget {
  const _HeroProgress({required this.course});

  final SoftCourse course;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      inset: true,
      padding: const EdgeInsets.all(22),
      child: Stack(
        children: [
          const Positioned(
            right: 0,
            top: 0,
            child: SoftIcon(
              icon: Icons.circle,
              color: AppTheme.success,
              size: 74,
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${(course.progress * 100).round()}%',
                style: const TextStyle(
                  color: AppTheme.accent,
                  fontSize: 46,
                  fontWeight: FontWeight.w900,
                  height: 1,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                '课程整体进度',
                style: TextStyle(
                  color: AppTheme.text,
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                '已完成 7 / ${course.lessonCount + 6} 课时',
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              ProgressRail(value: course.progress),
            ],
          ),
        ],
      ),
    );
  }
}

class _RecommendedReview extends StatelessWidget {
  const _RecommendedReview({
    required this.tasks,
    required this.onReview,
  });

  final List<SoftReviewTask> tasks;
  final VoidCallback onReview;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _PanelTitle(
            title: '推荐复习',
            accentColor: AppTheme.success,
          ),
          const SizedBox(height: 12),
          ...tasks.take(3).map(
                (task) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _ReviewTaskRow(
                    task: task,
                    onReview: onReview,
                  ),
                ),
              ),
        ],
      ),
    );
  }
}

class _ReviewTaskRow extends StatelessWidget {
  const _ReviewTaskRow({
    required this.task,
    required this.onReview,
  });

  final SoftReviewTask task;
  final VoidCallback onReview;

  @override
  Widget build(BuildContext context) {
    final color = task.priority == 2 ? AppTheme.success : AppTheme.accent;
    return SectionCard(
      inset: true,
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          _NumberBadge(value: task.priority, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '复习任务：${_compactTaskTitle(task.title)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  '预计 ${task.estimatedMinutes} 分钟 · 薄弱知识点 ${task.weakPoints.length} 个 · 来源第 ${task.priority + 3} 课时',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          SoftButton(
            label: '开始复习',
            icon: Icons.chevron_right_rounded,
            onPressed: onReview,
          ),
        ],
      ),
    );
  }
}

class _NumberBadge extends StatelessWidget {
  const _NumberBadge({
    required this.value,
    required this.color,
  });

  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusControl),
        boxShadow: AppTheme.raisedShadow,
      ),
      child: Text(
        '$value',
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _RecentCourses extends ConsumerWidget {
  const _RecentCourses({required this.courses});

  final List<SoftCourse> courses;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _PanelTitle(
            title: '最近课程',
            accentColor: AppTheme.accentLight,
          ),
          const SizedBox(height: 12),
          ...courses.take(2).map(
                (course) => Padding(
                  padding: const EdgeInsets.only(bottom: 14),
                  child: SectionCard(
                    inset: true,
                    padding: const EdgeInsets.all(16),
                    onTap: () {
                      ref.read(softUiProvider.notifier).selectCourse(course.id);
                      context.go('/courses/${course.id}');
                    },
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          course.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppTheme.text,
                            fontSize: 17,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            StatusPill(
                              label: course.status,
                              color: AppTheme.success,
                            ),
                            StatusPill(label: '${course.lessonCount * 2} 课时'),
                            StatusPill(
                                label:
                                    '${course.materialCount ~/ 2 + 1} 份待整理资料'),
                          ],
                        ),
                        const SizedBox(height: 12),
                        ProgressRail(value: course.progress),
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

class _PanelTitle extends StatelessWidget {
  const _PanelTitle({
    required this.title,
    required this.accentColor,
  });

  final String title;
  final Color accentColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(99),
            boxShadow: AppTheme.raisedShadow,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.text,
              fontSize: 22,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        Container(
          width: 18,
          height: 18,
          decoration: BoxDecoration(
            color: accentColor,
            borderRadius: BorderRadius.circular(99),
            boxShadow: [
              BoxShadow(
                color: accentColor.withValues(alpha: 0.28),
                blurRadius: 12,
                spreadRadius: 2,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

String _shortCourseTitle(String title) {
  return title.replaceAll('期末复习', '').replaceAll('核心概念', '').trim();
}

String _compactTaskTitle(String title) {
  if (title.contains('循环队列')) {
    return '循环队列';
  }
  if (title.contains('二叉树')) {
    return '二叉树遍历';
  }
  if (title.contains('排序')) {
    return '栈的应用';
  }
  return title;
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
            decoration: const InputDecoration(hintText: '例如：操作系统期末复习'),
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
