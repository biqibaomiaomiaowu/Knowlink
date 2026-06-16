import 'package:go_router/go_router.dart';

import '../../features/course_library/course_library_page.dart';
import '../../features/course_qa/course_qa_page.dart';
import '../../features/course_workbench/course_workbench_page.dart';
import '../../features/home/home_page.dart';
import '../../features/lesson_detail/lesson_detail_page.dart';
import '../../features/quiz/quiz_page.dart';
import '../../features/review/review_page.dart';

class AppRouter {
  static GoRouter createRouter() {
    return GoRouter(
      routes: [
        GoRoute(
          path: '/',
          builder: (context, state) => const HomePage(),
        ),
        GoRoute(
          path: '/courses',
          builder: (context, state) => const CourseLibraryPage(),
        ),
        GoRoute(
          path: '/courses/:courseId',
          builder: (context, state) {
            return CourseWorkbenchPage(
              courseId: state.pathParameters['courseId']!,
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/lessons/:lessonId',
          builder: (context, state) {
            return LessonDetailPage(
              courseId: state.pathParameters['courseId']!,
              lessonId: state.pathParameters['lessonId']!,
            );
          },
        ),
        GoRoute(
          path: '/courses/:courseId/test',
          builder: (context, state) {
            return QuizPage(courseId: state.pathParameters['courseId']!);
          },
        ),
        GoRoute(
          path: '/courses/:courseId/chat',
          builder: (context, state) {
            return CourseQaPage(courseId: state.pathParameters['courseId']!);
          },
        ),
        GoRoute(
          path: '/courses/:courseId/review',
          builder: (context, state) {
            return ReviewPage(courseId: state.pathParameters['courseId']!);
          },
        ),
        GoRoute(
          path: '/import',
          redirect: (_, __) => '/courses',
        ),
        GoRoute(
          path: '/recommend',
          redirect: (_, __) => '/',
        ),
        GoRoute(
          path: '/courses/:courseId/progress',
          redirect: (_, state) => '/courses/${state.pathParameters['courseId']}',
        ),
        GoRoute(
          path: '/courses/:courseId/inquiry',
          redirect: (_, state) =>
              '/courses/${state.pathParameters['courseId']}/chat',
        ),
        GoRoute(
          path: '/courses/:courseId/qa',
          redirect: (_, state) =>
              '/courses/${state.pathParameters['courseId']}/chat',
        ),
        GoRoute(
          path: '/courses/:courseId/quiz',
          redirect: (_, state) =>
              '/courses/${state.pathParameters['courseId']}/test',
        ),
        GoRoute(
          path: '/courses/:courseId/handout',
          redirect: (_, state) =>
              '/courses/${state.pathParameters['courseId']}/lessons/lesson-1',
        ),
        GoRoute(
          path: '/courses/:courseId/exports',
          redirect: (_, state) =>
              '/courses/${state.pathParameters['courseId']}/review',
        ),
        GoRoute(
          path: '/quizzes/:quizId',
          redirect: (_, __) => '/courses/course-1/test',
        ),
      ],
      errorBuilder: (context, state) => const HomePage(),
    );
  }

  static final router = createRouter();
}
