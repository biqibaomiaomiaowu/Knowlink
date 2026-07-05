import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/course_qa/course_qa_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('loads a course session history and continues with session id',
      (tester) async {
    _useTestSurface(tester, const Size(1200, 1400));
    final api = _CourseQaFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(api)],
        child: const MaterialApp(home: CourseQaPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(api.courseSessionFetches, contains('101'));
    expect(find.text('Stored course session'), findsOneWidget);

    await tester.tap(find.text('Stored course session'));
    await tester.pumpAndSettle();

    expect(api.messageFetches, [7001]);
    expect(find.text('What is stored?'), findsOneWidget);
    expect(find.text('Stored answer'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Follow up');
    await tester.tap(find.byIcon(Icons.send_outlined));
    await tester.pumpAndSettle();

    expect(api.courseQaRequests.last.request.sessionId, 7001);
    expect(find.text('Course answer: Follow up'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('qa_new_session_button')));
    await tester.pumpAndSettle();
    expect(find.text('Stored answer'), findsNothing);

    await tester.enterText(find.byType(TextField), 'Fresh question');
    await tester.tap(find.byIcon(Icons.send_outlined));
    await tester.pumpAndSettle();

    expect(api.courseQaRequests.last.request.sessionId, isNull);
    expect(find.text('Course answer: Fresh question'), findsOneWidget);
  });

  testWidgets('course and lesson history scopes do not leak', (tester) async {
    _useTestSurface(tester, const Size(1200, 1400));
    final api = _CourseQaFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(api)],
        child: const MaterialApp(
          home: CourseQaPage(courseId: '101', lessonId: '2'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(api.lessonSessionFetches, contains('101/2'));
    expect(find.text('Stored lesson session'), findsOneWidget);

    await tester.tap(find.text('Stored lesson session'));
    await tester.pumpAndSettle();
    expect(api.messageFetches, [8001]);
    expect(find.text('Lesson stored question'), findsOneWidget);
    expect(find.text('Lesson stored answer'), findsOneWidget);

    await tester.tap(find.byType(ChoiceChip).first);
    await tester.pumpAndSettle();
    expect(find.text('Stored course session'), findsOneWidget);
    expect(find.text('Lesson stored answer'), findsNothing);

    await tester.tap(find.text('Stored course session'));
    await tester.pumpAndSettle();
    expect(api.messageFetches, [8001, 7001]);
    expect(find.text('Stored answer'), findsOneWidget);

    await tester.enterText(find.byType(TextField), 'Course follow up');
    await tester.tap(find.byIcon(Icons.send_outlined));
    await tester.pumpAndSettle();

    expect(api.courseQaRequests.last.request.sessionId, 7001);
    expect(api.lessonQaRequests, isEmpty);
  });

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
  final courseSessionFetches = <String>[];
  final lessonSessionFetches = <String>[];
  final messageFetches = <int>[];

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
  Future<QaSessionsModel> fetchCourseQaSessions(String courseId) async {
    courseSessionFetches.add(courseId);
    return QaSessionsModel(
      items: [
        QaSessionModel(
          sessionId: 7001,
          courseId: courseId,
          scopeType: 'course',
          title: 'Stored course session',
          lastMessageAt: DateTime.utc(2026, 4, 18, 15, 2),
        ),
      ],
    );
  }

  @override
  Future<QaSessionsModel> fetchLessonQaSessions({
    required String courseId,
    required String lessonId,
  }) async {
    lessonSessionFetches.add('$courseId/$lessonId');
    return QaSessionsModel(
      items: [
        QaSessionModel(
          sessionId: 8001,
          courseId: courseId,
          scopeType: 'lesson',
          lessonId: lessonId,
          title: 'Stored lesson session',
          lastMessageAt: DateTime.utc(2026, 4, 18, 15, 3),
        ),
      ],
    );
  }

  @override
  Future<QaSessionMessagesModel> fetchQaSessionMessages(int sessionId) async {
    messageFetches.add(sessionId);
    if (sessionId == 8001) {
      return const QaSessionMessagesModel(
        items: [
          QaMessageModel(
            sessionId: 8001,
            messageId: 1,
            role: 'user',
            contentMd: 'Lesson stored question',
            question: 'Lesson stored question',
            answerMd: '',
            citations: [],
          ),
          QaMessageModel(
            sessionId: 8001,
            messageId: 2,
            role: 'assistant',
            contentMd: 'Lesson stored answer',
            question: 'Lesson stored question',
            answerMd: 'Lesson stored answer',
            citations: [],
          ),
        ],
      );
    }
    return const QaSessionMessagesModel(
      items: [
        QaMessageModel(
          sessionId: 7001,
          messageId: 1,
          role: 'user',
          contentMd: 'What is stored?',
          question: 'What is stored?',
          answerMd: '',
          citations: [],
        ),
        QaMessageModel(
          sessionId: 7001,
          messageId: 2,
          role: 'assistant',
          contentMd: 'Stored answer',
          question: 'What is stored?',
          answerMd: 'Stored answer',
          citations: [],
        ),
      ],
    );
  }

  @override
  Future<QaMessageModel> createCourseQaMessage({
    required String courseId,
    required ScopedQaMessageRequestModel request,
  }) async {
    courseQaRequests.add(_CourseQaCall(courseId: courseId, request: request));
    return QaMessageModel(
      sessionId: request.sessionId ?? 7002,
      messageId: courseQaRequests.length,
      question: request.question,
      answerMd: request.question.startsWith('Follow up') ||
              request.question.startsWith('Fresh question') ||
              request.question.startsWith('Course follow up')
          ? 'Course answer: ${request.question}'
          : '课程回答：${request.question}',
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
      sessionId: request.sessionId ?? 8002,
      messageId: lessonQaRequests.length,
      question: request.question,
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
