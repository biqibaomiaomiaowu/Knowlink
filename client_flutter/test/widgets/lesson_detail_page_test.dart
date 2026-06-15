import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/features/lesson_detail/lesson_detail_page.dart';

void main() {
  testWidgets('lesson detail shows the retained study workspace', (
    tester,
  ) async {
    _useTestSurface(tester);

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(
          home: LessonDetailPage(courseId: 'course-1', lessonId: 'lesson-1'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('栈与队列专项复习'), findsOneWidget);
    expect(find.text('主视频'), findsOneWidget);
    expect(find.text('本节 AI 问答'), findsOneWidget);
    expect(find.text('本节资料'), findsOneWidget);
    expect(find.text('本节讲义'), findsOneWidget);
    expect(find.text('进入测试'), findsOneWidget);
    expect(find.text('加入复习'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1400, 1200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}
