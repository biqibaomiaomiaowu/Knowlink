import 'package:flutter/material.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';

class CourseGraphPage extends StatelessWidget {
  const CourseGraphPage({
    required this.courseId,
    this.lessonId,
    this.kind = CourseGraphPageKind.graph,
    super.key,
  });

  final String courseId;
  final String? lessonId;
  final CourseGraphPageKind kind;

  @override
  Widget build(BuildContext context) {
    final title = switch (kind) {
      CourseGraphPageKind.settings => '课程设置',
      CourseGraphPageKind.graph => lessonId == null ? '课程图谱' : '课时图谱',
    };
    final message = switch (kind) {
      CourseGraphPageKind.settings => '课程设置入口已预留，当前版本先保持只读状态。',
      CourseGraphPageKind.graph => '知识图谱生成暂未启用，后续会接入图谱 read model。',
    };
    return AppScaffold(
      title: title,
      activeTab: KnowLinkTab.home,
      courseId: courseId,
      body: _PlaceholderBody(
        title: title,
        scope: lessonId == null ? 'course:$courseId' : 'lesson:$lessonId',
        status: kind == CourseGraphPageKind.graph ? 'placeholder' : 'ready',
        message: message,
        icon: kind == CourseGraphPageKind.graph
            ? Icons.hub_outlined
            : Icons.settings_outlined,
      ),
    );
  }
}

enum CourseGraphPageKind { graph, settings }

class _PlaceholderBody extends StatelessWidget {
  const _PlaceholderBody({
    required this.title,
    required this.scope,
    required this.status,
    required this.message,
    required this.icon,
  });

  final String title;
  final String scope;
  final String status;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        PageTitle(title: title, subtitle: scope, icon: icon),
        SectionCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              StatusPill(label: status),
              const SizedBox(height: 14),
              Text(
                message,
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w700,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 16),
              const Text('空状态稳定展示，不触发未支持的生成任务。'),
            ],
          ),
        ),
      ],
    );
  }
}
