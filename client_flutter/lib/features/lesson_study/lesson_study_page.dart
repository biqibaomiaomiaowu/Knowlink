import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/models/handout_models.dart';
import '../../shared/models/lesson_study_state.dart';
import '../../shared/providers/lesson_study_provider.dart';

class LessonStudyPage extends ConsumerStatefulWidget {
  const LessonStudyPage({
    required this.courseId,
    required this.lessonId,
    super.key,
  });

  final String courseId;
  final String lessonId;

  @override
  ConsumerState<LessonStudyPage> createState() => _LessonStudyPageState();
}

class _LessonStudyPageState extends ConsumerState<LessonStudyPage> {
  final _questionController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void didUpdateWidget(covariant LessonStudyPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId ||
        oldWidget.lessonId != widget.lessonId) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _load());
    }
  }

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  void _load() {
    if (!mounted) {
      return;
    }
    ref.read(lessonStudyProvider.notifier).load(
          courseId: widget.courseId,
          lessonId: widget.lessonId,
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(lessonStudyProvider);
    return AppScaffold(
      title: '课时学习',
      activeTab: KnowLinkTab.handout,
      courseId: widget.courseId,
      body: _LessonStudyBody(
        courseId: widget.courseId,
        lessonId: widget.lessonId,
        state: state,
        questionController: _questionController,
        onRetry: _load,
      ),
    );
  }
}

class _LessonStudyBody extends ConsumerWidget {
  const _LessonStudyBody({
    required this.courseId,
    required this.lessonId,
    required this.state,
    required this.questionController,
    required this.onRetry,
  });

  final String courseId;
  final String lessonId;
  final LessonStudyState state;
  final TextEditingController questionController;
  final VoidCallback onRetry;
  static const double _closedOutlineIconLeft = -30;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (state.lessonDetail.hasError) {
      return AppErrorView(
        message: '课时学习加载失败：${state.lessonDetail.error}',
        onRetry: onRetry,
      );
    }
    if (state.lessonDetail.isLoading ||
        state.courseId != courseId ||
        state.lessonId != lessonId) {
      return const AppLoadingView(label: '正在加载课时学习');
    }

    final detail = state.lessonDetail.valueOrNull;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        ListView(
          padding: EdgeInsets.zero,
          children: [
            _LessonStudyHeader(
              detail: detail,
              courseId: courseId,
              lessonId: lessonId,
              onOpenMaterials: () => _openMaterials(context, ref),
            ),
            const SizedBox(height: 16),
            _LessonWorkspace(
              state: state,
              questionController: questionController,
            ),
          ],
        ),
        Positioned(
          left: _closedOutlineIconLeft,
          top: 96,
          child: SizedBox(
            width: 78,
            child: Align(
              alignment: Alignment.centerRight,
              child: _OutlineTrigger(
                onPressed: () =>
                    ref.read(lessonStudyProvider.notifier).openOutline(),
              ),
            ),
          ),
        ),
        if (state.isOutlineOpen)
          Positioned(
            key: const Key('lesson_outline_drawer'),
            left: 0,
            top: 150,
            bottom: 16,
            width: 336,
            child: _OutlineDrawer(state: state),
          ),
      ],
    );
  }

  Future<void> _openMaterials(BuildContext context, WidgetRef ref) async {
    ref.read(lessonStudyProvider.notifier).openMaterials();
    await showDialog<void>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.20),
      builder: (context) => BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 9, sigmaY: 9),
        child: _MaterialsDialog(materials: state.materials),
      ),
    );
    if (context.mounted) {
      ref.read(lessonStudyProvider.notifier).closeMaterials();
    }
  }
}

class _LessonStudyHeader extends StatelessWidget {
  const _LessonStudyHeader({
    required this.detail,
    required this.courseId,
    required this.lessonId,
    required this.onOpenMaterials,
  });

  final LessonDetailModel? detail;
  final String courseId;
  final String lessonId;
  final VoidCallback onOpenMaterials;

  @override
  Widget build(BuildContext context) {
    final lesson = detail?.lesson;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: PageTitle(
            title: lesson?.title ?? '课时学习',
            subtitle: '课程 $courseId · 课时 $lessonId',
            icon: Icons.play_circle_outline,
          ),
        ),
        const SizedBox(width: 16),
        Wrap(
          spacing: 10,
          runSpacing: 8,
          alignment: WrapAlignment.end,
          children: [
            OutlinedButton.icon(
              onPressed: onOpenMaterials,
              icon: const Icon(Icons.folder_open_outlined),
              label: const Text('本节资料'),
            ),
            FilledButton.icon(
              onPressed: () => context.go(
                '/courses/$courseId/lessons/$lessonId/quiz',
              ),
              icon: const Icon(Icons.check_box_outlined),
              label: const Text('进入测试'),
            ),
          ],
        ),
      ],
    );
  }
}

class _LessonWorkspace extends StatelessWidget {
  const _LessonWorkspace({
    required this.state,
    required this.questionController,
  });

  final LessonStudyState state;
  final TextEditingController questionController;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 980;
        final videoAndAi = Column(
          children: [
            _VideoPanel(state: state),
            const SizedBox(height: 16),
            _AiPanel(
              state: state,
              questionController: questionController,
            ),
          ],
        );
        final blockPanel = _BlockPanel(state: state);

        if (!wide) {
          return Column(
            children: [
              videoAndAi,
              const SizedBox(height: 16),
              blockPanel,
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: videoAndAi),
            const SizedBox(width: 16),
            SizedBox(width: 396, child: blockPanel),
          ],
        );
      },
    );
  }
}

class _VideoPanel extends StatelessWidget {
  const _VideoPanel({required this.state});

  final LessonStudyState state;

  @override
  Widget build(BuildContext context) {
    final detail = state.lessonDetail.valueOrNull;
    final playback = state.playback.valueOrNull;
    final videoName = detail?.primaryVideo?.originalName ??
        detail?.lesson.primaryVideoResourceId ??
        '暂无主视频';
    final position = detail?.positionSec ?? 0;
    final duration = playback?.durationSec ?? detail?.primaryVideo?.durationSec;

    return SectionCard(
      key: const Key('lesson_study_video_panel'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _PanelTitle(
            icon: Icons.play_circle_outline,
            title: '主视频',
          ),
          const SizedBox(height: 14),
          Container(
            height: 340,
            width: double.infinity,
            decoration: BoxDecoration(
              color: const Color(0xFF0F172A),
              borderRadius: BorderRadius.circular(8),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x221E293B),
                  blurRadius: 24,
                  offset: Offset(0, 12),
                ),
              ],
            ),
            child: Stack(
              children: [
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      gradient: const LinearGradient(
                        colors: [Color(0xFF111827), Color(0xFF1D4ED8)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                    ),
                  ),
                ),
                Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.play_arrow_rounded,
                        color: Colors.white,
                        size: 72,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        videoName,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
                Positioned(
                  left: 24,
                  right: 24,
                  bottom: 22,
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(_formatSeconds(position)),
                          Text(duration == null
                              ? '--:--'
                              : _formatSeconds(duration)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      LinearProgressIndicator(
                        value: duration == null || duration <= 0
                            ? 0
                            : (position / duration).clamp(0, 1),
                        minHeight: 8,
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _BlockPanel extends ConsumerWidget {
  const _BlockPanel({required this.state});

  final LessonStudyState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final block = state.selectedBlock;
    return SectionCard(
      key: const Key('lesson_study_block_panel'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Expanded(
                child: _PanelTitle(
                  icon: Icons.menu_book_outlined,
                  title: '讲义块',
                ),
              ),
              FilledButton(
                onPressed: state.isGeneratingSelectedBlock || block == null
                    ? null
                    : () => ref
                        .read(lessonStudyProvider.notifier)
                        .generateSelectedBlock(),
                child: const Text('生成讲义'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (block == null)
            const Text('当前课时还没有可展示的讲义块。')
          else
            _HandoutBlockView(block: block),
          const SizedBox(height: 12),
          Text(
            state.latestHandout.valueOrNull == null
                ? '等待讲义生成。'
                : '当前讲义基于 ${state.materials.length} 份资料生成。',
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _HandoutBlockView extends StatelessWidget {
  const _HandoutBlockView({required this.block});

  final HandoutBlockModel block;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          block.title,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 12),
        Text(
          block.contentMd?.replaceAll('### ', '') ?? block.summary,
          style: const TextStyle(height: 1.55),
        ),
        if (block.citations.isNotEmpty) ...[
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: block.citations
                .map(
                  (citation) => StatusPill(
                    label: '${citation.refLabel} · ${citation.locatorText}',
                    color: const Color(0xFF64748B),
                  ),
                )
                .toList(),
          ),
        ],
      ],
    );
  }
}

class _AiPanel extends ConsumerWidget {
  const _AiPanel({
    required this.state,
    required this.questionController,
  });

  final LessonStudyState state;
  final TextEditingController questionController;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final messages = state.selectedBlockQaMessages;
    return SectionCard(
      key: const Key('lesson_study_ai_panel'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _PanelTitle(
            icon: Icons.forum_outlined,
            title: 'AI 问答',
          ),
          const SizedBox(height: 12),
          if (messages.isEmpty)
            const _ChatBubble(
              text: '我会基于当前视频、课件和字幕回答。你可以问“循环队列为什么要空一个位置？”',
              isUser: false,
            )
          else
            ...messages.map(
              (message) => _ChatBubble(
                text: message.answerMd,
                isUser: false,
              ),
            ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: questionController,
                  minLines: 1,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    hintText: '问本节 AI：例如 循环队列判满公式怎么记？',
                  ),
                ),
              ),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: state.isSubmittingQuestion
                    ? null
                    : () {
                        final question = questionController.text;
                        questionController.clear();
                        ref
                            .read(lessonStudyProvider.notifier)
                            .askQuestion(question);
                      },
                icon: const Icon(Icons.send_outlined),
                label: const Text('发送'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _OutlineTrigger extends StatelessWidget {
  const _OutlineTrigger({required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 8,
      borderRadius: BorderRadius.circular(8),
      color: Colors.white,
      child: IconButton(
        tooltip: '讲义目录',
        onPressed: onPressed,
        icon: const Icon(Icons.format_list_bulleted, color: AppTheme.brandBlue),
      ),
    );
  }
}

class _OutlineDrawer extends ConsumerWidget {
  const _OutlineDrawer({required this.state});

  final LessonStudyState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outline = state.outline.valueOrNull;
    return Material(
      elevation: 18,
      borderRadius: BorderRadius.circular(8),
      color: Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Expanded(
                  child: _PanelTitle(
                    icon: Icons.schema_outlined,
                    title: '讲义目录',
                  ),
                ),
                IconButton(
                  tooltip: '关闭讲义目录',
                  onPressed: () =>
                      ref.read(lessonStudyProvider.notifier).closeOutline(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: ListView(
                children: [
                  for (final section in outline?.items ?? const [])
                    _OutlineSection(section: section),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OutlineSection extends ConsumerWidget {
  const _OutlineSection({required this.section});

  final HandoutOutlineSectionModel section;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            section.title,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          for (final child in section.children)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(child.title),
              subtitle: Text(_rangeText(child.startSec, child.endSec)),
              onTap: () {
                final block = ref
                    .read(lessonStudyProvider)
                    .blockForId(child.blockId);
                if (block != null) {
                  ref.read(lessonStudyProvider.notifier).selectBlock(block);
                }
                ref.read(lessonStudyProvider.notifier).closeOutline();
              },
            ),
        ],
      ),
    );
  }
}

class _MaterialsDialog extends StatelessWidget {
  const _MaterialsDialog({required this.materials});

  final List<ScopedResourceModel> materials;

  @override
  Widget build(BuildContext context) {
    return Dialog(
      key: const Key('lesson_materials_dialog'),
      insetPadding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 620),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: _PanelTitle(
                      icon: Icons.folder_open_outlined,
                      title: '本节资料',
                    ),
                  ),
                  IconButton(
                    tooltip: '关闭',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              if (materials.isEmpty)
                const Text('暂无本节资料。')
              else
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: materials.length,
                    separatorBuilder: (_, __) => const Divider(height: 20),
                    itemBuilder: (context, index) {
                      final material = materials[index];
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: SoftIcon(
                          icon: _resourceIcon(material.resourceType),
                          size: 44,
                        ),
                        title: Text(material.originalName),
                        subtitle: Text(
                          '${material.resourceType} · ${material.usageRole}',
                        ),
                      );
                    },
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PanelTitle extends StatelessWidget {
  const _PanelTitle({
    required this.icon,
    required this.title,
  });

  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: AppTheme.brandBlue),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
      ],
    );
  }
}

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({
    required this.text,
    required this.isUser,
  });

  final String text;
  final bool isUser;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        constraints: const BoxConstraints(maxWidth: 620),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.brandBlue : const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: isUser ? Colors.white : AppTheme.ink,
            height: 1.45,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

IconData _resourceIcon(String resourceType) {
  return switch (resourceType) {
    'mp4' || 'video' => Icons.movie_outlined,
    'pdf' => Icons.picture_as_pdf_outlined,
    'ppt' || 'pptx' => Icons.slideshow_outlined,
    'srt' => Icons.closed_caption_outlined,
    _ => Icons.insert_drive_file_outlined,
  };
}

String _formatSeconds(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}

String _rangeText(int startSec, int endSec) {
  return '${_formatSeconds(startSec)} - ${_formatSeconds(endSec)}';
}
