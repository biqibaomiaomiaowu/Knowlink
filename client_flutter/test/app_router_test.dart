import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/router/app_router.dart';
import 'package:knowlink_client/features/course_library/course_library_page.dart';
import 'package:knowlink_client/features/course_qa/course_qa_page.dart';
import 'package:knowlink_client/features/course_workbench/course_workbench_page.dart';
import 'package:knowlink_client/features/home/home_page.dart';
import 'package:knowlink_client/features/lesson_detail/lesson_detail_page.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';
import 'package:knowlink_client/features/review/review_page.dart';

void main() {
  testWidgets('soft ui routes resolve to retained pages', (tester) async {
    final router = AppRouter.createRouter();

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);

    final routes = <String, Type>{
      '/courses': CourseLibraryPage,
      '/courses/101': CourseWorkbenchPage,
      '/courses/101/lessons/l-2': LessonDetailPage,
      '/courses/101/test': QuizPage,
      '/courses/101/chat': CourseQaPage,
      '/courses/101/review': ReviewPage,
    };

    for (final entry in routes.entries) {
      router.go(entry.key);
      await tester.pumpAndSettle();
      expect(
        find.byType(entry.value),
        findsOneWidget,
        reason: '${entry.key} should resolve to ${entry.value}',
      );
    }

    router.go('/courses/101/review?kind=subjective_grading');
    await tester.pumpAndSettle();
    expect(find.byType(ReviewPage), findsOneWidget);
  });

  testWidgets('removed legacy routes redirect into retained scope', (
    tester,
  ) async {
    final router = AppRouter.createRouter();

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    final redirects = <String, Type>{
      '/import': CourseLibraryPage,
      '/recommend': HomePage,
      '/courses/101/progress': CourseWorkbenchPage,
      '/courses/101/inquiry': CourseQaPage,
      '/courses/101/qa': CourseQaPage,
      '/courses/101/quiz': QuizPage,
      '/courses/101/handout': LessonDetailPage,
      '/courses/101/exports': ReviewPage,
      '/quizzes/test-1': QuizPage,
    };

    for (final entry in redirects.entries) {
      router.go(entry.key);
      await tester.pumpAndSettle();
      expect(
        find.byType(entry.value),
        findsOneWidget,
        reason: '${entry.key} should redirect to ${entry.value}',
      );
    }
  });
}
