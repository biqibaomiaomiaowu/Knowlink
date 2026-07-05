import 'dart:async';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:go_router/go_router.dart';

import '../handout/handout_video_controller.dart';
import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/models/handout_models.dart';
import '../../shared/models/lesson_study_state.dart';
import '../../shared/providers/course_flow_providers.dart';
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
    return ListView(
      padding: EdgeInsets.zero,
      children: [
        _LessonStudyHeader(
          detail: detail,
          courseId: courseId,
          lessonId: lessonId,
          onOpenMaterials: () => _openMaterials(context, ref),
        ),
        const SizedBox(height: 22),
        _LessonWorkspace(
          state: state,
          questionController: questionController,
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 760;
        final title = Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                lesson?.title ?? '课时学习',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.displaySmall?.copyWith(
                      fontSize: compact ? 30 : 42,
                      height: 1.02,
                    ),
              ),
            ),
          ],
        );
        final actions = Wrap(
          spacing: 10,
          runSpacing: 10,
          alignment: compact ? WrapAlignment.start : WrapAlignment.end,
          children: [
            _SoftActionButton(
              label: '本节资料',
              icon: Icons.folder_open_outlined,
              onPressed: onOpenMaterials,
            ),
            _SoftActionButton(
              label: '课时测试',
              icon: Icons.check_box_outlined,
              primary: true,
              onPressed: () => context.go(
                '/courses/$courseId/lessons/$lessonId/quiz',
              ),
            ),
          ],
        );

        if (compact) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              title,
              const SizedBox(height: 16),
              actions,
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: title),
            const SizedBox(width: 24),
            actions,
          ],
        );
      },
    );
  }
}

class _SoftActionButton extends StatelessWidget {
  const _SoftActionButton({
    required this.label,
    required this.icon,
    required this.onPressed,
    this.primary = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool primary;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    final foreground = primary ? Colors.white : AppTheme.ink;
    return Opacity(
      opacity: enabled ? 1 : 0.52,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: primary ? AppTheme.brandBlue : AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          boxShadow: primary ? AppTheme.shadowAccent : AppTheme.shadowRaised,
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(16),
          child: InkWell(
            onTap: onPressed,
            borderRadius: BorderRadius.circular(16),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(icon, color: foreground, size: 18),
                  const SizedBox(width: 8),
                  Text(
                    label,
                    style: TextStyle(
                      color: foreground,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _LessonCard extends StatelessWidget {
  const _LessonCard({
    required this.surfaceKey,
    required this.child,
    super.key,
  });

  final Key surfaceKey;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: surfaceKey,
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.all(Radius.circular(32)),
        boxShadow: AppTheme.shadowRaised,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(32),
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: child,
        ),
      ),
    );
  }
}

class _LessonWorkspace extends ConsumerWidget {
  const _LessonWorkspace({
    required this.state,
    required this.questionController,
  });

  final LessonStudyState state;
  final TextEditingController questionController;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 980;
        final player = ref.watch(playerStateProvider);
        final videoPanel = _VideoPanel(state: state, player: player);
        final blockPanel = _BlockPanel(state: state);
        final aiPanel = _AiPanel(
          state: state,
          questionController: questionController,
        );
        final lessonGrid = wide
            ? Column(
                children: [
                  IntrinsicHeight(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(flex: 105, child: videoPanel),
                        const SizedBox(width: 16),
                        Expanded(flex: 95, child: blockPanel),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  aiPanel,
                ],
              )
            : Column(
                children: [
                  videoPanel,
                  const SizedBox(height: 16),
                  blockPanel,
                  const SizedBox(height: 16),
                  aiPanel,
                ],
              );

        return Stack(
          clipBehavior: Clip.none,
          children: [
            lessonGrid,
            Positioned(
              left: -8,
              top: 8,
              child: _OutlineTrigger(
                key: const Key('lesson_outline_trigger'),
                onPressed: () =>
                    ref.read(lessonStudyProvider.notifier).openOutline(),
              ),
            ),
            if (state.isOutlineOpen)
              Positioned(
                key: const Key('lesson_outline_drawer'),
                left: 0,
                top: 116,
                bottom: 16,
                width:
                    (constraints.maxWidth - 32).clamp(280.0, 340.0).toDouble(),
                child: _OutlineDrawer(state: state),
              ),
          ],
        );
      },
    );
  }
}

class _VideoPanel extends ConsumerStatefulWidget {
  const _VideoPanel({required this.state, required this.player});

  final LessonStudyState state;
  final PlayerState player;

  @override
  ConsumerState<_VideoPanel> createState() => _VideoPanelState();
}

class _VideoPanelState extends ConsumerState<_VideoPanel> {
  HandoutVideoController? _controller;
  String? _playbackUrl;
  bool _isInitializing = false;
  Object? _initializationError;
  int? _pendingSeekTargetSec;

  @override
  void initState() {
    super.initState();
    _syncControllerWithPlayback();
  }

  @override
  void didUpdateWidget(covariant _VideoPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncControllerWithPlayback();
    if (oldWidget.player.positionSec != widget.player.positionSec) {
      _requestSeekTo(widget.player.positionSec);
    }
  }

  @override
  void dispose() {
    _disposeController();
    super.dispose();
  }

  void _syncControllerWithPlayback() {
    final nextUrl = widget.state.playback.valueOrNull?.playbackUrl;
    if (nextUrl == _playbackUrl) {
      return;
    }
    _disposeController();
    _playbackUrl = nextUrl;
    _controller = null;
    _isInitializing = false;
    _initializationError = null;
    _pendingSeekTargetSec = null;

    if (nextUrl == null || nextUrl.trim().isEmpty) {
      return;
    }

    final controller = ref.read(handoutVideoControllerFactoryProvider)(
      Uri.parse(nextUrl),
    );
    _controller = controller;
    _isInitializing = true;
    controller.addListener(_handleControllerChanged);
    unawaited(
      controller.initialize().then((_) {
        if (!mounted || _controller != controller) {
          return;
        }
        final positionSec = widget.state.lessonDetail.valueOrNull?.positionSec;
        if (positionSec != null && positionSec > 0) {
          unawaited(controller.seekTo(Duration(seconds: positionSec)));
        }
        _applyPendingSeek();
        setState(() {
          _isInitializing = false;
        });
      }).catchError((Object error) {
        if (!mounted || _controller != controller) {
          return;
        }
        setState(() {
          _isInitializing = false;
          _initializationError = error;
        });
      }),
    );
  }

  void _disposeController() {
    final controller = _controller;
    if (controller == null) {
      return;
    }
    controller.removeListener(_handleControllerChanged);
    unawaited(controller.dispose());
  }

  void _handleControllerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  void _requestSeekTo(int positionSec) {
    _pendingSeekTargetSec = positionSec < 0 ? 0 : positionSec;
    _applyPendingSeek();
  }

  void _applyPendingSeek() {
    final targetSec = _pendingSeekTargetSec;
    final controller = _controller;
    if (targetSec == null || controller == null || !controller.isInitialized) {
      return;
    }
    if ((controller.position.inSeconds - targetSec).abs() <= 1) {
      _pendingSeekTargetSec = null;
      return;
    }
    unawaited(
      controller.seekTo(Duration(seconds: targetSec)).then((_) {
        if (!mounted ||
            _controller != controller ||
            _pendingSeekTargetSec != targetSec) {
          return;
        }
        _pendingSeekTargetSec = null;
        setState(() {});
      }).catchError((Object error) {
        if (!mounted || _controller != controller) {
          return;
        }
        setState(() {
          _pendingSeekTargetSec = null;
          _initializationError = error;
        });
      }),
    );
  }

  void _togglePlay() {
    final controller = _controller;
    if (controller == null || !controller.isInitialized) {
      return;
    }
    final command =
        controller.isPlaying ? controller.pause() : controller.play();
    unawaited(command);
  }

  @override
  Widget build(BuildContext context) {
    final detail = widget.state.lessonDetail.valueOrNull;
    final playback = widget.state.playback.valueOrNull;
    final videoName = detail?.primaryVideo?.originalName ??
        detail?.lesson.primaryVideoResourceId ??
        '暂无主视频';
    final controller = _controller;
    final position = controller?.isInitialized == true
        ? controller!.position.inSeconds
        : detail?.positionSec ?? 0;
    final controllerDuration =
        controller?.isInitialized == true ? controller!.duration.inSeconds : 0;
    final duration = controllerDuration > 0
        ? controllerDuration
        : playback?.durationSec ?? detail?.primaryVideo?.durationSec;
    final videoHeight =
        (MediaQuery.sizeOf(context).width * 0.36).clamp(320.0, 460.0);

    return _LessonCard(
      key: const Key('lesson_study_video_panel'),
      surfaceKey: const Key('lesson_video_card_surface'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _PanelTitle(
            icon: Icons.play_circle_outline,
            title: '主视频',
          ),
          const SizedBox(height: 14),
          Semantics(
            label: videoName.toString(),
            child: Container(
              key: const Key('lesson_video_surface'),
              height: videoHeight,
              width: double.infinity,
              clipBehavior: Clip.antiAlias,
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(32),
                boxShadow: AppTheme.shadowInsetLook,
              ),
              child: Stack(
                children: [
                  Positioned.fill(
                    child: _buildVideoSurface(),
                  ),
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            AppTheme.ink.withValues(alpha: 0.10),
                            Colors.transparent,
                            AppTheme.ink.withValues(alpha: 0.30),
                          ],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: const [0, 0.34, 1],
                        ),
                      ),
                    ),
                  ),
                  const Positioned(
                    left: 24,
                    top: 20,
                    child: Text(
                      'LECTURE',
                      style: TextStyle(
                        color: AppTheme.muted,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.54,
                      ),
                    ),
                  ),
                  Center(
                    child: Material(
                      color: Colors.transparent,
                      shape: const CircleBorder(),
                      child: InkWell(
                        onTap: controller?.isInitialized == true
                            ? _togglePlay
                            : null,
                        customBorder: const CircleBorder(),
                        child: Container(
                          width: 78,
                          height: 78,
                          decoration: const BoxDecoration(
                            color: AppTheme.surface,
                            shape: BoxShape.circle,
                            boxShadow: AppTheme.shadowRaised,
                          ),
                          child: Icon(
                            controller?.isPlaying == true
                                ? Icons.pause_rounded
                                : Icons.play_arrow_rounded,
                            color: AppTheme.brandBlue,
                            size: 42,
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    left: 22,
                    right: 22,
                    bottom: 24,
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              _formatSeconds(position),
                              style: const TextStyle(
                                color: AppTheme.muted,
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            Text(
                              duration == null
                                  ? '--:--'
                                  : _formatSeconds(duration),
                              style: const TextStyle(
                                color: AppTheme.muted,
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _SoftProgressBar(
                          value: duration == null || duration <= 0
                              ? 0
                              : (position / duration).clamp(0, 1),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoSurface() {
    final controller = _controller;
    if (widget.state.playback.hasError || _initializationError != null) {
      return _buildVideoPlaceholder();
    }
    if (widget.state.playback.valueOrNull == null ||
        _isInitializing ||
        controller == null ||
        !controller.isInitialized) {
      return _buildVideoPlaceholder();
    }
    final aspectRatio =
        controller.aspectRatio <= 0 ? 16 / 9 : controller.aspectRatio;
    return ColoredBox(
      key: const Key('lesson_video_player'),
      color: Colors.black,
      child: Center(
        child: AspectRatio(
          aspectRatio: aspectRatio,
          child: controller.buildPlayer(),
        ),
      ),
    );
  }

  Widget _buildVideoPlaceholder() {
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(32),
        gradient: const LinearGradient(
          colors: [
            Color(0xFFE9EEF5),
            Color(0xFFD5DCE7),
            Color(0xFFB9C5D7),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
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
    return _LessonCard(
      key: const Key('lesson_study_block_panel'),
      surfaceKey: const Key('lesson_handout_card_surface'),
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
              _SoftActionButton(
                label: state.isGeneratingSelectedBlock ? '正在生成' : '生成讲义',
                icon: Icons.auto_awesome_outlined,
                onPressed: state.isGeneratingSelectedBlock || block == null
                    ? null
                    : () => ref
                        .read(lessonStudyProvider.notifier)
                        .generateSelectedBlock(),
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
              fontSize: 12,
              fontWeight: FontWeight.w600,
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
    final content = block.contentMd;
    return Container(
      key: const Key('lesson_handout_surface'),
      constraints: const BoxConstraints(minHeight: 360),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(24),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            block.title,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          if (content == null || content.trim().isEmpty)
            Text(
              block.summary.isEmpty ? '该讲义块暂无正文。' : block.summary,
              style: const TextStyle(height: 1.55),
            )
          else
            MarkdownBody(
              data: content,
              selectable: true,
              styleSheet: _lessonHandoutMarkdownStyleSheet(context),
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
      ),
    );
  }
}

MarkdownStyleSheet _lessonHandoutMarkdownStyleSheet(BuildContext context) {
  final theme = Theme.of(context);
  return MarkdownStyleSheet.fromTheme(theme).copyWith(
    p: const TextStyle(
      color: AppTheme.ink,
      height: 1.55,
      fontSize: 14,
      fontWeight: FontWeight.w500,
    ),
    h1: theme.textTheme.titleLarge?.copyWith(
      color: AppTheme.ink,
      fontWeight: FontWeight.w900,
    ),
    h2: theme.textTheme.titleMedium?.copyWith(
      color: AppTheme.ink,
      fontWeight: FontWeight.w900,
    ),
    h3: theme.textTheme.titleSmall?.copyWith(
      color: AppTheme.ink,
      fontWeight: FontWeight.w900,
    ),
    listBullet: const TextStyle(
      color: AppTheme.ink,
      height: 1.45,
      fontWeight: FontWeight.w700,
    ),
    code: const TextStyle(
      color: AppTheme.ink,
      backgroundColor: Color(0xFFEFF3F8),
      fontSize: 13,
      height: 1.45,
    ),
    codeblockDecoration: BoxDecoration(
      color: const Color(0xFFEFF3F8),
      borderRadius: BorderRadius.circular(14),
    ),
  );
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
    return _LessonCard(
      key: const Key('lesson_study_ai_panel'),
      surfaceKey: const Key('lesson_ai_card_surface'),
      child: Container(
        key: const Key('lesson_ai_panel_surface'),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(24),
          boxShadow: AppTheme.shadowInsetLook,
        ),
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
                surfaceKey: Key('lesson_ai_bubble_ai_surface'),
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
                  child: Container(
                    key: const Key('lesson_ai_input_surface'),
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: AppTheme.shadowInsetLook,
                    ),
                    child: TextField(
                      controller: questionController,
                      minLines: 1,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        hintText: '问本节 AI：例如 循环队列判满公式怎么记？',
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        filled: false,
                        contentPadding: EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                _SoftActionButton(
                  label: '发送',
                  icon: Icons.send_outlined,
                  primary: true,
                  onPressed: state.isSubmittingQuestion
                      ? null
                      : () {
                          final question = questionController.text;
                          questionController.clear();
                          ref
                              .read(lessonStudyProvider.notifier)
                              .askQuestion(question);
                        },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _OutlineTrigger extends StatelessWidget {
  const _OutlineTrigger({required this.onPressed, super.key});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return _SoftIconButton(
      tooltip: '讲义目录',
      icon: Icons.format_list_bulleted,
      onPressed: onPressed,
      size: 46,
      radius: 18,
    );
  }
}

class _OutlineDrawer extends ConsumerWidget {
  const _OutlineDrawer({required this.state});

  final LessonStudyState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final outline = state.outline.valueOrNull;
    return Container(
      key: const Key('lesson_outline_drawer_surface'),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.only(
          topRight: Radius.circular(32),
          bottomRight: Radius.circular(32),
        ),
        boxShadow: AppTheme.shadowRaised,
      ),
      child: ClipRRect(
        borderRadius: const BorderRadius.only(
          topRight: Radius.circular(32),
          bottomRight: Radius.circular(32),
        ),
        child: Material(
          color: Colors.transparent,
          child: Padding(
            padding: const EdgeInsets.all(22),
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
                    _SoftIconButton(
                      tooltip: '关闭讲义目录',
                      icon: Icons.close,
                      onPressed: () =>
                          ref.read(lessonStudyProvider.notifier).closeOutline(),
                      size: 42,
                      radius: 16,
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
    final children = section.children;
    final selectedBlockId = ref.watch(lessonStudyProvider).selectedBlockId;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(22),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _OutlineParentTitle(title: section.title),
          Padding(
            padding: const EdgeInsets.only(left: 24),
            child: Column(
              children: [
                for (final child in children)
                  Padding(
                    padding: EdgeInsets.only(
                      top: child == children.first ? 0 : 8,
                    ),
                    child: _OutlineChildButton(
                      child: child,
                      isActive: child.blockId == selectedBlockId ||
                          (selectedBlockId == null && child == children.first),
                      onTap: () {
                        final block = ref
                            .read(lessonStudyProvider)
                            .blockForId(child.blockId);
                        if (block != null) {
                          ref
                              .read(lessonStudyProvider.notifier)
                              .selectBlock(block);
                        }
                        final player = ref.read(playerStateProvider);
                        ref.read(playerStateProvider.notifier).state =
                            player.copyWith(positionSec: child.startSec);
                        ref.read(lessonStudyProvider.notifier).closeOutline();
                      },
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

class _OutlineParentTitle extends StatelessWidget {
  const _OutlineParentTitle({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final parts = _splitOutlineTitle(title);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          if (parts.prefix.isNotEmpty) ...[
            Text(
              parts.prefix,
              style: const TextStyle(
                color: AppTheme.brandBlue,
                fontSize: 14,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: Text(
              parts.text,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 16,
                fontWeight: FontWeight.w900,
                height: 1.2,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OutlineChildButton extends StatelessWidget {
  const _OutlineChildButton({
    required this.child,
    required this.isActive,
    required this.onTap,
  });

  final HandoutOutlineChildModel child;
  final bool isActive;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final parts = _splitOutlineTitle(child.title);
    final foreground = isActive ? Colors.white : AppTheme.ink;
    final subtle =
        isActive ? Colors.white.withValues(alpha: 0.86) : AppTheme.muted;
    return Container(
      key: Key('lesson_outline_child_${child.blockId}'),
      width: double.infinity,
      decoration: BoxDecoration(
        color: isActive ? AppTheme.brandBlue : AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: isActive ? AppTheme.shadowAccent : AppTheme.shadowSmall,
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  parts.prefix.isEmpty ? '-' : parts.prefix,
                  style: TextStyle(
                    color: subtle,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    height: 1.25,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        parts.text,
                        overflow: TextOverflow.visible,
                        style: TextStyle(
                          color: foreground,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          height: 1.35,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        _rangeText(child.startSec, child.endSec),
                        style: TextStyle(
                          color: subtle,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          height: 1.35,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
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
      elevation: 0,
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      insetPadding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: Container(
          key: const Key('lesson_materials_dialog_surface'),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(32),
            boxShadow: AppTheme.shadowRaised,
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(32),
            child: Material(
              color: Colors.transparent,
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
                        _SoftIconButton(
                          tooltip: '关闭',
                          icon: Icons.close,
                          onPressed: () => Navigator.of(context).pop(),
                          size: 42,
                          radius: 16,
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
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 12),
                          itemBuilder: (context, index) {
                            final material = materials[index];
                            return Container(
                              key: Key(
                                  'lesson_material_row_${material.resourceId}'),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 11,
                              ),
                              decoration: BoxDecoration(
                                color: AppTheme.surface,
                                borderRadius: BorderRadius.circular(18),
                                boxShadow: AppTheme.shadowInsetLook,
                              ),
                              child: _MaterialRowContent(
                                contentPadding: EdgeInsets.zero,
                                leading: _FileBadge(
                                  resourceType: material.resourceType,
                                ),
                                title: Text(material.originalName),
                                subtitle: Text(
                                  '${material.resourceType} · ${material.usageRole}',
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _MaterialRowContent extends StatelessWidget {
  const _MaterialRowContent({
    required this.contentPadding,
    required this.leading,
    required this.title,
    required this.subtitle,
  });

  final EdgeInsetsGeometry contentPadding;
  final Widget leading;
  final Widget title;
  final Widget subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: contentPadding,
      child: Row(
        children: [
          leading,
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                DefaultTextStyle.merge(
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w700,
                  ),
                  child: title,
                ),
                const SizedBox(height: 4),
                DefaultTextStyle.merge(
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                  child: subtitle,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FileBadge extends StatelessWidget {
  const _FileBadge({required this.resourceType});

  final String resourceType;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        boxShadow: AppTheme.shadowRaised,
      ),
      child: Text(
        _fileBadgeLabel(resourceType),
        style: TextStyle(
          color: _fileBadgeColor(resourceType),
          fontSize: 11,
          fontWeight: FontWeight.w800,
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
        Container(
          width: 40,
          height: 40,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppTheme.surface,
            borderRadius: BorderRadius.circular(20),
            boxShadow: AppTheme.shadowInsetLook,
          ),
          child: Icon(icon, color: AppTheme.brandBlue, size: 20),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 22,
              fontWeight: FontWeight.w800,
              height: 1.1,
              letterSpacing: 0,
            ),
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
    this.surfaceKey,
  });

  final String text;
  final bool isUser;
  final Key? surfaceKey;

  @override
  Widget build(BuildContext context) {
    final bubbleRadius = BorderRadius.only(
      topLeft: Radius.circular(isUser ? 20 : 8),
      topRight: Radius.circular(isUser ? 8 : 20),
      bottomLeft: const Radius.circular(20),
      bottomRight: const Radius.circular(20),
    );
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        key: surfaceKey,
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
        constraints: const BoxConstraints(maxWidth: 620),
        decoration: BoxDecoration(
          color: isUser ? AppTheme.brandBlue : AppTheme.surface,
          borderRadius: bubbleRadius,
          boxShadow: isUser ? AppTheme.shadowAccent : AppTheme.shadowSmall,
        ),
        child: Text(
          text,
          style: TextStyle(
            color: isUser ? Colors.white : AppTheme.ink,
            fontSize: 13,
            height: 1.45,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class _SoftIconButton extends StatelessWidget {
  const _SoftIconButton({
    required this.tooltip,
    required this.icon,
    required this.onPressed,
    this.size = 46,
    this.radius = 16,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;
  final double size;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Opacity(
      opacity: enabled ? 1 : 0.52,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(radius),
          boxShadow: AppTheme.shadowRaised,
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(radius),
          child: Tooltip(
            message: tooltip,
            child: InkWell(
              onTap: onPressed,
              borderRadius: BorderRadius.circular(radius),
              child: SizedBox(
                width: size,
                height: size,
                child: Icon(
                  icon,
                  color: AppTheme.brandBlue,
                  size: size * 0.45,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SoftProgressBar extends StatelessWidget {
  const _SoftProgressBar({required this.value});

  final num value;

  @override
  Widget build(BuildContext context) {
    final progress = value.clamp(0, 1).toDouble();
    return Container(
      key: const Key('lesson_video_progress_bar'),
      height: 12,
      padding: const EdgeInsets.all(3),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(999),
        boxShadow: AppTheme.shadowInsetLook,
      ),
      child: Align(
        alignment: Alignment.centerLeft,
        child: FractionallySizedBox(
          widthFactor: progress,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              gradient: const LinearGradient(
                colors: [AppTheme.brandBlue, AppTheme.success],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

String _fileBadgeLabel(String resourceType) {
  final normalized = resourceType.trim().toUpperCase();
  if (normalized.isEmpty) {
    return 'FILE';
  }
  if (normalized == 'VIDEO') {
    return 'MP4';
  }
  return normalized.length <= 4 ? normalized : normalized.substring(0, 4);
}

Color _fileBadgeColor(String resourceType) {
  return switch (resourceType.toLowerCase()) {
    'pdf' => AppTheme.danger,
    'srt' || 'doc' || 'docx' => AppTheme.success,
    'mp4' || 'video' || 'ppt' || 'pptx' => AppTheme.brandBlue,
    _ => AppTheme.brandBlue,
  };
}

class _OutlineTitleParts {
  const _OutlineTitleParts(this.prefix, this.text);

  final String prefix;
  final String text;
}

_OutlineTitleParts _splitOutlineTitle(String title) {
  final trimmed = title.trim();
  final match = RegExp(r'^(\d+(?:\.\d+)*)(?:\s+(.+))?$').firstMatch(trimmed);
  if (match == null) {
    return _OutlineTitleParts('', trimmed);
  }
  return _OutlineTitleParts(match.group(1) ?? '', match.group(2) ?? trimmed);
}

String _formatSeconds(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}

String _rangeText(int startSec, int endSec) {
  return '${_formatSeconds(startSec)} - ${_formatSeconds(endSec)}';
}
