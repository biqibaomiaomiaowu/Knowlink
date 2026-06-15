import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/soft_ui_models.dart';
import '../../shared/providers/soft_ui_provider.dart';

class LessonDetailPage extends ConsumerStatefulWidget {
  const LessonDetailPage({
    required this.courseId,
    required this.lessonId,
    super.key,
  });

  final String courseId;
  final String lessonId;

  @override
  ConsumerState<LessonDetailPage> createState() => _LessonDetailPageState();
}

class _LessonDetailPageState extends ConsumerState<LessonDetailPage> {
  final _questionController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref
          .read(softUiProvider.notifier)
          .selectLesson(widget.courseId, widget.lessonId);
    });
  }

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(softUiProvider);
    final lessons = state.lessons[widget.courseId] ?? state.activeCourseLessons;
    final lesson = lessons.firstWhere(
      (item) => item.id == widget.lessonId,
      orElse: () => state.activeLesson,
    );
    return AppScaffold(
      title: '课时学习',
      activeTab: KnowLinkTab.lesson,
      courseId: widget.courseId,
      lessonId: lesson.id,
      body: ListView(
        children: [
          PageTitle(
            title: lesson.title,
            subtitle: '课时学习 · 视频、资料、讲义和本节 AI 问答在同一页完成。',
            icon: Icons.play_circle_outline,
            actions: [
              SoftButton(
                label: '上传本节资料',
                icon: Icons.upload_file_outlined,
                onPressed: () => _pickLessonMaterials(lesson),
              ),
              SoftButton(
                label: '进入测试',
                icon: Icons.fact_check_outlined,
                onPressed: () => context.go('/courses/${lesson.courseId}/test'),
              ),
              SoftButton(
                label: '加入复习',
                icon: Icons.auto_stories_outlined,
                primary: true,
                onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('已加入今日复习')),
                ),
              ),
            ],
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 1050;
              final left = Column(
                children: [
                  _VideoPanel(lesson: lesson),
                  const SizedBox(height: 16),
                  _HandoutPanel(
                    lesson: lesson,
                    onGenerate: () => ref
                        .read(softUiProvider.notifier)
                        .generateHandout(lesson.courseId, lesson.id),
                  ),
                ],
              );
              final right = Column(
                children: [
                  _LessonAiPanel(
                    controller: _questionController,
                    onSend: () {
                      ref.read(softUiProvider.notifier).sendChat(
                            text: _questionController.text,
                            scope: '当前课时',
                          );
                      _questionController.clear();
                    },
                    messages: state.activeChatSession.messages,
                  ),
                  const SizedBox(height: 16),
                  _LessonMaterials(
                    lesson: lesson,
                    onUpload: () => _pickLessonMaterials(lesson),
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

  Future<void> _pickLessonMaterials(SoftLesson lesson) async {
    final files = await openFiles();
    if (!mounted) {
      return;
    }
    if (files.isEmpty) {
      ref.read(softUiProvider.notifier).addLessonMaterial(
            lesson.courseId,
            lesson.id,
            'lesson-extra-material.pdf',
          );
      return;
    }
    for (final file in files) {
      ref
          .read(softUiProvider.notifier)
          .addLessonMaterial(lesson.courseId, lesson.id, file.name);
    }
  }
}

class _VideoPanel extends StatelessWidget {
  const _VideoPanel({required this.lesson});

  final SoftLesson lesson;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('主视频'),
          const SizedBox(height: 12),
          Container(
            height: 300,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(AppTheme.radiusCard),
              boxShadow: AppTheme.insetShadow,
            ),
            child: Stack(
              children: [
                const Positioned(
                  left: 22,
                  top: 18,
                  child: Text(
                    'LECTURE',
                    style: TextStyle(
                      color: AppTheme.muted,
                      fontSize: 11,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 1.4,
                    ),
                  ),
                ),
                Center(
                  child: Container(
                    width: 78,
                    height: 78,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(999),
                      boxShadow: AppTheme.raisedShadow,
                    ),
                    child: const Icon(
                      Icons.play_arrow_rounded,
                      color: AppTheme.accent,
                      size: 44,
                    ),
                  ),
                ),
                Positioned(
                  left: 22,
                  right: 22,
                  bottom: 24,
                  child: ProgressRail(value: lesson.progress),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusPill(label: _formatSeconds(lesson.currentTime)),
              StatusPill(label: '总时长 ${_formatSeconds(lesson.duration)}'),
              StatusPill(label: lesson.status, color: AppTheme.success),
            ],
          ),
        ],
      ),
    );
  }
}

class _LessonAiPanel extends StatelessWidget {
  const _LessonAiPanel({
    required this.controller,
    required this.onSend,
    required this.messages,
  });

  final TextEditingController controller;
  final VoidCallback onSend;
  final List<SoftChatMessage> messages;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('本节 AI 问答'),
          const SizedBox(height: 12),
          Container(
            height: 240,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(24),
              boxShadow: AppTheme.insetShadow,
            ),
            child: ListView(
              children: messages
                  .map(
                    (message) => ChatBubble(
                      role: message.role,
                      content: message.content,
                    ),
                  )
                  .toList(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            minLines: 2,
            maxLines: 3,
            decoration: const InputDecoration(hintText: '问问本节内容...'),
            onSubmitted: (_) => onSend(),
          ),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerRight,
            child: SoftButton(
              label: '发送',
              icon: Icons.send_outlined,
              primary: true,
              onPressed: onSend,
            ),
          ),
        ],
      ),
    );
  }
}

class _LessonMaterials extends StatelessWidget {
  const _LessonMaterials({
    required this.lesson,
    required this.onUpload,
  });

  final SoftLesson lesson;
  final VoidCallback onUpload;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(child: _SectionTitle('本节资料')),
              SoftButton(
                label: '上传',
                icon: Icons.upload_file_outlined,
                onPressed: onUpload,
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (lesson.materials.isEmpty)
            const Text('暂无本节资料。')
          else
            ...lesson.materials.map(
              (material) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: MaterialRow(
                  name: material.name,
                  type: material.type,
                  meta: '本节资料',
                  citationEnabled: material.citationEnabled,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _HandoutPanel extends StatelessWidget {
  const _HandoutPanel({
    required this.lesson,
    required this.onGenerate,
  });

  final SoftLesson lesson;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: _SectionTitle(lesson.handout.title)),
              SoftButton(
                label: '根据资料生成讲义',
                icon: Icons.auto_awesome_outlined,
                primary: true,
                onPressed: onGenerate,
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...lesson.handout.blocks.map(
            (block) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: SectionCard(
                inset: true,
                padding: const EdgeInsets.all(16),
                child: Text(
                  block,
                  style: const TextStyle(
                    color: AppTheme.text,
                    fontWeight: FontWeight.w700,
                    height: 1.5,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ...lesson.handout.citations.map(
                (item) => StatusPill(label: item, color: AppTheme.success),
              ),
              ...lesson.handout.weakHints.map(
                (item) => StatusPill(label: item, color: AppTheme.danger),
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

String _formatSeconds(int seconds) {
  final minutes = (seconds ~/ 60).toString().padLeft(2, '0');
  final rest = (seconds % 60).toString().padLeft(2, '0');
  return '$minutes:$rest';
}
