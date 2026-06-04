import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/course_lesson_models.dart';
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
  late Future<PlaceholderEntryModel> _placeholderFuture;

  bool get _isLessonScope => widget.lessonId != null;

  @override
  void initState() {
    super.initState();
    _placeholderFuture = _loadPlaceholder();
  }

  @override
  void didUpdateWidget(covariant CourseQaPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId ||
        oldWidget.lessonId != widget.lessonId) {
      _placeholderFuture = _loadPlaceholder();
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: _isLessonScope ? '本节 QA' : '全课程 QA',
      activeTab: KnowLinkTab.inquiry,
      courseId: widget.courseId,
      body: FutureBuilder<PlaceholderEntryModel>(
        future: _placeholderFuture,
        builder: (context, snapshot) {
          final placeholder = snapshot.data ??
              PlaceholderEntryModel(
                key: _isLessonScope ? 'lesson_qa' : 'course_qa',
                title: _isLessonScope ? '本节 QA' : '全课程 QA',
                status: snapshot.connectionState == ConnectionState.waiting
                    ? 'generating'
                    : 'placeholder',
                message: snapshot.error?.toString() ?? '暂无会话',
              );
          return _QaLayout(
            courseId: widget.courseId,
            lessonId: widget.lessonId,
            placeholder: placeholder,
          );
        },
      ),
    );
  }

  Future<PlaceholderEntryModel> _loadPlaceholder() {
    final api = ref.read(courseLessonApiProvider);
    if (_isLessonScope) {
      return api.fetchLessonQaPlaceholder(
        courseId: widget.courseId,
        lessonId: widget.lessonId!,
      );
    }
    return api.fetchCourseQaPlaceholder(widget.courseId);
  }
}

class _QaLayout extends StatelessWidget {
  const _QaLayout({
    required this.courseId,
    required this.lessonId,
    required this.placeholder,
  });

  final String courseId;
  final String? lessonId;
  final PlaceholderEntryModel placeholder;

  bool get _isLessonScope => lessonId != null;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 820;
        final history = _HistoryPanel(isLessonScope: _isLessonScope);
        final chat = _ChatPanel(
          courseId: courseId,
          lessonId: lessonId,
          placeholder: placeholder,
        );
        if (wide) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SizedBox(width: 280, child: history),
              const SizedBox(width: 14),
              Expanded(child: chat),
            ],
          );
        }
        return Column(
          children: [
            SizedBox(height: 150, child: history),
            const SizedBox(height: 12),
            Expanded(child: chat),
          ],
        );
      },
    );
  }
}

class _HistoryPanel extends StatelessWidget {
  const _HistoryPanel({required this.isLessonScope});

  final bool isLessonScope;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '历史会话',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: ListView(
              children: [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.chat_bubble_outline),
                  title: Text(isLessonScope ? '本节问题' : '全课程问题'),
                  subtitle: const Text('暂无历史消息'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatPanel extends StatelessWidget {
  const _ChatPanel({
    required this.courseId,
    required this.lessonId,
    required this.placeholder,
  });

  final String courseId;
  final String? lessonId;
  final PlaceholderEntryModel placeholder;

  @override
  Widget build(BuildContext context) {
    final scopeLabel = lessonId == null
        ? '当前范围：全课程 $courseId'
        : '当前范围：课程 $courseId / 课时 $lessonId';
    return SectionCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  scopeLabel,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              StatusPill(label: placeholder.status),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                border: Border.all(color: AppTheme.line),
                borderRadius: BorderRadius.circular(8),
              ),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _AnswerBubble(
                    title: placeholder.title,
                    message: placeholder.message.isEmpty
                        ? '此入口已预留，等待后端会话返回。'
                        : placeholder.message,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            minLines: 3,
            maxLines: 5,
            decoration: InputDecoration(
              hintText: lessonId == null ? '向整门课程提问' : '只向当前课时提问',
              border: const OutlineInputBorder(),
              suffixIcon: const IconButton(
                tooltip: '发送',
                onPressed: null,
                icon: Icon(Icons.send_outlined),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AnswerBubble extends StatelessWidget {
  const _AnswerBubble({
    required this.title,
    required this.message,
  });

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
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
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                Text(message),
                const SizedBox(height: 10),
                const Text(
                  '引用：等待后端返回结构化 citation',
                  style: TextStyle(
                    color: AppTheme.muted,
                    fontWeight: FontWeight.w700,
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
