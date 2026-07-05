import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:knowlink_client/app/theme/app_theme.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/handout/handout_video_controller.dart';
import 'package:knowlink_client/features/lesson_study/lesson_study_page.dart';
import 'package:knowlink_client/shared/models/course_lesson_models.dart';
import 'package:knowlink_client/shared/models/handout_models.dart' as handouts;
import 'package:knowlink_client/shared/models/resource_upload_models.dart'
    as resources;
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('lesson study page matches prototype structure', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    expect(find.text('本节资料'), findsOneWidget);
    expect(find.text('课时测试'), findsOneWidget);
    expect(find.text('加入复习'), findsNothing);
    expect(find.text('生成讲义'), findsWidgets);
    expect(find.text('根据资料生成讲义'), findsNothing);
    expect(find.byKey(const Key('lesson_study_video_panel')), findsOneWidget);
    expect(find.byKey(const Key('lesson_study_ai_panel')), findsOneWidget);
    expect(find.byKey(const Key('lesson_study_block_panel')), findsOneWidget);

    final lessonTitleRect = tester.getRect(find.text('第 1 课：栈与队列'));
    final videoRect =
        tester.getRect(find.byKey(const Key('lesson_study_video_panel')));
    expect(lessonTitleRect.left, lessThan(videoRect.left + 12));
  });

  testWidgets('wide lesson room uses prototype two-row grid', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    final videoRect =
        tester.getRect(find.byKey(const Key('lesson_study_video_panel')));
    final blockRect =
        tester.getRect(find.byKey(const Key('lesson_study_block_panel')));
    final aiRect =
        tester.getRect(find.byKey(const Key('lesson_study_ai_panel')));

    expect(videoRect.top, moreOrLessEquals(blockRect.top, epsilon: 1));
    expect(aiRect.top, greaterThan(videoRect.bottom));
    expect(aiRect.left, moreOrLessEquals(videoRect.left, epsilon: 1));
    expect(aiRect.right, moreOrLessEquals(blockRect.right, epsilon: 1));
  });

  testWidgets('lesson outline trigger is moved into the workspace', (
    tester,
  ) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    final videoRect =
        tester.getRect(find.byKey(const Key('lesson_study_video_panel')));
    final triggerRect =
        tester.getRect(find.byKey(const Key('lesson_outline_trigger')));

    expect(triggerRect.left, greaterThanOrEqualTo(videoRect.left + 12));
    expect(triggerRect.top, lessThan(videoRect.top));
  });

  testWidgets('lesson video play button fades out after playback starts', (
    tester,
  ) async {
    _useTestSurface(tester);
    final videoControllers = <_FakeLessonStudyVideoController>[];

    await _pumpLessonStudy(
      tester,
      videoControllerFactory: (uri) {
        final controller = _FakeLessonStudyVideoController(uri);
        videoControllers.add(controller);
        return controller;
      },
    );

    final playControlFinder =
        find.byKey(const Key('lesson_video_play_control'));
    expect(playControlFinder, findsOneWidget);
    expect(
      tester.widget<AnimatedOpacity>(playControlFinder).opacity,
      1,
    );

    await tester.tap(find.byKey(const Key('lesson_video_play_toggle')));
    await tester.pump();
    expect(videoControllers.single.isPlaying, isTrue);

    await tester.pump(const Duration(milliseconds: 2600));
    expect(
      tester.widget<AnimatedOpacity>(playControlFinder).opacity,
      0,
    );
  });

  testWidgets('lesson soft-ui surfaces use prototype tokens', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    final videoCardSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_video_card_surface')),
    );
    final videoCardDecoration = videoCardSurface.decoration! as BoxDecoration;
    expect(videoCardDecoration.color, AppTheme.surface);
    expect(videoCardDecoration.borderRadius, BorderRadius.circular(32));
    expect(videoCardDecoration.boxShadow, AppTheme.shadowRaised);

    final videoSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_video_surface')),
    );
    final videoDecoration = videoSurface.decoration! as BoxDecoration;
    expect(videoDecoration.color, AppTheme.surface);
    expect(videoDecoration.borderRadius, BorderRadius.circular(32));
    expect(videoDecoration.boxShadow, AppTheme.shadowInsetLook);

    final progressBar = tester.widget<Container>(
      find.byKey(const Key('lesson_video_progress_bar')),
    );
    expect(progressBar.padding, const EdgeInsets.all(3));

    final handoutSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_handout_surface')),
    );
    final handoutDecoration = handoutSurface.decoration! as BoxDecoration;
    expect(handoutDecoration.color, AppTheme.surface);
    expect(handoutDecoration.borderRadius, BorderRadius.circular(24));
    expect(handoutDecoration.boxShadow, AppTheme.shadowInsetLook);

    final aiPanelSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_ai_panel_surface')),
    );
    final aiPanelDecoration = aiPanelSurface.decoration! as BoxDecoration;
    expect(aiPanelDecoration.color, AppTheme.surface);
    expect(aiPanelDecoration.borderRadius, BorderRadius.circular(24));
    expect(aiPanelDecoration.boxShadow, AppTheme.shadowInsetLook);

    final aiBubble = tester.widget<Container>(
      find.byKey(const Key('lesson_ai_bubble_ai_surface')),
    );
    final aiBubbleDecoration = aiBubble.decoration! as BoxDecoration;
    expect(
      aiBubbleDecoration.borderRadius,
      const BorderRadius.only(
        topLeft: Radius.circular(8),
        topRight: Radius.circular(20),
        bottomLeft: Radius.circular(20),
        bottomRight: Radius.circular(20),
      ),
    );
    expect(aiBubbleDecoration.boxShadow, AppTheme.shadowSmall);

    final aiInputSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_ai_input_surface')),
    );
    final inputDecoration = aiInputSurface.decoration! as BoxDecoration;
    expect(inputDecoration.color, AppTheme.surface);
    expect(inputDecoration.borderRadius, BorderRadius.circular(16));
    expect(inputDecoration.boxShadow, AppTheme.shadowInsetLook);

    await tester.tap(find.byTooltip('讲义目录'));
    await tester.pumpAndSettle();

    final drawerSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_outline_drawer_surface')),
    );
    final drawerDecoration = drawerSurface.decoration! as BoxDecoration;
    expect(drawerDecoration.color, AppTheme.surface);
    expect(
      drawerDecoration.borderRadius,
      const BorderRadius.only(
        topRight: Radius.circular(32),
        bottomRight: Radius.circular(32),
      ),
    );
    expect(drawerDecoration.boxShadow, AppTheme.shadowRaised);
  });

  testWidgets(
      'lesson video surface renders playback controller when URL exists',
      (tester) async {
    _useTestSurface(tester);
    final videoControllers = <_FakeLessonStudyVideoController>[];

    await _pumpLessonStudy(
      tester,
      videoControllerFactory: (uri) {
        final controller = _FakeLessonStudyVideoController(uri);
        videoControllers.add(controller);
        return controller;
      },
    );

    expect(videoControllers, hasLength(1));
    expect(
      videoControllers.single.uri.toString(),
      'https://cdn.test/501.mp4',
    );
    expect(find.byKey(const Key('lesson_video_player')), findsOneWidget);
    expect(find.text('https://cdn.test/501.mp4'), findsOneWidget);
  });

  testWidgets('lesson video listener persists playback progress', (
    tester,
  ) async {
    _useTestSurface(tester);
    final apiClient = _LessonStudyPageFakeApiClient();
    final videoControllers = <_FakeLessonStudyVideoController>[];

    await _pumpLessonStudy(
      tester,
      apiClient: apiClient,
      videoControllerFactory: (uri) {
        final controller = _FakeLessonStudyVideoController(uri);
        videoControllers.add(controller);
        return controller;
      },
    );

    expect(videoControllers, hasLength(1));
    videoControllers.single.jumpTo(const Duration(seconds: 182));
    await tester.pump();
    await tester.pump(const Duration(seconds: 2));
    await tester.pump();

    expect(apiClient.progressUpdates, isNotEmpty);
    expect(apiClient.progressUpdates.last['lastPositionSec'], 182);
    expect(apiClient.progressUpdates.last['lastHandoutBlockId'], '4201');
  });

  testWidgets('lesson outline child seeks video to child start time', (
    tester,
  ) async {
    _useTestSurface(tester);
    final videoControllers = <_FakeLessonStudyVideoController>[];

    await _pumpLessonStudy(
      tester,
      videoControllerFactory: (uri) {
        final controller = _FakeLessonStudyVideoController(uri);
        videoControllers.add(controller);
        return controller;
      },
    );

    expect(videoControllers, hasLength(1));
    videoControllers.single.seekPositions.clear();

    await tester.tap(find.byKey(const Key('lesson_outline_trigger')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('lesson_outline_child_4202')));
    await tester.pumpAndSettle();

    expect(
      videoControllers.single.seekPositions,
      contains(const Duration(seconds: 90)),
    );
  });

  testWidgets('lesson handout block renders markdown structure', (
    tester,
  ) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(
      tester,
      firstBlockContentMd: '''
### 栈定义

- 只允许在一端插入和删除
- **队列** 从队尾入队、队头出队

代码/公式文本：`top = n - 1`
''',
    );

    final markdown = find.descendant(
      of: find.byKey(const Key('lesson_handout_surface')),
      matching: find.byType(MarkdownBody),
    );

    expect(markdown, findsOneWidget);
    final markdownBody = tester.widget<MarkdownBody>(markdown);
    expect(markdownBody.data, contains('### 栈定义'));
    expect(markdownBody.data, contains('- 只允许在一端插入和删除'));
    expect(markdownBody.data, contains('**队列**'));
    expect(markdownBody.data, contains('`top = n - 1`'));
    expect(find.textContaining('### 栈定义'), findsNothing);
    expect(find.textContaining('- 只允许在一端插入和删除'), findsNothing);
  });

  testWidgets('lesson outline drawer opens from left trigger', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    expect(find.byKey(const Key('lesson_outline_drawer')), findsNothing);

    await tester.tap(find.byTooltip('讲义目录'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('lesson_outline_drawer')), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_outline_drawer')),
        matching: find.byType(ListTile),
      ),
      findsNothing,
    );
    final outlineChild = tester.widget<Container>(
      find.byKey(const Key('lesson_outline_child_4201')),
    );
    final outlineChildDecoration = outlineChild.decoration! as BoxDecoration;
    expect(outlineChildDecoration.color, AppTheme.brandBlue);
    expect(outlineChildDecoration.borderRadius, BorderRadius.circular(16));
    expect(outlineChildDecoration.boxShadow, AppTheme.shadowAccent);
    expect(find.text('第一章'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_outline_drawer')),
        matching: find.text('1.1'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_outline_drawer')),
        matching: find.text('极限定义'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('lesson materials open in blurred dialog', (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    await tester.tap(find.text('本节资料'));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('lesson_materials_dialog')), findsOneWidget);
    expect(find.byType(BackdropFilter), findsWidgets);
    final dialogSurface = tester.widget<Container>(
      find.byKey(const Key('lesson_materials_dialog_surface')),
    );
    final dialogDecoration = dialogSurface.decoration! as BoxDecoration;
    expect(dialogDecoration.color, AppTheme.surface);
    expect(dialogDecoration.borderRadius, BorderRadius.circular(32));
    expect(dialogDecoration.boxShadow, AppTheme.shadowRaised);
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_materials_dialog')),
        matching: find.byType(ListTile),
      ),
      findsNothing,
    );
    final materialRow = tester.widget<Container>(
      find.byKey(const Key('lesson_material_row_501')),
    );
    final materialRowDecoration = materialRow.decoration! as BoxDecoration;
    expect(materialRowDecoration.color, AppTheme.surface);
    expect(materialRowDecoration.borderRadius, BorderRadius.circular(18));
    expect(materialRowDecoration.boxShadow, AppTheme.shadowInsetLook);
    expect(find.text('本节资料'), findsWidgets);
    expect(
      find.descendant(
        of: find.byKey(const Key('lesson_materials_dialog')),
        matching: find.text('01-栈与队列.mp4'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('lesson materials support mp4 preview and delete refresh',
      (tester) async {
    _useTestSurface(tester);
    final apiClient = _LessonStudyPageFakeApiClient();
    await _pumpLessonStudy(tester, apiClient: apiClient);

    await tester.tap(find.text('本节资料'));
    await tester.pumpAndSettle();

    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('lesson_material_row_501')),
        matching: find.byIcon(Icons.play_arrow_outlined),
      ),
    );
    await tester.pumpAndSettle();

    expect(apiClient.playbackResourceIds, contains(501));
    expect(
        find.byKey(const Key('lesson_material_preview_url')), findsOneWidget);
    expect(find.text('https://cdn.test/501.mp4'), findsOneWidget);

    await tester.tap(
      find.descendant(
        of: find.byKey(const Key('lesson_material_row_502')),
        matching: find.byIcon(Icons.delete_outline),
      ),
    );
    await tester.pumpAndSettle();

    expect(apiClient.deletedResourceIds, [502]);
    expect(find.byKey(const Key('lesson_material_row_502')), findsNothing);
    expect(find.text('栈与队列讲义.pdf'), findsNothing);
  });

  testWidgets('enter test action routes to lesson quiz context',
      (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    await tester.tap(find.text('课时测试'));
    await tester.pumpAndSettle();

    expect(find.text('lesson quiz 101/42'), findsOneWidget);
  });

  testWidgets(
      'generate handout button shows generating while request is pending',
      (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _DelayedGenerateBlockLessonStudyPageFakeApiClient();
    await _pumpLessonStudy(tester, apiClient: fakeApiClient);

    await tester.tap(find.text('生成讲义').last);
    await fakeApiClient.generateRequested.future;
    await tester.pump();

    expect(find.text('正在生成'), findsOneWidget);
    expect(fakeApiClient.generateRequestCount, 1);

    await tester.tap(find.text('正在生成'));
    await tester.pump();

    expect(fakeApiClient.generateRequestCount, 1);

    fakeApiClient.generateResponse.complete(
      handouts.HandoutBlockGenerateResultModel.fromJson({
        'blockId': 4201,
        'outlineKey': 'section-1-1',
        'status': 'ready',
        'generationStatus': 'ready',
        'startSec': 0,
        'endSec': 90,
      }),
    );
    await tester.pumpAndSettle();

    expect(find.text('生成讲义'), findsWidgets);
  });

  testWidgets(
      'generate handout button stays disabled while selected block is generating',
      (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _GeneratingBlockLessonStudyPageFakeApiClient();
    await _pumpLessonStudy(tester, apiClient: fakeApiClient);

    await tester.tap(find.text('生成讲义').last);
    await tester.pumpAndSettle();

    expect(find.text('正在生成'), findsOneWidget);
    final disabledButton = tester.widget<InkWell>(
      find.ancestor(
        of: find.text('正在生成'),
        matching: find.byType(InkWell),
      ),
    );
    expect(disabledButton.onTap, isNull);

    await tester.tap(find.text('正在生成'));
    await tester.pump();

    expect(fakeApiClient.generateRequestCount, 1);
  });

  testWidgets('embedded lesson QA shows the question and answer as a pair',
      (tester) async {
    _useTestSurface(tester);
    await _pumpLessonStudy(tester);

    await tester.enterText(
      find.byType(TextField),
      'Why keep one queue slot empty?',
    );
    await tester.tap(find.byIcon(Icons.send_outlined));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('lesson_ai_entry_question_1')), findsOneWidget);
    expect(find.text('Why keep one queue slot empty?'), findsOneWidget);
    expect(find.byKey(const Key('lesson_ai_entry_answer_1')), findsOneWidget);
    expect(
      find.textContaining('Keep one empty slot to distinguish full and empty'),
      findsOneWidget,
    );
  });

  testWidgets('embedded lesson QA retry reuses the failed question row',
      (tester) async {
    _useTestSurface(tester);
    final fakeApiClient = _FailThenSucceedQaLessonStudyPageFakeApiClient();
    await _pumpLessonStudy(tester, apiClient: fakeApiClient);

    await tester.enterText(find.byType(TextField), 'Why did QA fail?');
    await tester.tap(find.byIcon(Icons.send_outlined));
    await tester.pumpAndSettle();

    expect(fakeApiClient.qaRequestCount, 1);
    expect(find.text('Why did QA fail?'), findsOneWidget);
    expect(find.byKey(const Key('lesson_ai_entry_error_1')), findsOneWidget);
    expect(find.byKey(const Key('lesson_ai_retry_1')), findsOneWidget);

    await tester.tap(find.byKey(const Key('lesson_ai_retry_1')));
    await tester.pumpAndSettle();

    expect(fakeApiClient.qaRequestCount, 2);
    expect(find.text('Why did QA fail?'), findsOneWidget);
    expect(find.byKey(const Key('lesson_ai_entry_error_1')), findsNothing);
    expect(find.byKey(const Key('lesson_ai_entry_answer_1')), findsOneWidget);
    expect(find.textContaining('Recovered page answer'), findsOneWidget);
  });
}

Future<void> _pumpLessonStudy(
  WidgetTester tester, {
  String? firstBlockContentMd,
  ApiClient? apiClient,
  HandoutVideoControllerFactory? videoControllerFactory,
}) async {
  final router = GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => const LessonStudyPage(
          courseId: '101',
          lessonId: '42',
        ),
      ),
      GoRoute(
        path: '/courses/:courseId/lessons/:lessonId/quiz',
        builder: (context, state) => Text(
          'lesson quiz ${state.pathParameters['courseId']}/'
          '${state.pathParameters['lessonId']}',
        ),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        apiClientProvider.overrideWithValue(
          apiClient ??
              _LessonStudyPageFakeApiClient(
                firstBlockContentMd: firstBlockContentMd,
              ),
        ),
        if (videoControllerFactory != null)
          handoutVideoControllerFactoryProvider.overrideWithValue(
            videoControllerFactory,
          ),
      ],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

class _FakeLessonStudyVideoController implements HandoutVideoController {
  _FakeLessonStudyVideoController(this.uri);

  final Uri uri;
  final List<VoidCallback> _listeners = [];
  final List<Duration> seekPositions = [];
  bool _isInitialized = false;
  bool _isPlaying = false;
  Duration _position = Duration.zero;

  @override
  Future<void> initialize() async {
    _isInitialized = true;
    _notifyListeners();
  }

  @override
  Future<void> play() async {
    _isPlaying = true;
    _notifyListeners();
  }

  @override
  Future<void> pause() async {
    _isPlaying = false;
    _notifyListeners();
  }

  @override
  Future<void> seekTo(Duration position) async {
    seekPositions.add(position);
    _position = position;
    _notifyListeners();
  }

  void jumpTo(Duration position) {
    _position = position;
    _notifyListeners();
  }

  @override
  Future<void> dispose() async {
    _listeners.clear();
  }

  @override
  void addListener(VoidCallback listener) {
    _listeners.add(listener);
  }

  @override
  void removeListener(VoidCallback listener) {
    _listeners.remove(listener);
  }

  @override
  Widget buildPlayer() {
    return ColoredBox(
      color: Colors.black,
      child: Center(
        child: Text(
          uri.toString(),
          style: const TextStyle(color: Colors.white),
        ),
      ),
    );
  }

  @override
  bool get isInitialized => _isInitialized;

  @override
  bool get isPlaying => _isPlaying;

  @override
  Duration get position => _position;

  @override
  Duration get duration => const Duration(minutes: 45);

  @override
  double get aspectRatio => 16 / 9;

  void _notifyListeners() {
    for (final listener in List<VoidCallback>.from(_listeners)) {
      listener();
    }
  }
}

void _useTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1448, 1086);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _LessonStudyPageFakeApiClient extends ApiClient {
  _LessonStudyPageFakeApiClient({this.firstBlockContentMd});

  final String? firstBlockContentMd;
  var qaRequestCount = 0;
  final deletedResourceIds = <int>[];
  final playbackResourceIds = <int>[];
  final progressUpdates = <Map<String, dynamic>>[];

  @override
  Future<LessonDetailModel> fetchLessonDetail({
    required String courseId,
    required String lessonId,
  }) async {
    return LessonDetailModel.fromJson({
      'lesson': {
        'lessonId': lessonId,
        'courseId': courseId,
        'title': '第 1 课：栈与队列',
        'orderIndex': 1,
        'lessonStatus': 'learning_ready',
        'primaryVideoResourceId': 501,
        'primaryVideoStartSec': 0,
        'primaryVideoEndSec': 2700,
        'handoutStatus': 'ready',
        'quizStatus': 'not_generated',
        'reviewStatus': 'not_due',
        'masteryScore': 0.52,
        'lastPositionSec': 128,
      },
      'primaryVideo': {
        'resourceId': 501,
        'resourceName': '01-栈与队列.mp4',
        'resourceType': 'mp4',
        'durationSec': 2700,
        'startSec': 0,
        'endSec': 2700,
      },
      'lessonResources': [
        if (!deletedResourceIds.contains(501))
          {
            'resourceId': 501,
            'courseId': courseId,
            'resourceType': 'mp4',
            'originalName': '01-栈与队列.mp4',
            'scopeType': 'lesson',
            'lessonId': lessonId,
            'usageRole': 'primary_video',
            'visibleToCourseQa': true,
            'durationSec': 2700,
            'sortOrder': 1,
          },
        if (!deletedResourceIds.contains(502))
          {
            'resourceId': 502,
            'courseId': courseId,
            'resourceType': 'pdf',
            'originalName': '栈与队列讲义.pdf',
            'scopeType': 'lesson',
            'lessonId': lessonId,
            'usageRole': 'lesson_material',
            'visibleToCourseQa': true,
            'durationSec': null,
            'sortOrder': 2,
          },
      ],
      'artifactSummaries': [],
      'progress': {'lastPositionSec': 128, 'masteryScore': 0.52},
      'citations': [],
      'sourceOverview': {},
      'knowledgePointPlaceholders': [],
      'weaknessPlaceholders': [],
    });
  }

  @override
  Future<handouts.HandoutLatestModel> fetchLessonHandout({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutLatestModel.fromJson({
      'handoutVersionId': 4200,
      'title': '栈与队列讲义',
      'summary': '围绕栈、队列和循环队列的核心操作生成。',
      'totalBlocks': 2,
      'status': 'ready',
    });
  }

  @override
  Future<handouts.HandoutOutlineModel> fetchLessonHandoutOutline({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutOutlineModel.fromJson({
      'handoutVersionId': 4200,
      'title': '栈与队列讲义',
      'summary': '两级讲义目录',
      'items': [
        {
          'outlineKey': 'chapter-1',
          'title': '第一章',
          'summary': '',
          'startSec': 0,
          'endSec': 180,
          'sortNo': 1,
          'children': [
            _outlineChild(
              blockId: 4201,
              outlineKey: 'section-1-1',
              title: '1.1 极限定义',
              startSec: 0,
              endSec: 90,
            ),
            _outlineChild(
              blockId: 4202,
              outlineKey: 'section-1-2',
              title: '1.2 栈的操作端',
              startSec: 90,
              endSec: 180,
            ),
          ],
        },
      ],
      'outlineUsedFallback': false,
      'outlineIssues': [],
    });
  }

  @override
  Future<handouts.HandoutBlocksModel> fetchLessonHandoutBlocks({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutBlocksModel.fromJson({
      'items': [
        _block(
          blockId: 4201,
          outlineKey: 'section-1-1',
          title: '1.1 极限定义',
          contentMd: firstBlockContentMd ?? '栈只允许在一端插入和删除，队列从队尾入队、队头出队。',
        ),
        _block(
          blockId: 4202,
          outlineKey: 'section-1-2',
          title: '1.2 栈的操作端',
          contentMd: '操作端决定了数据结构的访问顺序。',
        ),
      ],
    });
  }

  @override
  Future<handouts.CurrentHandoutBlockModel> fetchLessonCurrentHandoutBlock({
    required String courseId,
    required String lessonId,
    required int currentSec,
  }) async {
    return handouts.CurrentHandoutBlockModel.fromJson({
      'blockId': 4201,
      'outlineKey': 'section-1-1',
      'startSec': 0,
      'endSec': 90,
      'generationStatus': 'ready',
    });
  }

  @override
  Future<resources.CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    playbackResourceIds.add(resourceId);
    return resources.CourseResourcePlaybackModel.fromJson({
      'resourceId': resourceId,
      'resourceType': 'mp4',
      'playbackUrl': 'https://cdn.test/$resourceId.mp4',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-07-05T12:00:00Z',
      'durationSec': 2700,
    });
  }

  @override
  Future<resources.DeleteCourseResourceResultModel> deleteCourseResource({
    required String courseId,
    required int resourceId,
  }) async {
    deletedResourceIds.add(resourceId);
    return resources.DeleteCourseResourceResultModel.fromJson({
      'deleted': true,
      'resourceId': resourceId,
    });
  }

  @override
  Future<LessonProgressModel> fetchLessonProgress({
    required String courseId,
    required String lessonId,
  }) async {
    return LessonProgressModel.fromJson({
      'courseId': courseId,
      'lessonId': lessonId,
      'lastPositionSec': null,
      'lastHandoutBlockId': null,
      'handoutReadPercent': 0,
      'quizStatus': 'not_generated',
      'reviewStatus': 'not_due',
      'lastActivityAt': '2026-07-05T12:00:00Z',
    });
  }

  @override
  Future<LessonProgressModel> updateLessonProgress({
    required String courseId,
    required String lessonId,
    required Map<String, dynamic> request,
  }) async {
    progressUpdates.add(Map<String, dynamic>.from(request));
    return LessonProgressModel.fromJson({
      'courseId': courseId,
      'lessonId': lessonId,
      'lastPositionSec': request['lastPositionSec'],
      'lastHandoutBlockId': request['lastHandoutBlockId'],
      'handoutReadPercent': 0,
      'quizStatus': 'not_generated',
      'reviewStatus': 'not_due',
      'lastActivityAt': '2026-07-05T12:00:00Z',
    });
  }

  @override
  Future<handouts.QaMessageModel> createLessonQaMessage({
    required String courseId,
    required String lessonId,
    required handouts.ScopedQaMessageRequestModel request,
  }) async {
    qaRequestCount++;
    return handouts.QaMessageModel.fromJson({
      'sessionId': 6201,
      'messageId': 6202,
      'answerMd': 'Keep one empty slot to distinguish full and empty queues.',
      'citations': [
        {
          'resourceId': 501,
          'refLabel': 'video',
          'startSec': 120,
          'endSec': 135,
        },
      ],
    });
  }
}

class _DelayedGenerateBlockLessonStudyPageFakeApiClient
    extends _LessonStudyPageFakeApiClient {
  final generateRequested = Completer<void>();
  final generateResponse =
      Completer<handouts.HandoutBlockGenerateResultModel>();
  var generateRequestCount = 0;

  @override
  Future<handouts.HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) {
    generateRequestCount++;
    if (!generateRequested.isCompleted) {
      generateRequested.complete();
    }
    return generateResponse.future;
  }
}

class _GeneratingBlockLessonStudyPageFakeApiClient
    extends _LessonStudyPageFakeApiClient {
  var generateRequestCount = 0;
  var _selectedBlockGenerating = false;

  @override
  Future<handouts.HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateRequestCount++;
    _selectedBlockGenerating = true;
    return handouts.HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'section-1-1',
      'status': 'generating',
      'generationStatus': 'generating',
      'startSec': 0,
      'endSec': 90,
    });
  }

  @override
  Future<handouts.HandoutBlocksModel> fetchLessonHandoutBlocks({
    required String courseId,
    required String lessonId,
  }) async {
    return handouts.HandoutBlocksModel.fromJson({
      'items': [
        _block(
          blockId: 4201,
          outlineKey: 'section-1-1',
          title: '1.1 极限定义',
          contentMd:
              _selectedBlockGenerating ? null : '栈只允许在一端插入和删除，队列从队尾入队、队头出队。',
          status: _selectedBlockGenerating ? 'generating' : 'ready',
          generationStatus: _selectedBlockGenerating ? 'generating' : 'ready',
        ),
        _block(
          blockId: 4202,
          outlineKey: 'section-1-2',
          title: '1.2 栈的操作端',
          contentMd: '操作端决定了数据结构的访问顺序。',
        ),
      ],
    });
  }
}

class _FailThenSucceedQaLessonStudyPageFakeApiClient
    extends _LessonStudyPageFakeApiClient {
  @override
  Future<handouts.QaMessageModel> createLessonQaMessage({
    required String courseId,
    required String lessonId,
    required handouts.ScopedQaMessageRequestModel request,
  }) async {
    qaRequestCount++;
    if (qaRequestCount == 1) {
      throw StateError('temporary qa failure');
    }
    return handouts.QaMessageModel.fromJson({
      'sessionId': 6201,
      'messageId': 6203,
      'answerMd': 'Recovered page answer',
      'citations': [],
    });
  }
}

Map<String, dynamic> _outlineChild({
  required int blockId,
  required String outlineKey,
  required String title,
  required int startSec,
  required int endSec,
}) {
  return {
    'outlineKey': outlineKey,
    'blockId': blockId,
    'title': title,
    'summary': '',
    'startSec': startSec,
    'endSec': endSec,
    'sortNo': blockId,
    'generationStatus': 'ready',
    'sourceSegmentKeys': ['segment-$blockId'],
    'topicTags': ['topic-$blockId'],
  };
}

Map<String, dynamic> _block({
  required int blockId,
  required String outlineKey,
  required String title,
  required String? contentMd,
  String status = 'ready',
  String? generationStatus,
}) {
  return {
    'blockId': blockId,
    'outlineKey': outlineKey,
    'title': title,
    'summary': '',
    'status': status,
    'generationStatus': generationStatus ?? status,
    'contentMd': contentMd,
    'startSec': 0,
    'endSec': 90,
    'citations': [
      {
        'resourceId': 501,
        'refLabel': '第 1 讲视频',
        'startSec': 18,
        'endSec': 42,
      },
    ],
  };
}
