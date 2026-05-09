import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/handout/handout_page.dart';
import 'package:knowlink_client/features/handout/handout_video_controller.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('handout page renders blocks, markdown, citations, and QA', (
    tester,
  ) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _HandoutPageFakeApiClient();
    final videoControllers = <_FakeHandoutVideoController>[];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
          handoutVideoControllerFactoryProvider.overrideWithValue(
            (uri) {
              final controller = _FakeHandoutVideoController(uri);
              videoControllers.add(controller);
              return controller;
            },
          ),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('高数期末冲刺讲义'), findsOneWidget);
    expect(find.text('集合的概念与表示'), findsOneWidget);
    expect(find.text('目录已使用降级结构展示。；目录按视频时间线降级生成'), findsOneWidget);
    expect(find.text('极限与连续'), findsWidgets);
    expect(find.textContaining('### 极限与连续'), findsNothing);
    expect(find.text('抓住定义与题型边界。'), findsOneWidget);
    expect(find.text('PDF 第 2 页'), findsOneWidget);
    expect(find.textContaining('当前块 QA'), findsOneWidget);
    expect(find.text('当前块还没有问答记录。'), findsOneWidget);
    expect(find.text('集合构造中'), findsOneWidget);
    expect(find.text('集合失败示例'), findsOneWidget);
    expect(find.textContaining('Push'), findsNothing);
    expect(find.text('第 1 章  绪论'), findsNothing);
    expect(find.text('查看原文'), findsNothing);
    expect(find.text('待生成'), findsWidgets);
    expect(find.text('2:00-6:00'), findsWidgets);

    await tester.tap(find.text('集合的概念与表示'));
    await tester.pumpAndSettle();
    expect(fakeApiClient.jumpTargetBlockIds, isEmpty);
    expect(find.text('抓住定义与题型边界。'), findsOneWidget);
    expect(fakeApiClient.qaRequests, isEmpty);

    await tester.tap(find.text('PDF 第 2 页'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.jumpTargetBlockIds, [4001]);
    expect(fakeApiClient.playbackResourceIds, [501]);
    expect(videoControllers.single.uri.toString(),
        'http://127.0.0.1:9000/video-501.mp4?X-Amz-Signature=demo');
    expect(find.text('跳转位置：视频 501 2:00 · 文档 502 第 2 页'), findsOneWidget);
    expect(find.text('引用位置：PDF 第 2 页'), findsOneWidget);

    await tester.tap(find.text('集合的表示方法').first);
    await tester.pumpAndSettle();

    expect(fakeApiClient.jumpTargetBlockIds, [4001, 4002]);
    expect(fakeApiClient.playbackResourceIds, [501, 501]);
    expect(videoControllers.last.seekPositions,
        contains(const Duration(minutes: 6, seconds: 10)));
    expect(find.text('课程 101 · 6:10'), findsOneWidget);
    expect(
      find.text('该讲义块状态为待生成，正文生成后会展示结构化讲义内容。'),
      findsOneWidget,
    );
    expect(find.text('跳转位置：视频 501 6:10 · 文档 502 第 2 页'), findsOneWidget);

    await tester.tap(find.text('集合构造中').first);
    await tester.pumpAndSettle();
    expect(
      find.text('该讲义块状态为生成中，正文生成后会展示结构化讲义内容。'),
      findsOneWidget,
    );

    await tester.tap(find.text('未知状态示例').first);
    await tester.pumpAndSettle();
    expect(
      find.text('该讲义块状态为状态待确认，正文生成后会展示结构化讲义内容。'),
      findsOneWidget,
    );
    expect(find.textContaining('mystery_state'), findsNothing);

    await tester.tap(find.text('集合失败示例').first);
    await tester.pumpAndSettle();
    expect(find.text('该讲义块生成失败，可重试生成。'), findsOneWidget);

    await tester.tap(find.text('极限与连续').first);
    await tester.pumpAndSettle();
    expect(find.text('抓住定义与题型边界。'), findsOneWidget);
    expect(videoControllers.last.seekPositions,
        contains(const Duration(minutes: 2)));
    await tester.tap(find.byTooltip('播放'));
    await tester.pumpAndSettle();
    expect(videoControllers.last.playCalls, 1);
    await tester.tap(find.byTooltip('暂停'));
    await tester.pumpAndSettle();
    expect(videoControllers.last.pauseCalls, 1);
    await tester.tap(find.widgetWithText(TextButton, '-30').first);
    await tester.pumpAndSettle();
    expect(videoControllers.last.seekPositions,
        contains(const Duration(minutes: 1, seconds: 30)));
    await tester.tap(find.widgetWithText(TextButton, '+30').first);
    await tester.pumpAndSettle();
    expect(videoControllers.last.seekPositions,
        contains(const Duration(minutes: 2)));
    expect(find.text('集合的表示方法'), findsWidgets);
    expect(find.text('抓住定义与题型边界。'), findsOneWidget);
    expect(fakeApiClient.jumpTargetBlockIds.last, 4001);

    await tester.tap(find.text('集合的表示方法').first);
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<FilledButton>(find.widgetWithText(FilledButton, '提交问题'))
          .onPressed,
      isNull,
    );

    await tester.enterText(find.byType(TextField), '这个定义怎么用？');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '提交问题'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.qaRequests.single.handoutBlockId, 4002);
    expect(find.text('回答 #6002'), findsOneWidget);
    expect(find.text('定义控制了题型的判断边界。'), findsOneWidget);
    expect(find.text('证据不足'), findsNothing);
    expect(find.text('PDF 第 8 页'), findsOneWidget);

    final jumpCallCountBeforeQaCitation =
        fakeApiClient.jumpTargetBlockIds.length;
    await tester.tap(find.text('PDF 第 8 页').first);
    await tester.pumpAndSettle();

    expect(
      fakeApiClient.jumpTargetBlockIds,
      hasLength(jumpCallCountBeforeQaCitation + 1),
    );
    expect(fakeApiClient.jumpTargetBlockIds.last, 4002);
    expect(find.text('引用位置：PDF 第 8 页'), findsOneWidget);
  });

  testWidgets('handout QA displays answer without citations', (
    tester,
  ) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _HandoutPageFakeApiClient(
      qaCitations: const [],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
          handoutVideoControllerFactoryProvider.overrideWithValue(
            (uri) => _FakeHandoutVideoController(uri),
          ),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), '证据够吗？');
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '提交问题'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.qaRequests.single.handoutBlockId, 4001);
    expect(find.text('证据不足'), findsNothing);
    expect(find.text('暂无引用。'), findsOneWidget);
  });

  testWidgets('playback unavailable state can retry with a fresh URL', (
    tester,
  ) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _PlaybackUnavailableHandoutPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
          handoutVideoControllerFactoryProvider.overrideWithValue(
            (uri) => _FakeHandoutVideoController(uri),
          ),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('PDF 第 2 页'));
    await tester.pumpAndSettle();

    expect(find.text('播放地址暂不可用'), findsOneWidget);
    expect(find.text('对象存储暂时无法生成播放地址，请重新加载视频。'), findsOneWidget);
    expect(fakeApiClient.playbackResourceIds, [501]);

    await tester.tap(find.widgetWithText(OutlinedButton, '重新加载视频'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.playbackResourceIds, [501, 501]);
    expect(
      find.text(
        'http://127.0.0.1:9000/video-501.mp4?X-Amz-Signature=demo',
      ),
      findsOneWidget,
    );
  });

  testWidgets('non-video and empty video states show distinct messages', (
    tester,
  ) async {
    _useLargeTestSurface(tester);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider
              .overrideWithValue(_NonVideoHandoutPageFakeApiClient()),
          handoutVideoControllerFactoryProvider.overrideWithValue(
            (uri) => _FakeHandoutVideoController(uri),
          ),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('PDF 第 2 页'));
    await tester.pumpAndSettle();
    expect(find.text('当前定位资源不是视频'), findsOneWidget);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider
              .overrideWithValue(_NoVideoHandoutPageFakeApiClient()),
          handoutVideoControllerFactoryProvider.overrideWithValue(
            (uri) => _FakeHandoutVideoController(uri),
          ),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('PDF 第 2 页'));
    await tester.pumpAndSettle();
    expect(find.text('当前讲义块暂无视频定位'), findsOneWidget);
  });

  testWidgets('video duration shows placeholder until metadata is available', (
    tester,
  ) async {
    _useLargeTestSurface(tester);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(_HandoutPageFakeApiClient()),
          handoutVideoControllerFactoryProvider.overrideWithValue(
            (uri) => _FakeHandoutVideoController(
              uri,
              duration: Duration.zero,
            ),
          ),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('PDF 第 2 页'));
    await tester.pumpAndSettle();

    expect(find.text('2:00 / --:--'), findsOneWidget);
  });
}

void _useLargeTestSurface(WidgetTester tester) {
  tester.view.physicalSize = const Size(1200, 2200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

class _HandoutPageFakeApiClient extends ApiClient {
  _HandoutPageFakeApiClient({
    this.qaCitations = const [
      {
        'resourceId': 777,
        'refLabel': 'PDF 第 8 页',
        'pageNo': 8,
      },
    ],
  });

  final List<int> jumpTargetBlockIds = [];
  final List<int> playbackResourceIds = [];
  final List<QaMessageRequestModel> qaRequests = [];
  final List<Map<String, Object?>> qaCitations;

  @override
  Future<HandoutLatestModel> fetchLatestHandout(String courseId) async {
    return const HandoutLatestModel(
      handoutVersionId: 3001,
      title: '高数期末冲刺讲义',
      summary: '按考试优先级整理的知识块',
      totalBlocks: 2,
      status: 'ready',
    );
  }

  @override
  Future<HandoutVersionStatusModel> fetchHandoutVersionStatus(
    int handoutVersionId,
  ) async {
    return const HandoutVersionStatusModel(
      handoutVersionId: 3001,
      status: 'ready',
      outlineStatus: 'ready',
      totalBlocks: 4,
      readyBlocks: 1,
      pendingBlocks: 3,
      sourceParseRunId: 9001,
    );
  }

  @override
  Future<HandoutOutlineModel> fetchLatestHandoutOutline(
    String courseId,
  ) async {
    return HandoutOutlineModel.fromJson({
      'handoutVersionId': 3001,
      'title': '高数期末冲刺讲义',
      'summary': '按视频时间线组织',
      'items': [
        {
          'outlineKey': 'section-1',
          'title': '集合的概念与表示',
          'summary': '从极限连续过渡到集合表示',
          'startSec': 120,
          'endSec': 1080,
          'sortNo': 1,
          'children': [
            {
              'outlineKey': 'outline-1',
              'blockId': 4001,
              'title': '极限与连续',
              'summary': '先抓必考定义和题型',
              'startSec': 120,
              'endSec': 360,
              'sortNo': 1,
              'generationStatus': 'ready',
              'sourceSegmentKeys': ['mp4-c1'],
              'topicTags': ['极限'],
            },
            {
              'outlineKey': 'outline-2',
              'blockId': 4002,
              'title': '集合的表示方法',
              'summary': '从列举法过渡到描述法',
              'startSec': 360,
              'endSec': 540,
              'sortNo': 2,
              'generationStatus': 'pending',
              'sourceSegmentKeys': ['mp4-c2'],
              'topicTags': ['集合'],
            },
            {
              'outlineKey': 'outline-3',
              'blockId': 4003,
              'title': '集合构造中',
              'summary': '生成中的讲义块',
              'startSec': 540,
              'endSec': 720,
              'sortNo': 3,
              'generationStatus': 'generating',
              'sourceSegmentKeys': ['mp4-c3'],
              'topicTags': ['集合'],
            },
            {
              'outlineKey': 'outline-4',
              'blockId': 4004,
              'title': '集合失败示例',
              'summary': '失败状态示例',
              'startSec': 720,
              'endSec': 900,
              'sortNo': 4,
              'generationStatus': 'failed',
              'sourceSegmentKeys': ['mp4-c4'],
              'topicTags': ['集合'],
            },
            {
              'outlineKey': 'outline-5',
              'blockId': 4005,
              'title': '未知状态示例',
              'summary': '未知状态讲义块',
              'startSec': 900,
              'endSec': 1080,
              'sortNo': 5,
              'generationStatus': 'mystery_state',
              'sourceSegmentKeys': ['mp4-c5'],
              'topicTags': [],
            },
          ],
        },
      ],
      'outlineUsedFallback': true,
      'outlineIssues': ['目录按视频时间线降级生成'],
    });
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    return HandoutBlocksModel.fromJson({
      'items': [
        {
          'blockId': 4001,
          'outlineKey': 'outline-1',
          'title': '极限与连续',
          'summary': '先抓必考定义和题型',
          'status': 'ready',
          'contentMd': '### 极限与连续\n\n抓住定义与题型边界。',
          'startSec': 120,
          'endSec': 360,
          'pageFrom': 2,
          'pageTo': 5,
          'citations': [
            {
              'resourceId': 501,
              'refLabel': 'PDF 第 2 页',
              'pageNo': 2,
            },
          ],
        },
        {
          'blockId': 4002,
          'outlineKey': 'outline-2',
          'title': '集合的表示方法',
          'summary': '从列举法过渡到描述法',
          'status': 'pending',
          'contentMd': null,
          'startSec': 360,
          'endSec': 540,
          'citations': [],
        },
        {
          'blockId': 4003,
          'outlineKey': 'outline-3',
          'title': '集合构造中',
          'summary': '生成中的讲义块',
          'status': 'generating',
          'contentMd': null,
          'startSec': 540,
          'endSec': 720,
          'citations': [],
        },
        {
          'blockId': 4004,
          'outlineKey': 'outline-4',
          'title': '集合失败示例',
          'summary': '失败状态示例',
          'status': 'failed',
          'contentMd': null,
          'startSec': 720,
          'endSec': 900,
          'citations': [],
        },
        {
          'blockId': 4005,
          'outlineKey': 'outline-5',
          'title': '未知状态示例',
          'summary': '未知状态讲义块',
          'status': 'mystery_state',
          'contentMd': null,
          'startSec': 900,
          'endSec': 1080,
          'citations': [],
        },
      ],
    });
  }

  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    jumpTargetBlockIds.add(blockId);
    return HandoutJumpTargetModel(
      blockId: blockId,
      videoResourceId: 501,
      startSec: blockId == 4001 ? 120 : 370,
      endSec: blockId == 4001 ? 360 : 540,
      docResourceId: 502,
      pageNo: 2,
    );
  }

  @override
  Future<CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    playbackResourceIds.add(resourceId);
    return CourseResourcePlaybackModel.fromJson({
      'resourceId': resourceId,
      'resourceType': 'mp4',
      'playbackUrl':
          'http://127.0.0.1:9000/video-$resourceId.mp4?X-Amz-Signature=demo',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-04-18T16:00:00+00:00',
      'durationSec': null,
    });
  }

  @override
  Future<QaMessageModel> createQaMessage({
    required QaMessageRequestModel request,
  }) async {
    qaRequests.add(request);
    return QaMessageModel.fromJson({
      'sessionId': 6001,
      'messageId': 6002,
      'answerMd': '定义控制了题型的判断边界。',
      'citations': qaCitations,
      'retrievedDocuments': [
        {'resourceId': 999},
      ],
    });
  }
}

class _PlaybackUnavailableHandoutPageFakeApiClient
    extends _HandoutPageFakeApiClient {
  var _playbackCalls = 0;

  @override
  Future<CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    playbackResourceIds.add(resourceId);
    _playbackCalls++;
    if (_playbackCalls == 1) {
      final requestOptions =
          RequestOptions(path: '/api/v1/course-resources/$resourceId/playback');
      throw DioException(
        requestOptions: requestOptions,
        response: Response<Map<String, dynamic>>(
          requestOptions: requestOptions,
          statusCode: 503,
          data: {
            'errorCode': 'resource.playback_unavailable',
          },
        ),
      );
    }
    return CourseResourcePlaybackModel.fromJson({
      'resourceId': resourceId,
      'resourceType': 'mp4',
      'playbackUrl':
          'http://127.0.0.1:9000/video-$resourceId.mp4?X-Amz-Signature=demo',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-04-18T16:00:00+00:00',
      'durationSec': null,
    });
  }
}

class _NonVideoHandoutPageFakeApiClient extends _HandoutPageFakeApiClient {
  @override
  Future<CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    playbackResourceIds.add(resourceId);
    final requestOptions =
        RequestOptions(path: '/api/v1/course-resources/$resourceId/playback');
    throw DioException(
      requestOptions: requestOptions,
      response: Response<Map<String, dynamic>>(
        requestOptions: requestOptions,
        statusCode: 409,
        data: {
          'errorCode': 'resource.not_video',
        },
      ),
    );
  }
}

class _NoVideoHandoutPageFakeApiClient extends _HandoutPageFakeApiClient {
  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    jumpTargetBlockIds.add(blockId);
    return HandoutJumpTargetModel(
      blockId: blockId,
      startSec: blockId == 4001 ? 120 : 360,
      endSec: blockId == 4001 ? 360 : 540,
      docResourceId: 502,
      pageNo: 2,
    );
  }
}

class _FakeHandoutVideoController implements HandoutVideoController {
  _FakeHandoutVideoController(
    this.uri, {
    this.duration = const Duration(minutes: 12, seconds: 48),
  });

  final Uri uri;
  @override
  final Duration duration;
  final List<VoidCallback> _listeners = [];
  final List<Duration> seekPositions = [];
  bool _isInitialized = false;
  bool _isPlaying = false;
  Duration _position = Duration.zero;
  int playCalls = 0;
  int pauseCalls = 0;

  @override
  Future<void> initialize() async {
    _isInitialized = true;
    _notifyListeners();
  }

  @override
  Future<void> play() async {
    playCalls++;
    _isPlaying = true;
    _notifyListeners();
  }

  @override
  Future<void> pause() async {
    pauseCalls++;
    _isPlaying = false;
    _notifyListeners();
  }

  @override
  Future<void> seekTo(Duration position) async {
    seekPositions.add(position);
    _position = position;
    _notifyListeners();
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
  Future<void> dispose() async {
    _listeners.clear();
  }

  @override
  bool get isInitialized => _isInitialized;

  @override
  bool get isPlaying => _isPlaying;

  @override
  Duration get position => _position;

  @override
  double get aspectRatio => 16 / 9;

  void _notifyListeners() {
    for (final listener in List<VoidCallback>.of(_listeners)) {
      listener();
    }
  }
}
