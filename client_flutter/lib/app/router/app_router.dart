import 'package:go_router/go_router.dart';

import '../../features/course_import/course_import_page.dart';
import '../../features/course_recommend/course_recommend_page.dart';
import '../../features/handout/handout_page.dart';
import '../../features/home/home_page.dart';
import '../../features/inquiry/inquiry_page.dart';
import '../../features/parse_progress/parse_progress_page.dart';
import '../../features/qa/qa_page.dart';
import '../../features/quiz/quiz_page.dart';
import '../../features/review/review_page.dart';

class AppRouter {
  static final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const HomePage(),
      ),
      GoRoute(
        path: '/import',
        builder: (context, state) => const CourseImportPage(),
      ),
      GoRoute(
        path: '/recommend',
        builder: (context, state) => const CourseRecommendPage(),
      ),
      GoRoute(
        path: '/courses/:courseId/progress',
        builder: (context, state) => ParseProgressPage(
          courseId: state.pathParameters['courseId'] ?? '101',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/inquiry',
        builder: (context, state) => InquiryPage(
          courseId: state.pathParameters['courseId'] ?? '101',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/handout',
        builder: (context, state) => HandoutPage(
          courseId: state.pathParameters['courseId'] ?? '101',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/qa/:sessionId',
        builder: (context, state) => QaPage(
          courseId: state.pathParameters['courseId'] ?? '101',
          sessionId: state.pathParameters['sessionId'] ?? '6001',
        ),
      ),
      GoRoute(
        path: '/quizzes/:quizId',
        builder: (context, state) => QuizPage(
          quizId: state.pathParameters['quizId'] ?? '8001',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/review',
        builder: (context, state) => ReviewPage(
          courseId: state.pathParameters['courseId'] ?? '101',
        ),
      ),
    ],
  );
}
