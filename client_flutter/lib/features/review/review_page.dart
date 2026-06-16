import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/providers/soft_ui_provider.dart';

class ReviewPage extends ConsumerWidget {
  const ReviewPage({
    this.courseId,
    super.key,
  });

  final String? courseId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(softUiProvider);
    final activeCourseId = courseId ?? state.activeCourseId;
    return AppScaffold(
      title: '复习中心',
      activeTab: KnowLinkTab.review,
      courseId: activeCourseId,
      lessonId: state.activeLessonId,
      body: ListView(
        children: [
          PageTitle(
            title: '复习中心',
            subtitle: '围绕今日复习、薄弱点、错题和掌握度组织复盘路径。',
            icon: Icons.auto_stories_outlined,
            actions: [
              SoftButton(
                label: '生成今日复习',
                icon: Icons.refresh_rounded,
                primary: true,
                onPressed: () {
                  ref.read(softUiProvider.notifier).regenerateReview();
                  _snack(context, '今日复习已生成');
                },
              ),
            ],
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 1080;
              final left = Column(
                children: [
                  _TodayReview(tasks: state.reviewTasks),
                  const SizedBox(height: 16),
                  _WeakPointGrid(),
                ],
              );
              final right = Column(
                children: [
                  _MasteryCard(),
                  const SizedBox(height: 16),
                  _ReviewPath(),
                  const SizedBox(height: 16),
                  _ExportPanel(
                    onExport: (name) {
                      ref.read(softUiProvider.notifier).export(name);
                      _snack(context, '$name 已加入导出任务');
                    },
                  ),
                ],
              );
              if (!wide) {
                return Column(
                  children: [
                    left,
                    const SizedBox(height: 16),
                    right,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 11, child: left),
                  const SizedBox(width: 16),
                  Expanded(flex: 9, child: right),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _TodayReview extends StatelessWidget {
  const _TodayReview({required this.tasks});

  final List<dynamic> tasks;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('今日复习'),
          const SizedBox(height: 12),
          ...tasks.map(
            (task) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ReviewTaskCard(
                priority: task.priority as int,
                title: task.title as String,
                sourceLesson: task.sourceLesson as String,
                weakPoints: List<String>.from(task.weakPoints as List),
                estimatedMinutes: task.estimatedMinutes as int,
                reason: task.reason as String,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WeakPointGrid extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const items = [
      ('循环队列边界', '错题 3 次 · 掌握 46%', 0.46),
      ('递归调用栈', '错题 2 次 · 掌握 58%', 0.58),
      ('排序稳定性', '错题 1 次 · 掌握 64%', 0.64),
      ('树的层序遍历', '错题 2 次 · 掌握 52%', 0.52),
    ];
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('薄弱点'),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth >= 720 ? 2 : 1;
              return GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: items.length,
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: columns,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  childAspectRatio: columns == 1 ? 2.8 : 2.2,
                ),
                itemBuilder: (context, index) {
                  final item = items[index];
                  return SectionCard(
                    inset: true,
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        StatusPill(
                          label: index == 0 ? '优先' : '复习',
                          color: index == 0 ? AppTheme.danger : AppTheme.accent,
                        ),
                        const SizedBox(height: 10),
                        Text(
                          item.$1,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppTheme.text,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          item.$2,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppTheme.muted,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const Spacer(),
                        ProgressRail(value: item.$3),
                      ],
                    ),
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

class _MasteryCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('掌握度'),
          const SizedBox(height: 14),
          const Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              MetricCard(
                icon: Icons.psychology_alt_outlined,
                label: '综合掌握',
                value: '72%',
                detail: '较昨日 +4%',
              ),
              MetricCard(
                icon: Icons.error_outline,
                label: '错题',
                value: '9',
                detail: '3 道高频',
                color: AppTheme.danger,
              ),
            ],
          ),
          const SizedBox(height: 16),
          const _SectionTitle('薄弱知识图谱'),
          const SizedBox(height: 12),
          Container(
            height: 180,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(24),
              boxShadow: AppTheme.insetShadow,
            ),
            child: const Wrap(
              alignment: WrapAlignment.center,
              spacing: 10,
              runSpacing: 10,
              children: [
                StatusPill(label: '循环队列', color: AppTheme.danger),
                StatusPill(label: '栈'),
                StatusPill(label: '递归'),
                StatusPill(label: '二叉树'),
                StatusPill(label: '排序复杂度', color: AppTheme.success),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ReviewPath extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const steps = [
      ('1. 快速回看讲义', '栈与队列专项复习 · 8 分钟'),
      ('2. 做 5 道针对题', '覆盖队满判断、长度计算和出入队模拟'),
      ('3. 复盘错题', '自动生成改错说明'),
      ('4. 阶段测验', '预计 25 分钟'),
    ];
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('今日复习路径'),
          const SizedBox(height: 12),
          ...steps.map(
            (step) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: SectionCard(
                inset: true,
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      step.$1,
                      style: const TextStyle(
                        color: AppTheme.text,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      step.$2,
                      style: const TextStyle(
                        color: AppTheme.muted,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
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

class _ExportPanel extends StatelessWidget {
  const _ExportPanel({required this.onExport});

  final ValueChanged<String> onExport;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('导出与报告'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              SoftButton(
                label: '导出复习计划',
                icon: Icons.download_outlined,
                onPressed: () => onExport('复习计划'),
              ),
              SoftButton(
                label: '导出错题本',
                icon: Icons.download_outlined,
                onPressed: () => onExport('错题本'),
              ),
              SoftButton(
                label: '导出讲义',
                icon: Icons.download_outlined,
                onPressed: () => onExport('讲义'),
              ),
              SoftButton(
                label: '生成学习报告',
                icon: Icons.assessment_outlined,
                primary: true,
                onPressed: () => onExport('学习报告'),
              ),
            ],
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

void _snack(BuildContext context, String text) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
}
