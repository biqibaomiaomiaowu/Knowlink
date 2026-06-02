import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/course_exports/course_exports_page.dart';
import '../../features/course_graph/course_graph_page.dart';
import '../../features/course_import/course_import_page.dart';
import '../../features/course_library/course_library_page.dart';
import '../../features/course_qa/course_qa_page.dart';
import '../../features/course_recommend/course_recommend_page.dart';
import '../../features/course_review/course_review_page.dart';
import '../../features/course_workbench/course_workbench_page.dart';
import '../../features/handout/handout_page.dart';
import '../../features/home/home_page.dart';
import '../../features/inquiry/inquiry_page.dart';
import '../../features/lesson_detail/lesson_detail_page.dart';
import '../../features/parse_progress/parse_progress_page.dart';
import '../../features/qa/qa_page.dart';
import '../../features/quiz/quiz_page.dart';
import '../../features/review/review_page.dart';
import '../../shared/providers/course_flow_providers.dart';

class AppRouter {
  static GoRouter createRouter() {
    return GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const HomePage(),
        ),
        GoRoute(
          path: '/import',
          builder: (context, state) {
            final courseId = state.uri.queryParameters['courseId'];
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseImportPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/recommend',
          builder: (context, state) => const CourseRecommendPage(),
        ),
        GoRoute(
          path: '/courses',
          builder: (context, state) => const CourseLibraryPage(),
        ),
        GoRoute(
          path: '/courses/:courseId',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseWorkbenchPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/settings',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseGraphPage(
                courseId: courseId,
                kind: CourseGraphPageKind.settings,
              ),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/qa',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseQaPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/graph',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseGraphPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/review',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            final reviewKind = courseReviewPageKindFromQuery(
              state.uri.queryParameters['kind'],
            );
            return _CourseFlowSync(
              courseId: courseId,
              child: reviewKind == CourseReviewPageKind.courseReview
                  ? ReviewPage(courseId: courseId)
                  : CourseReviewPage(courseId: courseId, kind: reviewKind),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/exports',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseExportsPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            final lessonId = state.pathParameters['lessonId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: LessonDetailPage(courseId: courseId, lessonId: lessonId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/qa',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            final lessonId = state.pathParameters['lessonId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseQaPage(courseId: courseId, lessonId: lessonId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/handout',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            final lessonId = state.pathParameters['lessonId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseReviewPage(
                courseId: courseId,
                lessonId: lessonId,
                kind: CourseReviewPageKind.lessonHandout,
              ),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/review',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            final lessonId = state.pathParameters['lessonId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseReviewPage(
                courseId: courseId,
                lessonId: lessonId,
                kind: CourseReviewPageKind.lessonReview,
              ),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId/graph',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            final lessonId = state.pathParameters['lessonId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: CourseGraphPage(courseId: courseId, lessonId: lessonId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/progress',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: ParseProgressPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/inquiry',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: InquiryPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/handout',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: HandoutPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/qa/:sessionId',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: QaPage(
                courseId: courseId,
                sessionId: state.pathParameters['sessionId']!,
              ),
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/quiz',
          builder: (context, state) {
            final courseId = state.pathParameters['courseId']!;
            return _CourseFlowSync(
              courseId: courseId,
              child: QuizPage(courseId: courseId),
            );
          },
        ),
        GoRoute(
          path: '/quizzes/:quizId',
          builder: (context, state) => QuizPage(
            quizId: state.pathParameters['quizId']!,
          ),
        ),
      ],
    );
  }

  static final router = createRouter();
}

class _CourseFlowSync extends ConsumerStatefulWidget {
  const _CourseFlowSync({
    required this.child,
    this.courseId,
  });

  final String? courseId;
  final Widget child;

  @override
  ConsumerState<_CourseFlowSync> createState() => _CourseFlowSyncState();
}

class _CourseFlowSyncState extends ConsumerState<_CourseFlowSync> {
  @override
  void initState() {
    super.initState();
    _scheduleSync();
  }

  @override
  void didUpdateWidget(covariant _CourseFlowSync oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.courseId != widget.courseId) {
      _scheduleSync();
    }
  }

  void _scheduleSync() {
    final courseId = widget.courseId;
    if (courseId == null || courseId.isEmpty) {
      return;
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || widget.courseId != courseId) {
        return;
      }
      ref.read(courseFlowProvider.notifier).startCourse(courseId);
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
