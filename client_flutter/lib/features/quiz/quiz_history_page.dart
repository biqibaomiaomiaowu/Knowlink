import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme/app_theme.dart';
import '../../core/widgets/app_error_view.dart';
import '../../core/widgets/app_loading_view.dart';
import '../../core/widgets/app_scaffold.dart';
import '../../core/widgets/knowlink_widgets.dart';
import '../../shared/models/quiz_models.dart';
import '../../shared/providers/quiz_provider.dart';

class CourseQuizHistoryPage extends ConsumerWidget {
  const CourseQuizHistoryPage({
    required this.courseId,
    super.key,
  });

  final String courseId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(courseQuizHistoryProvider(courseId));

    return AppScaffold(
      title: 'Quiz history',
      activeTab: KnowLinkTab.quiz,
      courseId: courseId,
      body: history.when(
        loading: () => const AppLoadingView(),
        error: (error, _) => AppErrorView(
          message: 'Quiz history failed to load: $error',
          onRetry: () => ref.invalidate(courseQuizHistoryProvider(courseId)),
        ),
        data: (items) => _QuizHistoryBody(
          courseId: courseId,
          items: items,
        ),
      ),
    );
  }
}

class _QuizHistoryBody extends StatelessWidget {
  const _QuizHistoryBody({
    required this.courseId,
    required this.items,
  });

  final String courseId;
  final List<CourseQuizHistoryItemModel> items;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const PageTitle(
            title: 'Quiz history',
            subtitle: 'Course and lesson quizzes generated for this course.',
            icon: Icons.history_rounded,
          ),
          if (items.isEmpty)
            const _EmptyHistory()
          else
            for (final item in items) ...[
              _QuizHistoryItem(
                item: item,
                onTap: () => context.go('/quizzes/${item.quizId}'),
              ),
              const SizedBox(height: 12),
            ],
        ],
      ),
    );
  }
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) {
    return const SectionCard(
      child: Text(
        'No quiz history yet.',
        style: TextStyle(
          color: AppTheme.muted,
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _QuizHistoryItem extends StatelessWidget {
  const _QuizHistoryItem({
    required this.item,
    required this.onTap,
  });

  final CourseQuizHistoryItemModel item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final attempt = item.latestAttempt;
    final scope = item.scopeType == 'lesson' && item.lessonId != null
        ? 'Lesson ${item.lessonId}'
        : 'Course';
    final scoreText = attempt == null
        ? 'No attempt'
        : '${attempt.score}/${attempt.totalScore}';

    return SectionCard(
      padding: EdgeInsets.zero,
      child: Material(
        type: MaterialType.transparency,
        child: ListTile(
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          leading: const SoftIcon(icon: Icons.quiz_outlined, size: 42),
          title: Text(
            'Quiz #${item.quizId}',
            style: const TextStyle(
              color: AppTheme.ink,
              fontSize: 17,
              fontWeight: FontWeight.w800,
            ),
          ),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                StatusPill(label: scope),
                StatusPill(label: item.status),
                StatusPill(label: '${item.questionCount} questions'),
                StatusPill(label: scoreText),
              ],
            ),
          ),
          trailing: const Icon(Icons.chevron_right_rounded),
          onTap: onTap,
        ),
      ),
    );
  }
}
