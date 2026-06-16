import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/app/router/app_router.dart';
import 'package:knowlink_client/features/course_recommend/course_recommend_page.dart';
import 'package:knowlink_client/features/home/home_page.dart';

void main() {
  testWidgets('legacy recommendation route is no longer a retained page', (
    tester,
  ) async {
    final router = AppRouter.createRouter();

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    router.go('/recommend');
    await tester.pumpAndSettle();

    expect(find.byType(HomePage), findsOneWidget);
    expect(find.byType(CourseRecommendPage), findsNothing);
    expect(find.text('智能课程推荐'), findsNothing);
  });
}
