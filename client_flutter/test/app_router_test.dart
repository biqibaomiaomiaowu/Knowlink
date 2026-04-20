import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/router/app_router.dart';
import 'package:knowlink_client/features/course_import/course_import_page.dart';
import 'package:knowlink_client/features/course_recommend/course_recommend_page.dart';
import 'package:knowlink_client/features/handout/handout_page.dart';
import 'package:knowlink_client/features/home/home_page.dart';
import 'package:knowlink_client/features/inquiry/inquiry_page.dart';
import 'package:knowlink_client/features/parse_progress/parse_progress_page.dart';
import 'package:knowlink_client/features/qa/qa_page.dart';
import 'package:knowlink_client/features/quiz/quiz_page.dart';
import 'package:knowlink_client/features/review/review_page.dart';

void main() {
  testWidgets('frozen routes resolve to expected pages', (tester) async {
    final router = AppRouter.createRouter();
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(
          routerConfig: router,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);

    final routes = <String, Finder>{
      '/import': find.byType(CourseImportPage),
      '/recommend': find.byType(CourseRecommendPage),
      '/courses/101/progress': find.byType(ParseProgressPage),
      '/courses/101/inquiry': find.byType(InquiryPage),
      '/courses/101/handout': find.byType(HandoutPage),
      '/quizzes/8001': find.byType(QuizPage),
      '/courses/101/review': find.byType(ReviewPage),
    };

    for (final entry in routes.entries) {
      router.go(entry.key);
      await tester.pumpAndSettle();
      expect(
        entry.value,
        findsOneWidget,
        reason: 'route ${entry.key} should resolve',
      );
    }

    router.go('/courses/205/qa/9876');
    await tester.pumpAndSettle();
    expect(find.byType(QaPage), findsOneWidget);
    expect(find.textContaining('QA'), findsOneWidget);
    expect(find.textContaining('205'), findsOneWidget);
    expect(find.textContaining('9876'), findsOneWidget);

    router.go('/quizzes/8001');
    await tester.pumpAndSettle();
    expect(find.byType(QuizPage), findsOneWidget);
    expect(find.textContaining('8001'), findsOneWidget);

    router.go('/');
    await tester.pumpAndSettle();
  });
}
