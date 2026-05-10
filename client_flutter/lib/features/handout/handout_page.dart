import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'handout_video_controller.dart';
import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/handout_models.dart';
import '../../shared/models/handout_state.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/handout_provider.dart';

class HandoutPage extends ConsumerStatefulWidget {
  const HandoutPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  ConsumerState<HandoutPage> createState() => _HandoutPageState();
}

class _HandoutPageState extends ConsumerState<HandoutPage> {
  final _questionController = TextEditingController();
  String? _lastCourseId;

  @override
  void initState() {
    super.initState();
    _questionController.addListener(_onQuestionChanged);
    _scheduleLoad();
  }

  @override
  void didUpdateWidget(covariant HandoutPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleLoad();
    }
  }

  @override
  void dispose() {
    _questionController.removeListener(_onQuestionChanged);
    _questionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(handoutProvider);
    final player = ref.watch(playerStateProvider);
    final notifier = ref.read(handoutProvider.notifier);
    final highlighted = state.highlightedChildFor(player.positionSec);
    final selectedChild = state.selectedOutlineChild;
    final selectedBlock = state.selectedBlock;

    return AppScaffold(
      title: '个性化互动讲义',
      activeTab: KnowLinkTab.handout,
      courseId: widget.courseId,
      body: _HandoutWorkspace(
        courseId: widget.courseId,
        state: state,
        player: player,
        highlightedChild: highlighted,
        selectedBlockId: selectedChild?.blockId,
        selectedBlock: selectedBlock,
        questionController: _questionController,
        onTogglePlay: () {
          ref.read(playerStateProvider.notifier).state = player.copyWith(
            isPlaying: !player.isPlaying,
          );
        },
        onSeek: (delta) {
          final next =
              (player.positionSec + delta).clamp(0, 24 * 60 * 60).toInt();
          ref.read(playerStateProvider.notifier).state = player.copyWith(
            positionSec: next,
          );
          notifier.syncHighlightedBlock(next);
          notifier.syncCurrentBlockFromPosition(
            courseId: widget.courseId,
            positionSec: next,
          );
        },
        onSelectChild: notifier.selectOutlineChild,
        onRefresh: () => notifier.refreshData(widget.courseId),
        onGenerate: () => notifier.generateAndPoll(widget.courseId),
        onGenerateBlock: selectedChild == null
            ? null
            : () => notifier.generateBlock(
                  selectedChild.blockId,
                  courseId: widget.courseId,
                ),
        onRetryPlayback: notifier.retryPlayback,
        onCitationTap: selectedChild == null
            ? null
            : (citation) => notifier.requestJumpTarget(
                  selectedChild.blockId,
                  citation: citation,
                ),
        onSubmitQuestion: () async {
          final text = _questionController.text;
          await notifier.submitQuestion(
            courseId: widget.courseId,
            question: text,
          );
          if (mounted &&
              ref.read(handoutProvider).qaSubmit.valueOrNull != null) {
            _questionController.clear();
          }
        },
      ),
    );
  }

  void _scheduleLoad() {
    if (_lastCourseId == widget.courseId) {
      return;
    }
    _lastCourseId = widget.courseId;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(handoutProvider.notifier).load(widget.courseId);
    });
  }

  void _onQuestionChanged() {
    if (mounted) {
      setState(() {});
    }
  }
}

class _HandoutWorkspace extends StatelessWidget {
  const _HandoutWorkspace({
    required this.courseId,
    required this.state,
    required this.player,
    required this.highlightedChild,
    required this.selectedBlockId,
    required this.selectedBlock,
    required this.questionController,
    required this.onTogglePlay,
    required this.onSeek,
    required this.onSelectChild,
    required this.onRefresh,
    required this.onGenerate,
    required this.onGenerateBlock,
    required this.onRetryPlayback,
    required this.onCitationTap,
    required this.onSubmitQuestion,
  });

  final String courseId;
  final HandoutState state;
  final PlayerState player;
  final HandoutOutlineChildModel? highlightedChild;
  final int? selectedBlockId;
  final HandoutBlockModel? selectedBlock;
  final TextEditingController questionController;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;
  final ValueChanged<HandoutOutlineChildModel> onSelectChild;
  final VoidCallback onRefresh;
  final VoidCallback onGenerate;
  final VoidCallback? onGenerateBlock;
  final VoidCallback onRetryPlayback;
  final ValueChanged<CitationModel>? onCitationTap;
  final VoidCallback onSubmitQuestion;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < 1120) {
          return ListView(
            key: const Key('handout_stacked_workspace'),
            children: [
              _OutlinePanel(
                state: state,
                highlightedBlockId: highlightedChild?.blockId,
                selectedBlockId: selectedBlockId,
                onSelect: onSelectChild,
                onRefresh: onRefresh,
                onGenerate: onGenerate,
              ),
              const SizedBox(height: 16),
              _LearningCenterPanel(
                courseId: courseId,
                state: state,
                player: player,
                highlightedChild: highlightedChild,
                selectedBlock: selectedBlock,
                onTogglePlay: onTogglePlay,
                onSeek: onSeek,
                onGenerateBlock: onGenerateBlock,
                onRetryPlayback: onRetryPlayback,
                onCitationTap: onCitationTap,
              ),
              const SizedBox(height: 16),
              _RightStudyPanel(
                state: state,
                selectedBlock: selectedBlock,
                controller: questionController,
                onCitationTap: onCitationTap,
                onSubmit: onSubmitQuestion,
              ),
            ],
          );
        }

        return Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SizedBox(
              width: 294,
              child: _OutlinePanel(
                state: state,
                highlightedBlockId: highlightedChild?.blockId,
                selectedBlockId: selectedBlockId,
                onSelect: onSelectChild,
                onRefresh: onRefresh,
                onGenerate: onGenerate,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _LearningCenterPanel(
                courseId: courseId,
                state: state,
                player: player,
                highlightedChild: highlightedChild,
                selectedBlock: selectedBlock,
                onTogglePlay: onTogglePlay,
                onSeek: onSeek,
                onGenerateBlock: onGenerateBlock,
                onRetryPlayback: onRetryPlayback,
                onCitationTap: onCitationTap,
              ),
            ),
            const SizedBox(width: 16),
            SizedBox(
              width: 352,
              child: _RightStudyPanel(
                state: state,
                selectedBlock: selectedBlock,
                controller: questionController,
                onCitationTap: onCitationTap,
                onSubmit: onSubmitQuestion,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _OutlinePanel extends StatelessWidget {
  const _OutlinePanel({
    required this.state,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
    required this.onRefresh,
    required this.onGenerate,
  });

  final HandoutState state;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutOutlineChildModel> onSelect;
  final VoidCallback onRefresh;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    final outline = state.outline.valueOrNull;
    final blockList = Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: _BlockList(
        state: state,
        outline: outline,
        highlightedBlockId: highlightedBlockId,
        selectedBlockId: selectedBlockId,
        onSelect: onSelect,
      ),
    );

    return SectionCard(
      padding: EdgeInsets.zero,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final hasBoundedHeight = constraints.hasBoundedHeight;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            mainAxisSize:
                hasBoundedHeight ? MainAxisSize.max : MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 14, 10, 12),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        '讲义结构',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    IconButton(
                      tooltip: '刷新讲义',
                      onPressed: state.isLoading ? null : onRefresh,
                      icon: const Icon(Icons.sync),
                    ),
                  ],
                ),
              ),
              const Divider(height: 1),
              if (hasBoundedHeight)
                Expanded(child: blockList)
              else
                SizedBox(height: 480, child: blockList),
              const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: _OutlinePanelFooter(
                  state: state,
                  outline: outline,
                  onGenerate: onGenerate,
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _OutlinePanelFooter extends StatelessWidget {
  const _OutlinePanelFooter({
    required this.state,
    required this.outline,
    required this.onGenerate,
  });

  final HandoutState state;
  final HandoutOutlineModel? outline;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    final status = state.versionStatus.valueOrNull;
    final total = status?.totalBlocks ?? 0;
    final ready = status?.readyBlocks ?? 0;
    final value = total == 0 ? 0.0 : ready / total;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (outline != null &&
            (outline!.outlineUsedFallback || outline!.outlineIssues.isNotEmpty))
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _OutlineIssueNotice(outline: outline!),
          ),
        if (status != null) ...[
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    minHeight: 6,
                    value: value,
                    backgroundColor: const Color(0xFFE2E8F0),
                    valueColor: const AlwaysStoppedAnimation<Color>(
                      Color(0xFF22C55E),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '$ready/$total',
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
        ],
        OutlinedButton.icon(
          onPressed: state.isGenerating ? null : onGenerate,
          icon: const Icon(Icons.auto_awesome, size: 18),
          label: Text(state.isGenerating ? '生成中' : '重新生成讲义'),
        ),
      ],
    );
  }
}

class _OutlineIssueNotice extends StatelessWidget {
  const _OutlineIssueNotice({
    required this.outline,
  });

  final HandoutOutlineModel outline;

  @override
  Widget build(BuildContext context) {
    final issueText = [
      if (outline.outlineUsedFallback) '目录已使用降级结构展示。',
      ...outline.outlineIssues,
    ].join('；');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline,
            size: 18,
            color: Color(0xFFB45309),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              issueText,
              style: const TextStyle(
                color: Color(0xFF92400E),
                fontSize: 12,
                fontWeight: FontWeight.w700,
                height: 1.35,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BlockList extends StatelessWidget {
  const _BlockList({
    required this.state,
    required this.outline,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
  });

  final HandoutState state;
  final HandoutOutlineModel? outline;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutOutlineChildModel> onSelect;

  @override
  Widget build(BuildContext context) {
    if (state.outline.isLoading) {
      return const AppLoadingView(label: '正在读取讲义目录');
    }
    if (state.outline.hasError) {
      return AppErrorView(message: '讲义目录暂不可用：${state.outline.error}');
    }
    final sections = outline?.items ?? const [];
    if (sections.isEmpty) {
      return const Text('暂无讲义目录。');
    }

    return ListView.builder(
      padding: EdgeInsets.zero,
      itemCount: sections.length,
      itemBuilder: (context, index) {
        final section = sections[index];
        final sectionBlockIds =
            section.children.map((child) => child.blockId).toSet();
        final containsSelected = selectedBlockId != null &&
            sectionBlockIds.contains(selectedBlockId);
        final containsHighlighted = highlightedBlockId != null &&
            sectionBlockIds.contains(highlightedBlockId);
        return Padding(
          padding:
              EdgeInsets.only(bottom: index == sections.length - 1 ? 0 : 8),
          child: _OutlineSectionGroup(
            state: state,
            section: section,
            index: index,
            containsSelected: containsSelected,
            containsHighlighted: containsHighlighted,
            highlightedBlockId: highlightedBlockId,
            selectedBlockId: selectedBlockId,
            onSelect: onSelect,
          ),
        );
      },
    );
  }
}

class _OutlineSectionGroup extends StatelessWidget {
  const _OutlineSectionGroup({
    required this.state,
    required this.section,
    required this.index,
    required this.containsSelected,
    required this.containsHighlighted,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
  });

  final HandoutState state;
  final HandoutOutlineSectionModel section;
  final int index;
  final bool containsSelected;
  final bool containsHighlighted;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutOutlineChildModel> onSelect;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _SectionHeader(
          section: section,
          index: index,
          isActive: containsSelected || containsHighlighted,
        ),
        if (section.children.isEmpty)
          const Padding(
            padding: EdgeInsets.only(left: 34, top: 6, bottom: 4),
            child: Text(
              '该分组暂无二级目录。',
              style: TextStyle(
                color: AppTheme.muted,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          )
        else
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 30),
            child: Column(
              children: [
                for (final child in section.children)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: _BlockTile(
                      child: child,
                      status: state.effectiveBlockStatus(child.blockId),
                      isHighlighted: child.blockId == highlightedBlockId,
                      isSelected: child.blockId == selectedBlockId,
                      onTap: () => onSelect(child),
                    ),
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.section,
    required this.index,
    required this.isActive,
  });

  final HandoutOutlineSectionModel section;
  final int index;
  final bool isActive;

  @override
  Widget build(BuildContext context) {
    final color = isActive ? AppTheme.brandBlue : AppTheme.ink;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Icon(
            section.children.isEmpty
                ? Icons.chevron_right
                : Icons.keyboard_arrow_down,
            color: color,
            size: 18,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '第 ${index + 1} 章  ${section.title}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: color,
                fontWeight: isActive ? FontWeight.w900 : FontWeight.w800,
                fontSize: 13,
              ),
            ),
          ),
          Text(
            '${section.children.length}',
            style: TextStyle(
              color: isActive ? AppTheme.brandBlue : AppTheme.subtle,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _BlockTile extends StatelessWidget {
  const _BlockTile({
    required this.child,
    required this.status,
    required this.isHighlighted,
    required this.isSelected,
    required this.onTap,
  });

  final HandoutOutlineChildModel child;
  final String status;
  final bool isHighlighted;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color =
        isSelected || isHighlighted ? AppTheme.brandBlue : AppTheme.muted;
    final background = isSelected
        ? const Color(0xFFEAF2FF)
        : isHighlighted
            ? const Color(0xFFF4F8FF)
            : Colors.transparent;
    final statusColor = _statusColor(status);

    return Padding(
      padding: EdgeInsets.zero,
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 8, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 10,
                  height: 10,
                  margin: const EdgeInsets.only(top: 4),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isSelected ? AppTheme.brandBlue : Colors.white,
                    border: Border.all(
                      color: isSelected || isHighlighted
                          ? AppTheme.brandBlue
                          : AppTheme.subtle,
                      width: isSelected ? 2 : 1.4,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        child.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: color,
                          fontWeight:
                              isSelected ? FontWeight.w900 : FontWeight.w700,
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          _OutlineMetaChip(
                            label: _statusLabel(status),
                            color: statusColor,
                          ),
                          _OutlineMetaChip(
                            label:
                                '${_formatSec(child.startSec)}-${_formatSec(child.endSec)}',
                            color: AppTheme.muted,
                          ),
                          if (child.topicTags.isNotEmpty)
                            _OutlineMetaChip(
                              label: child.topicTags.take(2).join(' / '),
                              color: AppTheme.subtle,
                            ),
                        ],
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

class _OutlineMetaChip extends StatelessWidget {
  const _OutlineMetaChip({
    required this.label,
    required this.color,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        color: color,
        fontSize: 11,
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

class _LearningCenterPanel extends StatelessWidget {
  const _LearningCenterPanel({
    required this.courseId,
    required this.state,
    required this.player,
    required this.highlightedChild,
    required this.selectedBlock,
    required this.onTogglePlay,
    required this.onSeek,
    required this.onGenerateBlock,
    required this.onRetryPlayback,
    required this.onCitationTap,
  });

  final String courseId;
  final HandoutState state;
  final PlayerState player;
  final HandoutOutlineChildModel? highlightedChild;
  final HandoutBlockModel? selectedBlock;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;
  final VoidCallback? onGenerateBlock;
  final VoidCallback onRetryPlayback;
  final ValueChanged<CitationModel>? onCitationTap;

  @override
  Widget build(BuildContext context) {
    final block = selectedBlock;
    final highlightedBlock = highlightedChild == null
        ? null
        : state.blockForId(highlightedChild!.blockId);
    final children = [
      Row(
        children: [
          Expanded(
            child: Text(
              '当前知识点：  ${block?.title ?? '等待同步'}',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
          const StatusPill(label: '学习模式'),
          const SizedBox(width: 12),
          StatusPill(
            label: '已掌握 ${_masteryFor(block)}%',
            color: const Color(0xFF16A34A),
          ),
        ],
      ),
      const SizedBox(height: 18),
      _VideoStage(
        courseId: courseId,
        state: state,
        block: highlightedBlock ?? block,
        player: player,
        onTogglePlay: onTogglePlay,
        onSeek: onSeek,
        onRetryPlayback: onRetryPlayback,
      ),
      const SizedBox(height: 18),
      _ContentPanel(
        state: state,
        block: block,
        onGenerateBlock: onGenerateBlock,
        onCitationTap: onCitationTap,
      ),
    ];
    return SectionCard(
      padding: const EdgeInsets.all(20),
      child: LayoutBuilder(
        builder: (context, constraints) {
          if (!constraints.hasBoundedHeight) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: children,
            );
          }
          return ListView(children: children);
        },
      ),
    );
  }

  int _masteryFor(HandoutBlockModel? block) {
    if (block == null) {
      return 0;
    }
    if (block.status == 'ready') {
      return 60;
    }
    if (block.status == 'generating') {
      return 35;
    }
    return 20;
  }
}

class _VideoStage extends ConsumerStatefulWidget {
  const _VideoStage({
    required this.courseId,
    required this.state,
    required this.block,
    required this.player,
    required this.onTogglePlay,
    required this.onSeek,
    required this.onRetryPlayback,
  });

  final String courseId;
  final HandoutState state;
  final HandoutBlockModel? block;
  final PlayerState player;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;
  final VoidCallback onRetryPlayback;

  @override
  ConsumerState<_VideoStage> createState() => _VideoStageState();
}

class _VideoStageState extends ConsumerState<_VideoStage> {
  HandoutVideoController? _controller;
  String? _playbackUrl;
  bool _isInitializing = false;
  Object? _initializationError;
  int? _pendingSeekTargetSec;
  bool? _pendingPlayState;
  int? _lastOverlayBlockId;
  Timer? _titleOverlayCollapseTimer;
  Timer? _contextOverlayCollapseTimer;
  bool _titleOverlayExpanded = true;
  bool _contextOverlayExpanded = true;

  @override
  void initState() {
    super.initState();
    _lastOverlayBlockId = widget.block?.blockId;
    _scheduleOverlayCollapse();
    _syncControllerWithPlayback();
  }

  @override
  void didUpdateWidget(covariant _VideoStage oldWidget) {
    super.didUpdateWidget(oldWidget);
    final nextBlockId = widget.block?.blockId;
    if (nextBlockId != _lastOverlayBlockId) {
      _lastOverlayBlockId = nextBlockId;
      _expandOverlaysTemporarily();
    }
    _syncControllerWithPlayback();
    _applyDesiredControllerState();
  }

  @override
  void dispose() {
    _titleOverlayCollapseTimer?.cancel();
    _contextOverlayCollapseTimer?.cancel();
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
    _pendingPlayState = null;

    if (nextUrl == null) {
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
        setState(() {
          _isInitializing = false;
        });
        _applyDesiredControllerState();
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
    _scheduleControllerSync();
  }

  void _scheduleControllerSync() {
    Future<void>.microtask(() {
      if (!mounted) {
        return;
      }
      _syncPlayerStateFromController();
      if (mounted) {
        setState(() {});
      }
    });
  }

  void _applyDesiredControllerState() {
    final controller = _controller;
    if (controller == null || !controller.isInitialized) {
      return;
    }
    final desiredSec = widget.player.positionSec;
    final currentSec = controller.position.inSeconds;
    if ((currentSec - desiredSec).abs() > 1 &&
        _pendingSeekTargetSec != desiredSec) {
      _pendingSeekTargetSec = desiredSec;
      unawaited(
        controller.seekTo(Duration(seconds: desiredSec)).then((_) {
          if (!mounted ||
              _controller != controller ||
              _pendingSeekTargetSec != desiredSec) {
            return;
          }
          _pendingSeekTargetSec = null;
          _scheduleControllerSync();
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

    final desiredPlaying = widget.player.isPlaying;
    if (controller.isPlaying != desiredPlaying &&
        _pendingPlayState != desiredPlaying) {
      _pendingPlayState = desiredPlaying;
      final command = desiredPlaying ? controller.play() : controller.pause();
      unawaited(
        command.then((_) {
          if (!mounted ||
              _controller != controller ||
              _pendingPlayState != desiredPlaying) {
            return;
          }
          _pendingPlayState = null;
          _scheduleControllerSync();
        }).catchError((Object error) {
          if (!mounted || _controller != controller) {
            return;
          }
          setState(() {
            _pendingPlayState = null;
            _initializationError = error;
          });
        }),
      );
    }
  }

  void _syncPlayerStateFromController() {
    final controller = _controller;
    if (!mounted || controller == null || !controller.isInitialized) {
      return;
    }
    final current = ref.read(playerStateProvider);
    final controllerSec = controller.position.inSeconds;
    final pendingSeek = _pendingSeekTargetSec;
    var nextPositionSec = controllerSec;
    if (pendingSeek != null) {
      if ((controllerSec - pendingSeek).abs() <= 1) {
        _pendingSeekTargetSec = null;
      } else {
        nextPositionSec = current.positionSec;
      }
    }
    if (current.positionSec == nextPositionSec &&
        current.isPlaying == controller.isPlaying) {
      return;
    }
    ref.read(playerStateProvider.notifier).state = current.copyWith(
      positionSec: nextPositionSec,
      isPlaying: controller.isPlaying,
    );
    unawaited(
      ref.read(handoutProvider.notifier).prefetchNextBlockNearPosition(
            courseId: widget.courseId,
            positionSec: nextPositionSec,
          ),
    );
  }

  void _expandOverlaysTemporarily() {
    _titleOverlayCollapseTimer?.cancel();
    _contextOverlayCollapseTimer?.cancel();
    if (mounted) {
      setState(() {
        _titleOverlayExpanded = true;
        _contextOverlayExpanded = true;
      });
    } else {
      _titleOverlayExpanded = true;
      _contextOverlayExpanded = true;
    }
    _scheduleOverlayCollapse();
  }

  void _scheduleOverlayCollapse() {
    _scheduleTitleOverlayCollapse();
    _scheduleContextOverlayCollapse();
  }

  void _scheduleTitleOverlayCollapse() {
    _titleOverlayCollapseTimer?.cancel();
    _titleOverlayCollapseTimer = Timer(const Duration(seconds: 3), () {
      if (!mounted) {
        return;
      }
      setState(() {
        _titleOverlayExpanded = false;
      });
    });
  }

  void _scheduleContextOverlayCollapse() {
    _contextOverlayCollapseTimer?.cancel();
    _contextOverlayCollapseTimer = Timer(const Duration(seconds: 3), () {
      if (!mounted) {
        return;
      }
      setState(() {
        _contextOverlayExpanded = false;
      });
    });
  }

  void _toggleTitleOverlay() {
    _titleOverlayCollapseTimer?.cancel();
    setState(() {
      _titleOverlayExpanded = !_titleOverlayExpanded;
    });
  }

  void _toggleContextOverlay() {
    _contextOverlayCollapseTimer?.cancel();
    setState(() {
      _contextOverlayExpanded = !_contextOverlayExpanded;
    });
  }

  @override
  Widget build(BuildContext context) {
    final block = widget.block;
    final positionLabel = _formatSec(widget.player.positionSec);
    final duration = _durationSec();
    final durationLabel = duration == null ? '--:--' : _formatSec(duration);
    final value = duration == null || duration == 0
        ? 0.0
        : (widget.player.positionSec / duration).clamp(0.0, 1.0).toDouble();
    final showContextBoard = !widget.state.playback.isLoading &&
        !widget.state.playback.hasError &&
        _initializationError == null;

    return Container(
      height: 472,
      decoration: BoxDecoration(
        color: const Color(0xFF070B12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: DecoratedBox(
                decoration: const BoxDecoration(color: Color(0xFF020617)),
                child: _buildVideoSurface(context),
              ),
            ),
          ),
          Positioned(
            left: 18,
            top: 18,
            right: 18,
            child: _VideoTitleOverlay(
              title: block == null ? '等待讲义块同步播放位置' : block.title,
              subtitle: block?.summary ?? '选择讲义块后同步播放定位、来源引用与追问上下文。',
              isExpanded: _titleOverlayExpanded,
              onToggle: _toggleTitleOverlay,
            ),
          ),
          if (showContextBoard)
            Positioned(
              right: 22,
              bottom: 78,
              width: _contextOverlayExpanded ? 280 : 168,
              height: _contextOverlayExpanded ? 148 : 44,
              child: _VideoContextBoard(
                block: block,
                status: block == null
                    ? null
                    : widget.state.effectiveBlockStatus(block.blockId),
                isExpanded: _contextOverlayExpanded,
                onToggle: _toggleContextOverlay,
              ),
            ),
          Positioned(
            left: 22,
            bottom: 68,
            child: Text(
              '课程 ${widget.courseId} · $positionLabel',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          Positioned(
            left: 18,
            right: 18,
            bottom: 14,
            child: LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 520;
                return Row(
                  children: [
                    IconButton(
                      tooltip: widget.player.isPlaying ? '暂停' : '播放',
                      onPressed: widget.onTogglePlay,
                      color: Colors.white,
                      icon: Icon(
                        widget.player.isPlaying
                            ? Icons.pause
                            : Icons.play_arrow,
                      ),
                    ),
                    Flexible(
                      child: Text(
                        '$positionLabel / $durationLabel',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      flex: compact ? 2 : 4,
                      child: ProgressRail(
                        value: value,
                        color: AppTheme.brandBlue,
                      ),
                    ),
                    const SizedBox(width: 10),
                    TextButton(
                      onPressed: () => widget.onSeek(-30),
                      child: Text(
                        compact ? '-30' : '-30s',
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                    TextButton(
                      onPressed: () => widget.onSeek(30),
                      child: Text(
                        compact ? '+30' : '+30s',
                        style: const TextStyle(color: Colors.white),
                      ),
                    ),
                    if (!compact) ...[
                      const Icon(Icons.volume_up_outlined, color: Colors.white),
                      const SizedBox(width: 12),
                      const Icon(Icons.fullscreen, color: Colors.white),
                    ],
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoSurface(BuildContext context) {
    if (widget.state.playback.isLoading) {
      return const _VideoStatusOverlay(
        icon: Icons.hourglass_top,
        title: '正在获取视频播放地址',
        subtitle: '已保留讲义正文和问答上下文。',
        showProgress: true,
      );
    }
    if (widget.state.playback.hasError) {
      final message = _playbackErrorMessage(widget.state.playback.error);
      return _VideoStatusOverlay(
        icon: Icons.error_outline,
        title: message.title,
        subtitle: message.subtitle,
        actionLabel: '重新加载视频',
        onAction: widget.onRetryPlayback,
      );
    }
    final playback = widget.state.playback.valueOrNull;
    if (playback == null) {
      return const _VideoStatusOverlay(
        icon: Icons.videocam_off_outlined,
        title: '当前讲义块暂无视频定位',
        subtitle: '可以继续阅读正文或使用当前块问答。',
      );
    }
    final controller = _controller;
    if (_initializationError != null) {
      return _VideoStatusOverlay(
        icon: Icons.error_outline,
        title: '视频加载失败',
        subtitle: '播放地址可能已过期或当前平台暂不可播放。',
        actionLabel: '重新加载视频',
        onAction: widget.onRetryPlayback,
      );
    }
    if (_isInitializing || controller == null || !controller.isInitialized) {
      return const _VideoStatusOverlay(
        icon: Icons.play_circle_outline,
        title: '正在加载视频',
        subtitle: '视频地址由后端预签名接口提供。',
        showProgress: true,
      );
    }
    final aspectRatio =
        controller.aspectRatio <= 0 ? 16 / 9 : controller.aspectRatio;
    return Center(
      child: AspectRatio(
        aspectRatio: aspectRatio,
        child: controller.buildPlayer(),
      ),
    );
  }

  int? _durationSec() {
    final controllerDuration = _controller?.duration.inSeconds ?? 0;
    if (controllerDuration > 0) {
      return controllerDuration;
    }
    final playbackDuration = widget.state.playback.valueOrNull?.durationSec;
    if (playbackDuration != null && playbackDuration > 0) {
      return playbackDuration;
    }
    return null;
  }

  _PlaybackErrorMessage _playbackErrorMessage(Object? error) {
    if (error is DioException) {
      final code = _errorCode(error.response?.data);
      if (code == 'resource.not_video') {
        return const _PlaybackErrorMessage(
          title: '当前定位资源不是视频',
          subtitle: '该讲义块返回的资源不能播放，可以继续阅读正文或使用当前块问答。',
        );
      }
      if (code == 'resource.playback_unavailable') {
        return const _PlaybackErrorMessage(
          title: '播放地址暂不可用',
          subtitle: '对象存储暂时无法生成播放地址，请重新加载视频。',
        );
      }
      return const _PlaybackErrorMessage(
        title: '视频网络请求失败',
        subtitle: '暂时无法连接播放地址接口，请重新加载视频。',
      );
    }
    return const _PlaybackErrorMessage(
      title: '视频播放地址暂不可用',
      subtitle: '暂时无法获取当前讲义块的视频地址，请重新加载视频。',
    );
  }

  String? _errorCode(Object? data) {
    if (data is Map) {
      return data['errorCode'] as String?;
    }
    return null;
  }
}

class _PlaybackErrorMessage {
  const _PlaybackErrorMessage({
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;
}

class _VideoTitleOverlay extends StatelessWidget {
  const _VideoTitleOverlay({
    required this.title,
    required this.subtitle,
    required this.isExpanded,
    required this.onToggle,
  });

  final String title;
  final String subtitle;
  final bool isExpanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.48),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: AnimatedCrossFade(
                firstChild: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                secondChild: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white70,
                        height: 1.3,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                crossFadeState: isExpanded
                    ? CrossFadeState.showSecond
                    : CrossFadeState.showFirst,
                duration: const Duration(milliseconds: 180),
              ),
            ),
            const SizedBox(width: 6),
            IconButton(
              tooltip: isExpanded ? '收起标题浮层' : '展开标题浮层',
              onPressed: onToggle,
              visualDensity: VisualDensity.compact,
              color: Colors.white70,
              icon: Icon(
                isExpanded
                    ? Icons.keyboard_arrow_up
                    : Icons.keyboard_arrow_down,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _VideoStatusOverlay extends StatelessWidget {
  const _VideoStatusOverlay({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.showProgress = false,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool showProgress;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment.topRight,
          radius: 1.2,
          colors: [Color(0xFF1E293B), Color(0xFF020617)],
        ),
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: Colors.white70, size: 40),
              const SizedBox(height: 14),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                subtitle,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white70,
                  height: 1.4,
                ),
              ),
              if (showProgress) ...[
                const SizedBox(height: 16),
                const LinearProgressIndicator(),
              ],
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  onPressed: onAction,
                  icon: const Icon(Icons.refresh),
                  label: Text(actionLabel!),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _VideoContextBoard extends StatelessWidget {
  const _VideoContextBoard({
    required this.block,
    required this.status,
    required this.isExpanded,
    required this.onToggle,
  });

  final HandoutBlockModel? block;
  final String? status;
  final bool isExpanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final block = this.block;
    return Container(
      padding: EdgeInsets.all(isExpanded ? 12 : 6),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: block == null || !isExpanded
          ? Row(
              children: [
                Expanded(
                  child: Text(
                    block == null
                        ? '等待同步'
                        : '${_statusLabel(status ?? block.status)} · ${_formatSec(block.startSec)}',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: isExpanded ? '收起讲义块信息' : '展开讲义块信息',
                  onPressed: onToggle,
                  visualDensity: VisualDensity.compact,
                  color: Colors.white70,
                  icon: Icon(
                    isExpanded
                        ? Icons.keyboard_arrow_down
                        : Icons.keyboard_arrow_up,
                  ),
                ),
              ],
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _statusLabel(status ?? block.status),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Color(0xFFA7F3D0),
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: '收起讲义块信息',
                      onPressed: onToggle,
                      visualDensity: VisualDensity.compact,
                      color: Colors.white70,
                      icon: const Icon(Icons.keyboard_arrow_down),
                    ),
                  ],
                ),
                Text(
                  block.summary.isEmpty ? block.title : block.summary,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    height: 1.35,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${_formatSec(block.startSec)}-${_formatSec(block.endSec)}',
                  style: const TextStyle(
                    color: Colors.white70,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
    );
  }
}

class _ContentPanel extends StatelessWidget {
  const _ContentPanel({
    required this.state,
    required this.block,
    required this.onGenerateBlock,
    required this.onCitationTap,
  });

  final HandoutState state;
  final HandoutBlockModel? block;
  final VoidCallback? onGenerateBlock;
  final ValueChanged<CitationModel>? onCitationTap;

  @override
  Widget build(BuildContext context) {
    final block = this.block;
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _TabHeader(),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  '知识点解析',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                if (block == null)
                  const Text('选择讲义块后展示正文和引用。')
                else ...[
                  _BlockContent(
                    block: block,
                    status: state.effectiveBlockStatus(block.blockId),
                    isGeneratingBlock: state.isBlockGenerating(block.blockId),
                    onGenerateBlock: onGenerateBlock,
                  ),
                  if (state
                      .blockGenerateRequestFor(block.blockId)
                      .hasError) ...[
                    const SizedBox(height: 12),
                    AppErrorView(
                      message:
                          '生成当前块失败：${state.blockGenerateRequestFor(block.blockId).error}',
                    ),
                  ],
                  const SizedBox(height: 14),
                  _CitationList(
                    block: block,
                    citations: block.citations,
                    onTap: onCitationTap,
                  ),
                  const SizedBox(height: 12),
                  _JumpTargetView(state: state),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TabHeader extends StatelessWidget {
  const _TabHeader();

  @override
  Widget build(BuildContext context) {
    const tabs = ['知识点解析', '例题讲解', '关联题', '扩展阅读'];
    return Container(
      height: 54,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppTheme.line)),
      ),
      child: Row(
        children: [
          for (final tab in tabs)
            Expanded(
              child: Container(
                alignment: Alignment.center,
                decoration: tab == tabs.first
                    ? const BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: AppTheme.brandBlue,
                            width: 3,
                          ),
                        ),
                      )
                    : null,
                child: Text(
                  tab,
                  style: TextStyle(
                    color:
                        tab == tabs.first ? AppTheme.brandBlue : AppTheme.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _BlockContent extends StatelessWidget {
  const _BlockContent({
    required this.block,
    required this.status,
    required this.isGeneratingBlock,
    required this.onGenerateBlock,
  });

  final HandoutBlockModel block;
  final String status;
  final bool isGeneratingBlock;
  final VoidCallback? onGenerateBlock;

  @override
  Widget build(BuildContext context) {
    if (status == 'failed') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('该讲义块生成失败，可重试生成。'),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: isGeneratingBlock ? null : onGenerateBlock,
            icon: const Icon(Icons.refresh),
            label: const Text('重新生成当前块'),
          ),
        ],
      );
    }
    if (status != 'ready') {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '该讲义块状态为${_statusLabel(status)}，正文生成后会展示结构化讲义内容。',
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: isGeneratingBlock ? null : onGenerateBlock,
            icon: const Icon(Icons.auto_awesome),
            label: Text(isGeneratingBlock ? '正在生成当前块' : '生成当前块'),
          ),
        ],
      );
    }
    final content = block.contentMd;
    if (content == null || content.trim().isEmpty) {
      return const Text('该讲义块暂无正文。');
    }
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.line),
      ),
      child: MarkdownBody(
        data: content,
        selectable: true,
        styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
          p: const TextStyle(
            color: AppTheme.ink,
            height: 1.5,
            fontSize: 14,
          ),
          h1: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: AppTheme.ink,
                fontWeight: FontWeight.w900,
              ),
          h2: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: AppTheme.ink,
                fontWeight: FontWeight.w900,
              ),
          h3: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: AppTheme.ink,
                fontWeight: FontWeight.w900,
              ),
          listBullet: const TextStyle(
            color: AppTheme.ink,
            height: 1.45,
          ),
          blockquoteDecoration: const BoxDecoration(
            color: Color(0xFFEFF6FF),
            border: Border(
              left: BorderSide(color: AppTheme.brandBlue, width: 3),
            ),
          ),
        ),
      ),
    );
  }
}

class _CitationList extends StatelessWidget {
  const _CitationList({
    this.block,
    required this.citations,
    required this.onTap,
  });

  final HandoutBlockModel? block;
  final List<CitationModel> citations;
  final ValueChanged<CitationModel>? onTap;

  @override
  Widget build(BuildContext context) {
    final displayCitations = _displayCitations();
    if (displayCitations.isEmpty) {
      return const Text('暂无引用。');
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('来源引用', style: Theme.of(context).textTheme.titleSmall),
              const Spacer(),
              const Text(
                '点击引用定位',
                style: TextStyle(
                  color: AppTheme.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: displayCitations
                .map(
                  (citation) => SourceChip(
                    icon: _citationIcon(citation),
                    label: _citationLabel(citation),
                    onTap: onTap == null ? null : () => onTap!(citation),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }

  List<CitationModel> _displayCitations() {
    final block = this.block;
    if (block == null) {
      return citations;
    }
    var videoCitationCount = 0;
    final nonVideoCitations = <CitationModel>[];
    for (final citation in citations) {
      if (citation.startSec != null || citation.endSec != null) {
        videoCitationCount++;
      } else {
        nonVideoCitations.add(citation);
      }
    }
    if (videoCitationCount < 2) {
      return citations;
    }
    return [
      CitationModel(
        resourceId: _firstVideoResourceId(citations),
        refLabel: '视频',
        startSec: block.startSec,
        endSec: block.endSec,
      ),
      ...nonVideoCitations,
    ];
  }

  int _firstVideoResourceId(List<CitationModel> citations) {
    for (final citation in citations) {
      if (citation.startSec != null || citation.endSec != null) {
        return citation.resourceId;
      }
    }
    return block?.blockId ?? 0;
  }
}

class _JumpTargetView extends StatelessWidget {
  const _JumpTargetView({
    required this.state,
  });

  final HandoutState state;

  @override
  Widget build(BuildContext context) {
    final citation = state.selectedCitation;
    final citationLine = citation == null
        ? null
        : Row(
            children: [
              const Icon(Icons.link, size: 18, color: AppTheme.brandBlue),
              const SizedBox(width: 8),
              Expanded(child: Text('引用位置：${_citationLabel(citation)}')),
            ],
          );

    if (state.jumpTarget.isLoading) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (citationLine != null) ...[
            citationLine,
            const SizedBox(height: 8),
          ],
          const LinearProgressIndicator(),
        ],
      );
    }
    if (state.jumpTarget.hasError) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (citationLine != null) ...[
            citationLine,
            const SizedBox(height: 8),
          ],
          Text('跳转信息暂不可用：${state.jumpTarget.error}'),
        ],
      );
    }
    final target = state.jumpTarget.valueOrNull;
    if (target == null) {
      return const Text('点击讲义块或引用后展示后端返回的跳转位置。');
    }
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFEFF6FF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFBFDBFE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (citationLine != null) ...[
            citationLine,
            const SizedBox(height: 8),
          ],
          Row(
            children: [
              const Icon(Icons.near_me_outlined, size: 18),
              const SizedBox(width: 8),
              Expanded(child: Text('跳转位置：${target.displayText}')),
            ],
          ),
        ],
      ),
    );
  }
}

class _RightStudyPanel extends StatelessWidget {
  const _RightStudyPanel({
    required this.state,
    required this.selectedBlock,
    required this.controller,
    required this.onCitationTap,
    required this.onSubmit,
  });

  final HandoutState state;
  final HandoutBlockModel? selectedBlock;
  final TextEditingController controller;
  final ValueChanged<CitationModel>? onCitationTap;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final children = [
      _QaPanel(
        state: state,
        selectedBlock: selectedBlock,
        controller: controller,
        onCitationTap: onCitationTap,
        onSubmit: onSubmit,
      ),
      const SizedBox(height: 16),
      _RelatedStudyPanel(selectedBlock: selectedBlock),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        if (!constraints.hasBoundedHeight) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          );
        }
        return ListView(children: children);
      },
    );
  }
}

class _QaPanel extends StatelessWidget {
  const _QaPanel({
    required this.state,
    required this.selectedBlock,
    required this.controller,
    required this.onCitationTap,
    required this.onSubmit,
  });

  final HandoutState state;
  final HandoutBlockModel? selectedBlock;
  final TextEditingController controller;
  final ValueChanged<CitationModel>? onCitationTap;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final selectedBlock = this.selectedBlock;
    final canSubmit = selectedBlock != null &&
        !state.isSubmittingQuestion &&
        controller.text.trim().isNotEmpty;

    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const SoftIcon(icon: Icons.smart_toy_outlined, size: 34),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'AI 思考问答（当前块 QA）',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (state.qaSubmit.hasError) ...[
            AppErrorView(message: '提交 QA 失败：${state.qaSubmit.error}'),
            const SizedBox(height: 12),
          ],
          if (state.selectedBlockQaMessages.isEmpty)
            _QaEmptyState(
              selectedBlock: selectedBlock,
            )
          else
            ...state.selectedBlockQaMessages.reversed.map(
              (message) => _QaAnswerCard(
                message: message,
                onCitationTap: onCitationTap,
              ),
            ),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            enabled: selectedBlock != null && !state.isSubmittingQuestion,
            minLines: 1,
            maxLines: 3,
            decoration: InputDecoration(
              hintText: selectedBlock == null ? '请先选择讲义块' : '继续提问...',
              suffixIcon: IconButton(
                tooltip: '发送',
                onPressed: canSubmit ? onSubmit : null,
                icon: const Icon(Icons.send_outlined),
              ),
            ),
          ),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed: canSubmit ? onSubmit : null,
            icon: const Icon(Icons.send),
            label: Text(state.isSubmittingQuestion ? '正在提交' : '提交问题'),
          ),
        ],
      ),
    );
  }
}

class _QaEmptyState extends StatelessWidget {
  const _QaEmptyState({
    required this.selectedBlock,
  });

  final HandoutBlockModel? selectedBlock;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        selectedBlock == null ? '请先选择讲义块。' : '当前块还没有问答记录。',
        style: const TextStyle(
          color: AppTheme.muted,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _QaAnswerCard extends StatelessWidget {
  const _QaAnswerCard({
    required this.message,
    required this.onCitationTap,
  });

  final QaMessageModel message;
  final ValueChanged<CitationModel>? onCitationTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: AppTheme.line),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Icon(Icons.smart_toy_outlined, size: 18),
                  const SizedBox(width: 8),
                  Expanded(child: Text('回答 #${message.messageId}')),
                ],
              ),
              const SizedBox(height: 8),
              Text(message.answerMd),
              const SizedBox(height: 8),
              _CitationList(
                citations: message.citations,
                onTap: onCitationTap,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RelatedStudyPanel extends StatelessWidget {
  const _RelatedStudyPanel({
    required this.selectedBlock,
  });

  final HandoutBlockModel? selectedBlock;

  @override
  Widget build(BuildContext context) {
    final title = selectedBlock?.title ?? '相关知识点';
    return SectionCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '延伸学习',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              StatusPill(
                label: selectedBlock == null ? '待选择' : '当前块',
                color: selectedBlock == null
                    ? const Color(0xFF64748B)
                    : AppTheme.brandBlue,
              ),
            ],
          ),
          const SizedBox(height: 12),
          _RelatedItem(
            icon: Icons.link,
            title: title == '相关知识点' ? '相邻知识点' : title,
            subtitle: '结合当前讲义块的上下文继续学习。',
          ),
          const SizedBox(height: 10),
          const _RelatedItem(
            icon: Icons.assignment_outlined,
            title: '来源回看',
            subtitle: '回到对应视频或资料位置核对依据。',
            color: Color(0xFF22C55E),
          ),
          const SizedBox(height: 10),
          const _RelatedItem(
            icon: Icons.quiz_outlined,
            title: '错题巩固',
            subtitle: '用当前知识点生成针对性练习。',
            color: Color(0xFF8B5CF6),
          ),
        ],
      ),
    );
  }
}

class _RelatedItem extends StatelessWidget {
  const _RelatedItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.color = AppTheme.brandBlue,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          SoftIcon(icon: icon, color: color, size: 42),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

IconData _citationIcon(CitationModel citation) {
  if (citation.startSec != null) {
    return Icons.play_circle_outline;
  }
  if (citation.slideNo != null) {
    return Icons.description_outlined;
  }
  if (citation.pageNo != null) {
    return Icons.picture_as_pdf_outlined;
  }
  return Icons.link;
}

String _formatSec(int seconds) {
  final minutes = seconds ~/ 60;
  final rest = seconds % 60;
  return '$minutes:${rest.toString().padLeft(2, '0')}';
}

String _citationLabel(CitationModel citation) {
  if (citation.refLabel == citation.locatorText) {
    return citation.refLabel;
  }
  return '${citation.refLabel} · ${citation.locatorText}';
}

String _statusLabel(String status) {
  return switch (status) {
    'ready' => '已生成',
    'pending' => '待生成',
    'generating' => '生成中',
    'failed' => '生成失败',
    'outline_ready' => '目录已生成',
    'partial_success' => '部分成功',
    'draft' => '草稿',
    'superseded' => '已被替换',
    _ => '状态待确认',
  };
}

Color _statusColor(String status) {
  return switch (status) {
    'ready' => const Color(0xFF16A34A),
    'pending' => AppTheme.muted,
    'generating' => AppTheme.brandBlue,
    'failed' => const Color(0xFFDC2626),
    'outline_ready' => const Color(0xFF16A34A),
    'partial_success' => const Color(0xFFB45309),
    'draft' => AppTheme.subtle,
    'superseded' => AppTheme.subtle,
    _ => const Color(0xFFB45309),
  };
}
