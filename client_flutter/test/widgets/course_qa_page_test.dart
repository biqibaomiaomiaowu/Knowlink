import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_qa/course_qa_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('course scope sends course QA messages only', (tester) async {
    _useTestSurface(tester, const Size(1200, 1400));
    final api = _CourseQaFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(api)],
        child: const MaterialApp(home: CourseQaPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课程问答'), findsWidgets);
    expect(find.text('课时问答'), findsOneWidget);
    expect(find.textContaining('流式输出'), findsNothing);

    await tester.enterText(find.byType(TextField), '这门课的重点是什么？');
    await tester.tap(find.byTooltip('发送'));
    await tester.pumpAndSettle();

    expect(api.courseQaRequests, hasLength(1));
    expect(api.courseQaRequests.single.courseId, '101');
    expect(api.courseQaRequests.single.request.question, '这门课的重点是什么？');
    expect(api.courseQaRequests.single.request.scopeType, 'course');
    expect(api.courseQaRequests.single.request.courseId, '101');
    expect(api.courseQaRequests.single.request.lessonId, isNull);
    expect(api.lessonQaRequests, isEmpty);
    expect(find.text('课程回答：这门课的重点是什么？'), findsOneWidget);
  });

  testWidgets('lesson id preselects lesson scope and keeps sessions separate',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1400));
    final api = _CourseQaFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(api)],
        child: const MaterialApp(
          home: CourseQaPage(courseId: '101', lessonId: 'l-2'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('课时问答'), findsWidgets);
    expect(find.textContaining('课时 l-2'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '这一课怎么复习？');
    await tester.tap(find.byTooltip('发送'));
    await tester.pumpAndSettle();

    expect(api.lessonQaRequests, hasLength(1));
    expect(api.lessonQaRequests.single.courseId, '101');
    expect(api.lessonQaRequests.single.lessonId, 'l-2');
    expect(api.lessonQaRequests.single.request.question, '这一课怎么复习？');
    expect(api.lessonQaRequests.single.request.scopeType, 'lesson');
    expect(api.lessonQaRequests.single.request.courseId, '101');
    expect(api.lessonQaRequests.single.request.lessonId, 'l-2');
    expect(api.courseQaRequests, isEmpty);
    expect(find.text('课时回答：这一课怎么复习？'), findsOneWidget);

    await tester.tap(find.widgetWithText(ChoiceChip, '课程问答'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '切回课程范围');
    await tester.tap(find.byTooltip('发送'));
    await tester.pumpAndSettle();

    expect(api.courseQaRequests, hasLength(1));
    expect(api.courseQaRequests.single.request.scopeType, 'course');
    expect(api.lessonQaRequests, hasLength(1));
    expect(find.text('课时回答：这一课怎么复习？'), findsNothing);
    expect(find.text('课程回答：切回课程范围'), findsOneWidget);
  });
}

void _useTestSurface(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _CourseQaFakeApiClient extends ApiClient {
  final courseQaRequests = <_CourseQaCall>[];
  final lessonQaRequests = <_LessonQaCall>[];

  @override
  Future<PlaceholderEntryModel> fetchCourseQaPlaceholder(
    String courseId,
  ) async {
    return const PlaceholderEntryModel(
      key: 'course_qa',
      title: '课程问答',
      status: 'ready',
      message: '可以围绕整门课程提问。',
    );
  }

  @override
  Future<PlaceholderEntryModel> fetchLessonQaPlaceholder({
    required String courseId,
    required String lessonId,
  }) async {
    return const PlaceholderEntryModel(
      key: 'lesson_qa',
      title: '课时问答',
      status: 'ready',
      message: '可以只围绕当前课时提问。',
    );
  }

  @override
  Future<QaMessageModel> createCourseQaMessage({
    required String courseId,
    required ScopedQaMessageRequestModel request,
  }) async {
    courseQaRequests.add(_CourseQaCall(courseId: courseId, request: request));
    return QaMessageModel(
      sessionId: 7001,
      messageId: courseQaRequests.length,
      answerMd: '课程回答：${request.question}',
      citations: const [],
    );
  }

  @override
  Future<QaMessageModel> createLessonQaMessage({
    required String courseId,
    required String lessonId,
    required ScopedQaMessageRequestModel request,
  }) async {
    lessonQaRequests.add(
      _LessonQaCall(
        courseId: courseId,
        lessonId: lessonId,
        request: request,
      ),
    );
    return QaMessageModel(
      sessionId: 8001,
      messageId: lessonQaRequests.length,
      answerMd: '课时回答：${request.question}',
      citations: const [],
    );
  }
}

class _CourseQaCall {
  const _CourseQaCall({required this.courseId, required this.request});

  final String courseId;
  final ScopedQaMessageRequestModel request;
}

class _LessonQaCall {
  const _LessonQaCall({
    required this.courseId,
    required this.lessonId,
    required this.request,
  });

  final String courseId;
  final String lessonId;
  final ScopedQaMessageRequestModel request;
}
