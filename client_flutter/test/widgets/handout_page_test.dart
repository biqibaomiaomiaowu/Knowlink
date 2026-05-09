import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/features/handout/handout_page.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';

void main() {
  testWidgets('handout page renders blocks, markdown, citations, and QA', (
    tester,
  ) async {
    _useLargeTestSurface(tester);
    final fakeApiClient = _HandoutPageFakeApiClient();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(fakeApiClient),
        ],
        child: const MaterialApp(home: HandoutPage(courseId: '101')),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('高数期末冲刺讲义'), findsOneWidget);
    expect(find.text('极限与连续'), findsWidgets);
    expect(find.text('### 极限与连续'), findsOneWidget);
    expect(find.text('PDF 第 2 页'), findsOneWidget);
    expect(find.textContaining('当前块 QA'), findsOneWidget);
    expect(find.text('当前块还没有问答记录。'), findsOneWidget);
    expect(find.text('集合构造中'), findsOneWidget);
    expect(find.text('集合失败示例'), findsOneWidget);
    expect(find.textContaining('Push'), findsNothing);
    expect(find.text('第 1 章  绪论'), findsNothing);
    expect(find.text('查看原文'), findsNothing);

    await tester.tap(find.text('PDF 第 2 页'));
    await tester.pumpAndSettle();

    expect(fakeApiClient.jumpTargetBlockIds, [4001]);
    expect(find.text('跳转位置：视频 501 2:00 · 文档 502 第 2 页'), findsOneWidget);
    expect(find.text('引用位置：PDF 第 2 页'), findsOneWidget);

    await tester.tap(find.text('集合的表示方法').first);
    await tester.pumpAndSettle();

    expect(find.text('课程 101 · 6:00'), findsOneWidget);
    expect(fakeApiClient.jumpTargetBlockIds, [4001, 4002]);
    expect(
      find.text('该讲义块状态为待生成，正文生成后会展示原始 Markdown。'),
      findsOneWidget,
    );
    expect(find.text('跳转位置：视频 501 6:00 · 文档 502 第 2 页'), findsOneWidget);

    await tester.tap(find.text('集合构造中').first);
    await tester.pumpAndSettle();
    expect(
      find.text('该讲义块状态为生成中，正文生成后会展示原始 Markdown。'),
      findsOneWidget,
    );

    await tester.tap(find.text('未知状态示例').first);
    await tester.pumpAndSettle();
    expect(
      find.text('该讲义块状态为状态待确认，正文生成后会展示原始 Markdown。'),
      findsOneWidget,
    );
    expect(find.textContaining('mystery_state'), findsNothing);

    await tester.tap(find.text('集合失败示例').first);
    await tester.pumpAndSettle();
    expect(find.text('该讲义块生成失败，可重试生成。'), findsOneWidget);

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
      'items': [],
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
          'contentMd': '### 极限与连续',
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
      startSec: blockId == 4001 ? 120 : 360,
      endSec: blockId == 4001 ? 360 : 540,
      docResourceId: 502,
      pageNo: 2,
    );
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
