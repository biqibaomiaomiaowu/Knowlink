import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
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
    final highlighted = state.highlightedBlockFor(player.positionSec);
    final selectedBlock = state.selectedBlock ?? highlighted;

    return AppScaffold(
      title: '个性化互动讲义',
      body: ListView(
        children: [
          _VideoPanel(
            courseId: widget.courseId,
            positionSec: player.positionSec,
            isPlaying: player.isPlaying,
            highlightedBlock: highlighted,
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
          ),
          const SizedBox(height: 12),
          _HandoutStatusPanel(
            state: state,
            courseId: widget.courseId,
            onRefresh: () => notifier.refreshData(widget.courseId),
            onGenerate: () => notifier.generateAndPoll(widget.courseId),
          ),
          const SizedBox(height: 12),
          _BlockListPanel(
            state: state,
            highlightedBlockId: highlighted?.blockId,
            selectedBlockId: selectedBlock?.blockId,
            onSelect: notifier.selectBlock,
          ),
          const SizedBox(height: 12),
          _CurrentBlockPanel(
            state: state,
            block: selectedBlock,
            onGenerateBlock: selectedBlock == null
                ? null
                : () => notifier.generateBlock(
                      selectedBlock.blockId,
                      courseId: widget.courseId,
                    ),
            onCitationTap: selectedBlock == null
                ? null
                : (citation) => notifier.requestJumpTarget(
                      selectedBlock.blockId,
                      citation: citation,
                    ),
          ),
          const SizedBox(height: 12),
          _QaPanel(
            state: state,
            selectedBlock: selectedBlock,
            controller: _questionController,
            onCitationTap: selectedBlock == null
                ? null
                : (citation) => notifier.requestJumpTarget(
                      selectedBlock.blockId,
                      citation: citation,
                    ),
            onSubmit: () async {
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
        ],
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

class _VideoPanel extends StatelessWidget {
  const _VideoPanel({
    required this.courseId,
    required this.positionSec,
    required this.isPlaying,
    required this.highlightedBlock,
    required this.onTogglePlay,
    required this.onSeek,
  });

  final String courseId;
  final int positionSec;
  final bool isPlaying;
  final HandoutBlockModel? highlightedBlock;
  final VoidCallback onTogglePlay;
  final ValueChanged<int> onSeek;

  @override
  Widget build(BuildContext context) {
    final block = highlightedBlock;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.play_circle_outline),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '课程 $courseId · ${_formatSec(positionSec)}',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: isPlaying ? '暂停' : '播放',
                  onPressed: onTogglePlay,
                  icon: Icon(
                    isPlaying ? Icons.pause : Icons.play_arrow,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              height: 140,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                block == null ? '等待讲义块同步播放位置' : '当前讲义块：${block.title}',
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: () => onSeek(-30),
                  icon: const Icon(Icons.replay_30),
                  label: const Text('后退 30 秒'),
                ),
                OutlinedButton.icon(
                  onPressed: () => onSeek(30),
                  icon: const Icon(Icons.forward_30),
                  label: const Text('前进 30 秒'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _HandoutStatusPanel extends StatelessWidget {
  const _HandoutStatusPanel({
    required this.state,
    required this.courseId,
    required this.onRefresh,
    required this.onGenerate,
  });

  final HandoutState state;
  final String courseId;
  final VoidCallback onRefresh;
  final VoidCallback onGenerate;

  @override
  Widget build(BuildContext context) {
    final latest = state.latest.valueOrNull;
    final versionStatus = state.versionStatus.valueOrNull;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              latest?.title ?? '课程 $courseId 的讲义',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(latest?.summary ?? '进入页面后会读取最新讲义，必要时自动发起生成。'),
            const SizedBox(height: 12),
            if (state.generateRequest.hasError)
              AppErrorView(
                message: '生成讲义失败：${state.generateRequest.error}',
                onRetry: onGenerate,
              )
            else if (state.latest.hasError)
              AppErrorView(
                message: '读取讲义失败：${state.latest.error}',
                onRetry: onRefresh,
              )
            else if (state.isGenerating)
              const AppLoadingView(label: '正在生成讲义并轮询状态')
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: state.isLoading ? null : onRefresh,
                    icon: const Icon(Icons.refresh),
                    label: const Text('刷新讲义'),
                  ),
                  FilledButton.icon(
                    onPressed: state.isGenerating ? null : onGenerate,
                    icon: const Icon(Icons.auto_awesome),
                    label: const Text('重新生成讲义'),
                  ),
                ],
              ),
            if (versionStatus != null) ...[
              const SizedBox(height: 12),
              _VersionStatusChips(status: versionStatus),
            ],
          ],
        ),
      ),
    );
  }
}

class _VersionStatusChips extends StatelessWidget {
  const _VersionStatusChips({
    required this.status,
  });

  final HandoutVersionStatusModel status;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        Chip(label: Text('状态 ${_statusLabel(status.status)}')),
        Chip(label: Text('目录 ${_statusLabel(status.outlineStatus)}')),
        Chip(label: Text('已完成 ${status.readyBlocks}/${status.totalBlocks}')),
        if (status.pendingBlocks > 0)
          Chip(label: Text('待生成 ${status.pendingBlocks}')),
      ],
    );
  }
}

class _BlockListPanel extends StatelessWidget {
  const _BlockListPanel({
    required this.state,
    required this.highlightedBlockId,
    required this.selectedBlockId,
    required this.onSelect,
  });

  final HandoutState state;
  final int? highlightedBlockId;
  final int? selectedBlockId;
  final ValueChanged<HandoutBlockModel> onSelect;

  @override
  Widget build(BuildContext context) {
    final blocks = state.blocks.valueOrNull?.items ?? const [];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '讲义块',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            if (state.blocks.isLoading)
              const AppLoadingView(label: '正在读取讲义块')
            else if (state.blocks.hasError)
              AppErrorView(message: '讲义块暂不可用：${state.blocks.error}')
            else if (blocks.isEmpty)
              const Text('暂无讲义块。')
            else
              ...blocks.map(
                (block) => _BlockTile(
                  block: block,
                  isHighlighted: block.blockId == highlightedBlockId,
                  isSelected: block.blockId == selectedBlockId,
                  onTap: () => onSelect(block),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _BlockTile extends StatelessWidget {
  const _BlockTile({
    required this.block,
    required this.isHighlighted,
    required this.isSelected,
    required this.onTap,
  });

  final HandoutBlockModel block;
  final bool isHighlighted;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final background = isSelected
        ? colorScheme.primaryContainer
        : isHighlighted
            ? colorScheme.secondaryContainer
            : Colors.transparent;

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Material(
        color: background,
        borderRadius: BorderRadius.circular(8),
        child: ListTile(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          onTap: onTap,
          leading: CircleAvatar(
            child: Text(_formatSec(block.startSec)),
          ),
          title: Text(block.title),
          subtitle: Text('${block.summary}\n${_statusLabel(block.status)}'),
          trailing: const Icon(Icons.chevron_right),
        ),
      ),
    );
  }
}

class _CurrentBlockPanel extends StatelessWidget {
  const _CurrentBlockPanel({
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
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '当前块正文',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            if (block == null)
              const Text('选择讲义块后展示正文和引用。')
            else ...[
              Text(
                block.title,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              _BlockContent(block: block),
              if (block.status != 'ready') ...[
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: state.blockGenerateRequest.isLoading
                      ? null
                      : onGenerateBlock,
                  icon: const Icon(Icons.auto_awesome),
                  label: Text(
                    state.blockGenerateRequest.isLoading ? '正在生成当前块' : '生成当前块',
                  ),
                ),
              ],
              if (state.blockGenerateRequest.hasError) ...[
                const SizedBox(height: 8),
                AppErrorView(
                  message: '生成当前块失败：${state.blockGenerateRequest.error}',
                ),
              ],
              const SizedBox(height: 12),
              _CitationList(
                citations: block.citations,
                onTap: onCitationTap,
              ),
              const SizedBox(height: 12),
              _JumpTargetView(state: state),
            ],
          ],
        ),
      ),
    );
  }
}

class _BlockContent extends StatelessWidget {
  const _BlockContent({
    required this.block,
  });

  final HandoutBlockModel block;

  @override
  Widget build(BuildContext context) {
    if (block.status == 'failed') {
      return const Text('该讲义块生成失败，可重试生成。');
    }
    if (block.status != 'ready') {
      return Text(
        '该讲义块状态为${_statusLabel(block.status)}，正文生成后会展示原始 Markdown。',
      );
    }
    final content = block.contentMd;
    if (content == null || content.trim().isEmpty) {
      return const Text('该讲义块暂无正文。');
    }
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        content,
        style: const TextStyle(
          fontFamily: 'monospace',
          height: 1.35,
        ),
      ),
    );
  }
}

class _CitationList extends StatelessWidget {
  const _CitationList({
    required this.citations,
    required this.onTap,
  });

  final List<CitationModel> citations;
  final ValueChanged<CitationModel>? onTap;

  @override
  Widget build(BuildContext context) {
    if (citations.isEmpty) {
      return const Text('暂无引用。');
    }
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: citations
          .map(
            (citation) => ActionChip(
              avatar: const Icon(Icons.link, size: 18),
              label: Text(_citationLabel(citation)),
              onPressed: onTap == null ? null : () => onTap!(citation),
            ),
          )
          .toList(),
    );
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
              const Icon(Icons.link, size: 18),
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
    return Column(
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
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              '当前块 QA',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              enabled: selectedBlock != null && !state.isSubmittingQuestion,
              minLines: 2,
              maxLines: 4,
              decoration: InputDecoration(
                labelText: selectedBlock == null
                    ? '请先选择讲义块'
                    : '追问：${selectedBlock.title}',
                border: const OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            FilledButton.icon(
              onPressed: canSubmit ? onSubmit : null,
              icon: const Icon(Icons.send),
              label: Text(state.isSubmittingQuestion ? '正在提交' : '提交问题'),
            ),
            if (state.qaSubmit.hasError) ...[
              const SizedBox(height: 8),
              AppErrorView(message: '提交 QA 失败：${state.qaSubmit.error}'),
            ],
            const SizedBox(height: 12),
            if (state.selectedBlockQaMessages.isEmpty)
              const Text('当前块还没有问答记录。')
            else
              ...state.selectedBlockQaMessages.reversed.map(
                (message) => _QaAnswerCard(
                  message: message,
                  onCitationTap: onCitationTap,
                ),
              ),
          ],
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
      padding: const EdgeInsets.only(top: 8),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).dividerColor),
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
