import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
import '../../shared/models/handout_models.dart';
import '../../shared/providers/course_flow_providers.dart';
import '../../shared/providers/course_qa_provider.dart';
import '../../shared/services/course_lesson_api.dart';

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
  final _questionController = TextEditingController();

  late String _selectedCourseId;
  late Future<PlaceholderEntryModel> _coursePlaceholderFuture;
  late Future<List<CourseLibraryItemModel>> _courseOptionsFuture;

  @override
  void initState() {
    super.initState();
    _selectedCourseId = widget.courseId;
    _loadCourseOptions();
    _loadPlaceholderFor(_selectedCourseId);
    _loadSessionsFor(_selectedCourseId);
  }

  @override
  void didUpdateWidget(covariant CourseQaPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _selectedCourseId = widget.courseId;
      _questionController.clear();
      _loadPlaceholderFor(_selectedCourseId);
      _loadSessionsFor(_selectedCourseId);
    }
  }

  @override
  void dispose() {
    _questionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const title = '课程问答';
    final scopeArgs = _scopeArgsFor(_selectedCourseId);
    final qaState = ref.watch(courseQaProvider(scopeArgs));
    return AppScaffold(
      title: title,
      activeTab: KnowLinkTab.inquiry,
      courseId: _selectedCourseId,
      body: FutureBuilder<PlaceholderEntryModel>(
        future: _coursePlaceholderFuture,
        builder: (context, snapshot) {
          final placeholder = snapshot.data ??
              PlaceholderEntryModel(
                key: 'course_qa',
                title: title,
                status: snapshot.connectionState == ConnectionState.waiting
                    ? 'loading'
                    : 'ready',
                message:
                    snapshot.hasError ? '暂时无法加载历史会话，可以继续发起新问题。' : '还没有问答记录。',
              );
          return _QaLayout(
            courseId: _selectedCourseId,
            courseOptionsFuture: _courseOptionsFuture,
            placeholder: placeholder,
            qaState: qaState,
            questionController: _questionController,
            onCourseChanged: _handleCourseChanged,
            onCourseOptionsRetry: _reloadCourseOptions,
            onNewSession: () {
              ref.read(courseQaProvider(scopeArgs).notifier).startNewSession();
            },
            onSessionSelected: (session) {
              ref
                  .read(courseQaProvider(scopeArgs).notifier)
                  .selectSession(session.sessionId);
            },
            onSubmit: _submitQuestion,
          );
        },
      ),
    );
  }

  void _loadCourseOptions() {
    _courseOptionsFuture =
        ref.read(courseLessonApiProvider).fetchCourseLibrary();
  }

  void _loadPlaceholderFor(String courseId) {
    _coursePlaceholderFuture =
        ref.read(courseLessonApiProvider).fetchCourseQaPlaceholder(courseId);
  }

  void _reloadCourseOptions() {
    setState(_loadCourseOptions);
  }

  void _handleCourseChanged(String courseId) {
    if (courseId == _selectedCourseId) {
      return;
    }
    final placeholderFuture =
        ref.read(courseLessonApiProvider).fetchCourseQaPlaceholder(courseId);
    setState(() {
      _selectedCourseId = courseId;
      _coursePlaceholderFuture = placeholderFuture;
      _questionController.clear();
    });
    ref.read(courseFlowProvider.notifier).startCourse(courseId);
    _loadSessionsFor(courseId);
    _goToCourseQa(courseId);
  }

  Future<void> _submitQuestion() async {
    final question = _questionController.text.trim();
    if (question.isEmpty) {
      return;
    }

    _questionController.clear();
    await ref
        .read(courseQaProvider(_scopeArgsFor(_selectedCourseId)).notifier)
        .submitQuestion(question);
  }

  QaScopeArgs _scopeArgsFor(String courseId) {
    return QaScopeArgs(
      courseId: courseId,
      scopeType: 'course',
    );
  }

  void _loadSessionsFor(String courseId) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _selectedCourseId == courseId) {
        ref
            .read(courseQaProvider(_scopeArgsFor(courseId)).notifier)
            .loadSessions();
      }
    });
  }

  void _goToCourseQa(String courseId) {
    try {
      context.go('/courses/$courseId/qa');
    } catch (_) {
      // Widget tests can mount this page without a router.
    }
  }
}

class _QaLayout extends StatelessWidget {
  const _QaLayout({
    required this.courseId,
    required this.courseOptionsFuture,
    required this.placeholder,
    required this.qaState,
    required this.questionController,
    required this.onCourseChanged,
    required this.onCourseOptionsRetry,
    required this.onNewSession,
    required this.onSessionSelected,
    required this.onSubmit,
  });

  final String courseId;
  final Future<List<CourseLibraryItemModel>> courseOptionsFuture;
  final PlaceholderEntryModel placeholder;
  final CourseQaState qaState;
  final TextEditingController questionController;
  final ValueChanged<String> onCourseChanged;
  final VoidCallback onCourseOptionsRetry;
  final VoidCallback onNewSession;
  final ValueChanged<QaSessionModel> onSessionSelected;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 860;
        final sidePanel = _ScopePanel(
          courseId: courseId,
          courseOptionsFuture: courseOptionsFuture,
          qaState: qaState,
          onCourseChanged: onCourseChanged,
          onCourseOptionsRetry: onCourseOptionsRetry,
          onNewSession: onNewSession,
          onSessionSelected: onSessionSelected,
        );
        final chatPanel = _ChatPanel(
          courseId: courseId,
          placeholder: placeholder,
          qaState: qaState,
          questionController: questionController,
          onSubmit: onSubmit,
        );
        if (wide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(width: 280, child: sidePanel),
              const SizedBox(width: 14),
              Expanded(child: chatPanel),
            ],
          );
        }
        final chatHeight =
            constraints.maxHeight > 760 ? constraints.maxHeight - 324 : 430.0;
        return SingleChildScrollView(
          child: Column(
            children: [
              SizedBox(height: 360, child: sidePanel),
              const SizedBox(height: 12),
              SizedBox(height: chatHeight, child: chatPanel),
            ],
          ),
        );
      },
    );
  }
}

class _ScopePanel extends StatelessWidget {
  const _ScopePanel({
    required this.courseId,
    required this.courseOptionsFuture,
    required this.qaState,
    required this.onCourseChanged,
    required this.onCourseOptionsRetry,
    required this.onNewSession,
    required this.onSessionSelected,
  });

  final String courseId;
  final Future<List<CourseLibraryItemModel>> courseOptionsFuture;
  final CourseQaState qaState;
  final ValueChanged<String> onCourseChanged;
  final VoidCallback onCourseOptionsRetry;
  final VoidCallback onNewSession;
  final ValueChanged<QaSessionModel> onSessionSelected;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '问答范围',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ChoiceChip(
                label: const Text('课程问答'),
                selected: true,
                onSelected: (_) {},
              ),
            ],
          ),
          const SizedBox(height: 16),
          FutureBuilder<List<CourseLibraryItemModel>>(
            future: courseOptionsFuture,
            builder: (context, snapshot) {
              if (snapshot.hasError && !snapshot.hasData) {
                return _CourseSelectorError(
                  selectedCourseId: courseId,
                  onRetry: onCourseOptionsRetry,
                );
              }
              return _CourseSelector(
                selectedCourseId: courseId,
                courses: snapshot.data ?? const <CourseLibraryItemModel>[],
                loading: snapshot.connectionState == ConnectionState.waiting,
                onChanged: onCourseChanged,
              );
            },
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Sessions',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              IconButton(
                key: const ValueKey('qa_new_session_button'),
                tooltip: 'New session',
                onPressed: onNewSession,
                icon: const Icon(Icons.add_comment_outlined),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Expanded(
            child: _SessionList(
              sessions: qaState.sessions,
              activeSessionId: qaState.activeSessionId,
              onSessionSelected: onSessionSelected,
            ),
          ),
        ],
      ),
    );
  }
}

class _SessionList extends StatelessWidget {
  const _SessionList({
    required this.sessions,
    required this.activeSessionId,
    required this.onSessionSelected,
  });

  final AsyncValue<List<QaSessionModel>> sessions;
  final int? activeSessionId;
  final ValueChanged<QaSessionModel> onSessionSelected;

  @override
  Widget build(BuildContext context) {
    return sessions.when(
      loading: () => const Center(
        child: SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      error: (error, stackTrace) => const Text(
        'Failed to load sessions',
        style: TextStyle(
          color: Color(0xFFB91C1C),
          fontWeight: FontWeight.w700,
        ),
      ),
      data: (items) {
        if (items.isEmpty) {
          return const Text(
            'No sessions yet',
            style: TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
            ),
          );
        }
        return ListView.separated(
          padding: EdgeInsets.zero,
          itemCount: items.length,
          separatorBuilder: (context, index) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            final session = items[index];
            final active = session.sessionId == activeSessionId;
            return InkWell(
              borderRadius: BorderRadius.circular(8),
              onTap: () => onSessionSelected(session),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: active
                      ? const Color(0xFFEFF6FF)
                      : const Color(0xFFF8FAFC),
                  border: Border.all(
                    color: active ? AppTheme.brandBlue : AppTheme.line,
                  ),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Text(
                    session.displayTitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: active ? AppTheme.brandBlue : AppTheme.ink,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _CourseSelector extends StatelessWidget {
  const _CourseSelector({
    required this.selectedCourseId,
    required this.courses,
    required this.loading,
    required this.onChanged,
  });

  final String selectedCourseId;
  final List<CourseLibraryItemModel> courses;
  final bool loading;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final options = _courseOptionsWithSelected(courses, selectedCourseId);
    final canSelect = !loading && options.length > 1;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xFFEFF6FF),
        border: Border.all(color: AppTheme.brandBlue),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(Icons.school_outlined, color: AppTheme.brandBlue),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '课程',
                    style: TextStyle(
                      color: AppTheme.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      key: const ValueKey('qa_course_selector'),
                      value: selectedCourseId,
                      isExpanded: true,
                      icon: const Icon(
                        Icons.keyboard_arrow_down_rounded,
                        color: AppTheme.muted,
                      ),
                      dropdownColor: AppTheme.surface,
                      style: const TextStyle(
                        color: AppTheme.ink,
                        fontWeight: FontWeight.w800,
                      ),
                      items: [
                        for (final option in options)
                          DropdownMenuItem<String>(
                            value: option.courseId,
                            child: Text(
                              option.title,
                              key: ValueKey(
                                'qa_course_option_${option.courseId}',
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                      ],
                      onChanged: canSelect
                          ? (value) {
                              if (value != null) {
                                onChanged(value);
                              }
                            }
                          : null,
                    ),
                  ),
                ],
              ),
            ),
            if (loading) ...[
              const SizedBox(width: 10),
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _CourseSelectorError extends StatelessWidget {
  const _CourseSelectorError({
    required this.selectedCourseId,
    required this.onRetry,
  });

  final String selectedCourseId;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        border: Border.all(color: AppTheme.line),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(Icons.school_outlined, color: AppTheme.muted),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '课程',
                    style: TextStyle(
                      color: AppTheme.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '课程 $selectedCourseId',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            IconButton(
              tooltip: '重新加载课程',
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
      ),
    );
  }
}

class _CourseOption {
  const _CourseOption({
    required this.courseId,
    required this.title,
  });

  final String courseId;
  final String title;
}

List<_CourseOption> _courseOptionsWithSelected(
  List<CourseLibraryItemModel> courses,
  String selectedCourseId,
) {
  final options = [
    for (final course in courses)
      _CourseOption(courseId: course.courseId, title: course.title),
  ];
  final hasSelected =
      options.any((option) => option.courseId == selectedCourseId);
  if (hasSelected) {
    return options;
  }
  return [
    _CourseOption(courseId: selectedCourseId, title: '课程 $selectedCourseId'),
    ...options,
  ];
}

class _ChatPanel extends StatelessWidget {
  const _ChatPanel({
    required this.courseId,
    required this.placeholder,
    required this.qaState,
    required this.questionController,
    required this.onSubmit,
  });

  final String courseId;
  final PlaceholderEntryModel placeholder;
  final CourseQaState qaState;
  final TextEditingController questionController;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final scopeText = '当前范围：课程 $courseId';
    const hintText = '向整门课程提问';
    final messages = qaState.entries;
    final isSubmitting = qaState.submit.isLoading;
    final submitError = qaState.submit.hasError ? qaState.submit.error : null;

    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            '课程问答',
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            scopeText,
            style: const TextStyle(
              color: AppTheme.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                border: Border.all(color: AppTheme.line),
                borderRadius: BorderRadius.circular(8),
              ),
              child: messages.isEmpty
                  ? _EmptyQaState(placeholder: placeholder)
                  : ListView.separated(
                      padding: const EdgeInsets.all(16),
                      itemCount: messages.length,
                      separatorBuilder: (context, index) =>
                          const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        return _MessagePair(message: messages[index]);
                      },
                    ),
            ),
          ),
          if (submitError != null) ...[
            const SizedBox(height: 10),
            Text(
              '提交 QA 失败：$submitError',
              style: const TextStyle(
                color: Color(0xFFB91C1C),
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: questionController,
                  minLines: 2,
                  maxLines: 4,
                  textInputAction: TextInputAction.newline,
                  decoration: const InputDecoration(
                    hintText: hintText,
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              SizedBox(
                width: 52,
                height: 52,
                child: IconButton.filled(
                  tooltip: '发送',
                  onPressed: isSubmitting ? null : onSubmit,
                  icon: isSubmitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.send_outlined),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _EmptyQaState extends StatelessWidget {
  const _EmptyQaState({required this.placeholder});

  final PlaceholderEntryModel placeholder;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.forum_outlined,
                color: AppTheme.brandBlue,
                size: 34,
              ),
              const SizedBox(height: 12),
              Text(
                placeholder.title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                placeholder.message.isEmpty ? '还没有问答记录。' : placeholder.message,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MessagePair extends StatelessWidget {
  const _MessagePair({required this.message});

  final CourseQaEntry message;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerRight,
          child: _QuestionBubble(question: message.question),
        ),
        const SizedBox(height: 8),
        Align(
          alignment: Alignment.centerLeft,
          child: _AnswerBubble(message: message),
        ),
      ],
    );
  }
}

class _QuestionBubble extends StatelessWidget {
  const _QuestionBubble({required this.question});

  final String question;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 620),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppTheme.brandBlue,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Text(
            question,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ),
    );
  }
}

class _AnswerBubble extends StatelessWidget {
  const _AnswerBubble({required this.message});

  final CourseQaEntry message;

  @override
  Widget build(BuildContext context) {
    final answer = message.answer;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 620),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: AppTheme.line),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '回答',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              if (message.errorText != null)
                Text(
                  message.errorText!,
                  style: const TextStyle(
                    color: Color(0xFFB91C1C),
                    fontWeight: FontWeight.w700,
                  ),
                )
              else if (answer == null)
                const Text(
                  '正在生成回答...',
                  style: TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w700,
                  ),
                )
              else ...[
                Text(answer.answerMd),
                if (answer.citations.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final citation in answer.citations)
                        Chip(
                          label: Text(
                            '${citation.refLabel} ${citation.locatorText}',
                          ),
                        ),
                    ],
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}
