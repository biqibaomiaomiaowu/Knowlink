import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/soft_ui_models.dart';
import '../../shared/providers/soft_ui_provider.dart';

class CourseQaPage extends ConsumerStatefulWidget {
  const CourseQaPage({
    required this.courseId,
    this.lessonId,
    super.key,
  });

  final String courseId;
  final String? lessonId;

  @override
  ConsumerState<CourseQaPage> createState() => _CourseQaPageState();
}

class _CourseQaPageState extends ConsumerState<CourseQaPage> {
  final _controller = TextEditingController();
  var _scope = '当前课时';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(softUiProvider);
    final session = state.activeChatSession;
    return AppScaffold(
      title: 'AI 问答',
      activeTab: KnowLinkTab.chat,
      courseId: widget.courseId,
      lessonId: widget.lessonId ?? state.activeLessonId,
      body: ListView(
        children: [
          PageTitle(
            title: 'AI 问答',
            subtitle: '按全课程、当前课时或指定章节切换回答范围，并保留来源引用。',
            icon: Icons.forum_outlined,
            actions: [
              SoftButton(
                label: '新建会话',
                icon: Icons.add_comment_outlined,
                primary: true,
                onPressed: () =>
                    ref.read(softUiProvider.notifier).newChatSession(_scope),
              ),
            ],
          ),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 1040;
              final history = _HistoryPanel(
                sessions: state.chatSessions,
                activeId: session.id,
                onSelect: (id) =>
                    ref.read(softUiProvider.notifier).selectChatSession(id),
              );
              final chat = _ChatPanel(
                session: session,
                scope: _scope,
                controller: _controller,
                onScopeChanged: (value) => setState(() => _scope = value),
                onSend: _send,
              );
              if (!wide) {
                return Column(
                  children: [
                    history,
                    const SizedBox(height: 16),
                    chat,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 3, child: history),
                  const SizedBox(width: 16),
                  Expanded(flex: 7, child: chat),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  void _send() {
    ref.read(softUiProvider.notifier).sendChat(
          text: _controller.text,
          scope: _scope,
        );
    _controller.clear();
  }
}

class _HistoryPanel extends StatelessWidget {
  const _HistoryPanel({
    required this.sessions,
    required this.activeId,
    required this.onSelect,
  });

  final List<SoftChatSession> sessions;
  final String activeId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const _SectionTitle('历史会话'),
          const SizedBox(height: 12),
          ...sessions.map(
            (session) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: SectionCard(
                inset: true,
                padding: const EdgeInsets.all(14),
                onTap: () => onSelect(session.id),
                child: Row(
                  children: [
                    SoftIcon(
                      icon: Icons.chat_bubble_outline,
                      color: session.id == activeId
                          ? AppTheme.success
                          : AppTheme.accent,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${session.scope}会话',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: AppTheme.text,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '${session.messages.length} 条消息',
                            style: const TextStyle(
                              color: AppTheme.muted,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
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
        ],
      ),
    );
  }
}

class _ChatPanel extends StatelessWidget {
  const _ChatPanel({
    required this.session,
    required this.scope,
    required this.controller,
    required this.onScopeChanged,
    required this.onSend,
  });

  final SoftChatSession session;
  final String scope;
  final TextEditingController controller;
  final ValueChanged<String> onScopeChanged;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(child: _SectionTitle('当前会话')),
              DropdownButton<String>(
                value: scope,
                underline: const SizedBox.shrink(),
                borderRadius: BorderRadius.circular(16),
                items: const [
                  DropdownMenuItem(value: '全课程', child: Text('全课程')),
                  DropdownMenuItem(value: '当前课时', child: Text('当前课时')),
                  DropdownMenuItem(value: '指定章节', child: Text('指定章节')),
                ],
                onChanged: (value) {
                  if (value != null) {
                    onScopeChanged(value);
                  }
                },
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            height: 370,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(24),
              boxShadow: AppTheme.insetShadow,
            ),
            child: ListView(
              children: session.messages
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
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: session.citations
                .map((item) => StatusPill(label: item, color: AppTheme.success))
                .toList(),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(hintText: '输入你的问题...'),
            onSubmitted: (_) => onSend(),
          ),
          const SizedBox(height: 12),
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
