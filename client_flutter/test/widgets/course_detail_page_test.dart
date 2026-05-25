import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_detail/course_detail_page.dart';
import 'package:knowlink_client/shared/models/course_summary.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course detail shows status and learning entry actions',
      (tester) async {
    tester.view.physicalSize = const Size(1200, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final fakeApiClient = _FakeCourseDetailApiClient();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(fakeApiClient)],
    );
    addTearDown(container.dispose);

    final router = GoRouter(
      routes: [
        GoRoute(
          path: '/courses/:courseId',
          builder: (context, state) => CourseDetailPage(
            courseId: state.pathParameters['courseId']!,
          ),
        ),
        GoRoute(
          path: '/courses/:courseId/progress',
          builder: (_, __) => const Text('progress-route'),
        ),
      ],
    );

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    router.go('/courses/101');
    await tester.pumpAndSettle();

    expect(find.text('课程 101'), findsOneWidget);
    expect(find.textContaining('learning_ready'), findsOneWidget);
    expect(find.widgetWithText(OutlinedButton, '进入解析'), findsOneWidget);

    await tester.tap(find.widgetWithText(OutlinedButton, '进入解析'));
    await tester.pumpAndSettle();

    expect(find.text('progress-route'), findsOneWidget);
  });

  testWidgets('course detail can switch current course', (tester) async {
    final fakeApiClient = _FakeCourseDetailApiClient();
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(fakeApiClient)],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: CourseDetailPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilledButton, '设为当前课程'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.switchedCourseIds, ['101']);
    expect(container.read(courseFlowProvider).courseId, '101');
  });

  testWidgets('course detail stays readable when current course fails',
      (tester) async {
    final fakeApiClient = _FakeCourseDetailApiClient(
      currentCourseError: StateError('no current course'),
    );
    final container = ProviderContainer(
      overrides: [apiClientProvider.overrideWithValue(fakeApiClient)],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: CourseDetailPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课程 101'), findsOneWidget);
    expect(find.textContaining('课程详情加载失败'), findsNothing);
    expect(find.widgetWithText(FilledButton, '设为当前课程'), findsOneWidget);
  });
}

class _FakeCourseDetailApiClient extends ApiClient {
  _FakeCourseDetailApiClient({this.currentCourseError});

  final Object? currentCourseError;
  final switchedCourseIds = <String>[];

  @override
  Future<CourseSummaryModel> fetchCourse(String courseId) async {
    return _course(int.parse(courseId));
  }

  @override
  Future<CourseSummaryModel> fetchCurrentCourse() async {
    final error = currentCourseError;
    if (error != null) {
      throw error;
    }
    return _course(202);
  }

  @override
  Future<CourseSummaryModel> switchCurrentCourse(String courseId) async {
    switchedCourseIds.add(courseId);
    return _course(int.parse(courseId));
  }

  CourseSummaryModel _course(int courseId) {
    return CourseSummaryModel.fromJson({
      'courseId': courseId,
      'title': '课程 $courseId',
      'entryType': 'recommendation',
      'catalogId': 'math-final-01',
      'lifecycleStatus': 'learning_ready',
      'pipelineStage': 'handout',
      'pipelineStatus': 'succeeded',
      'updatedAt': '2026-05-25T10:00:00+08:00',
    });
  }
}
