import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/providers/course_flow_providers.dart';
import 'package:knowlink_client/shared/providers/course_recommend_provider.dart';
import 'package:knowlink_client/shared/providers/handout_provider.dart';

void main() {
  test('load reads latest handout data and syncs course flow', () async {
    final fakeApiClient = _HandoutProviderFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.latest.valueOrNull?.handoutVersionId, 3001);
    expect(state.versionStatus.valueOrNull?.status, 'ready');
    expect(state.blocks.valueOrNull?.items, hasLength(2));
    expect(state.selectedBlock?.blockId, 4001);
    expect(container.read(courseFlowProvider).activeHandoutVersionId, 3001);
    expect(container.read(activeBlockProvider), 4001);
  });

  test('load auto generates when latest handout is missing', () async {
    final fakeApiClient = _HandoutProviderFakeApiClient(noActiveFirst: true);
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(fakeApiClient.generateHandoutCalls, 1);
    expect(state.generateRequest.valueOrNull?.entity.id, 3001);
    expect(state.latest.valueOrNull?.status, 'ready');
    expect(container.read(courseFlowProvider).activeHandoutVersionId, 3001);
  });

  test('unexpected handout generate entity surfaces an error', () async {
    final fakeApiClient = _UnexpectedGenerateEntityFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);
    container.read(courseFlowProvider.notifier)
      ..startCourse('101')
      ..setActiveHandoutVersion(3001)
      ..setSession(6001);

    await container.read(handoutProvider.notifier).generateAndPoll(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.isPolling, isFalse);
    expect(state.generateRequest.hasError, isTrue);
    expect(state.versionStatus.hasError, isTrue);
    expect(state.blocks.hasError, isTrue);
    expect(container.read(courseFlowProvider).activeHandoutVersionId, isNull);
    expect(container.read(courseFlowProvider).sessionId, isNull);
  });

  test('poll timeout becomes an error and clears stale active block', () async {
    final fakeApiClient = _HandoutProviderFakeApiClient(
      versionStatus: const HandoutVersionStatusModel(
        handoutVersionId: 3001,
        status: 'generating',
        outlineStatus: 'pending',
        totalBlocks: 2,
        readyBlocks: 0,
        pendingBlocks: 2,
        sourceParseRunId: 9001,
      ),
    );
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);
    container.read(activeBlockProvider.notifier).state = 4999;

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.isPolling, isFalse);
    expect(state.versionStatus.hasError, isTrue);
    expect(state.blocks.hasError, isTrue);
    expect(container.read(activeBlockProvider), isNull);
  });

  test('load failure clears stale handout version, session, and active block',
      () async {
    final fakeApiClient = _FailingLatestFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);
    container.read(courseFlowProvider.notifier)
      ..startCourse('101')
      ..setActiveHandoutVersion(3001)
      ..setSession(6001);
    container.read(activeBlockProvider.notifier).state = 4001;

    await container.read(handoutProvider.notifier).load(
          '101',
          autoGenerate: false,
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.latest.hasError, isTrue);
    expect(container.read(courseFlowProvider).activeHandoutVersionId, isNull);
    expect(container.read(courseFlowProvider).sessionId, isNull);
    expect(container.read(activeBlockProvider), isNull);
  });

  test('old course polling result does not overwrite newer course data',
      () async {
    final fakeApiClient = _SwitchCourseFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    final oldLoad = container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    await fakeApiClient.oldStatusRequested.future;

    await container.read(handoutProvider.notifier).load(
          '202',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    fakeApiClient.oldStatus.complete(
      const HandoutVersionStatusModel(
        handoutVersionId: 3001,
        status: 'ready',
        outlineStatus: 'ready',
        totalBlocks: 1,
        readyBlocks: 1,
        pendingBlocks: 0,
        sourceParseRunId: 9001,
      ),
    );
    await oldLoad;

    final state = container.read(handoutProvider);
    expect(state.latest.valueOrNull?.handoutVersionId, 3002);
    expect(state.selectedBlock?.blockId, 5001);
    expect(container.read(courseFlowProvider).activeHandoutVersionId, 3002);
    expect(container.read(activeBlockProvider), 5001);
  });

  test('jump target and current block ignore stale responses', () async {
    final fakeApiClient = _RaceFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);
    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final blocks = container.read(handoutProvider).blocks.valueOrNull!.items;

    final firstJump = container.read(handoutProvider.notifier).selectBlock(
          blocks[0],
        );
    await fakeApiClient.firstJumpRequested.future;
    final secondJump = container.read(handoutProvider.notifier).selectBlock(
          blocks[1],
        );
    await fakeApiClient.secondJumpRequested.future;
    fakeApiClient.secondJump.complete(
      const HandoutJumpTargetModel(
        blockId: 4002,
        startSec: 360,
      ),
    );
    await secondJump;
    fakeApiClient.firstJump.complete(
      const HandoutJumpTargetModel(
        blockId: 4001,
        startSec: 120,
      ),
    );
    await firstJump;

    expect(
        container.read(handoutProvider).jumpTarget.valueOrNull?.blockId, 4002);

    final firstCurrent = container
        .read(handoutProvider.notifier)
        .syncCurrentBlockFromPosition(courseId: '101', positionSec: 130);
    await fakeApiClient.firstCurrentRequested.future;
    final secondCurrent = container
        .read(handoutProvider.notifier)
        .syncCurrentBlockFromPosition(courseId: '101', positionSec: 380);
    await fakeApiClient.secondCurrentRequested.future;
    fakeApiClient.secondCurrent.complete(
      const CurrentHandoutBlockModel(
        blockId: 4002,
        outlineKey: 'outline-2',
        startSec: 360,
        endSec: 540,
        generationStatus: 'pending',
      ),
    );
    await secondCurrent;
    fakeApiClient.firstCurrent.complete(
      const CurrentHandoutBlockModel(
        blockId: 4001,
        outlineKey: 'outline-1',
        startSec: 120,
        endSec: 360,
        generationStatus: 'ready',
      ),
    );
    await firstCurrent;

    expect(container.read(activeBlockProvider), 4002);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4002);
  });

  test('manual block selection invalidates in-flight current-block response',
      () async {
    final fakeApiClient = _PendingCurrentFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final pendingCurrent = container
        .read(handoutProvider.notifier)
        .syncCurrentBlockFromPosition(courseId: '101', positionSec: 130);
    await fakeApiClient.currentRequested.future;

    final secondBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(secondBlock);
    fakeApiClient.current.complete(
      const CurrentHandoutBlockModel(
        blockId: 4001,
        outlineKey: 'outline-1',
        startSec: 120,
        endSec: 360,
        generationStatus: 'ready',
      ),
    );
    await pendingCurrent;

    expect(container.read(activeBlockProvider), 4002);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4002);
    expect(container.read(handoutProvider).currentBlock.valueOrNull, isNull);
    expect(
        container.read(handoutProvider).jumpTarget.valueOrNull?.blockId, 4002);
  });

  test('jump target mismatched block id becomes an error', () async {
    final fakeApiClient = _MismatchedJumpTargetFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final secondBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(secondBlock);

    expect(container.read(handoutProvider).jumpTarget.hasError, isTrue);
    expect(container.read(handoutProvider).jumpTarget.valueOrNull, isNull);
  });

  test('course reload invalidates stale current-block response', () async {
    final fakeApiClient = _SwitchCourseCurrentBlockFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final staleCurrent = container
        .read(handoutProvider.notifier)
        .syncCurrentBlockFromPosition(courseId: '101', positionSec: 130);
    await fakeApiClient.currentRequested.future;

    await container.read(handoutProvider.notifier).load(
          '202',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    fakeApiClient.current.complete(
      const CurrentHandoutBlockModel(
        blockId: 4001,
        outlineKey: 'outline-1',
        startSec: 120,
        endSec: 360,
        generationStatus: 'ready',
      ),
    );
    await staleCurrent;

    expect(container.read(activeBlockProvider), 5001);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 5001);
  });

  test('selecting a block syncs player position, active block, and jump target',
      () async {
    final fakeApiClient = _HandoutProviderFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final block = container.read(handoutProvider).blocks.valueOrNull!.items[1];

    await container.read(handoutProvider.notifier).selectBlock(block);

    expect(container.read(playerStateProvider).positionSec, 360);
    expect(container.read(activeBlockProvider), 4002);
    expect(fakeApiClient.jumpTargetBlockIds, [4002]);
    expect(
      container.read(handoutProvider).jumpTarget.valueOrNull?.blockId,
      4002,
    );
  });

  test('submitting a QA question uses selected block and syncs session',
      () async {
    final fakeApiClient = _HandoutProviderFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    await container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '  这个定义怎么用？  ',
        );

    expect(fakeApiClient.qaRequests.single.courseId, 101);
    expect(fakeApiClient.qaRequests.single.handoutBlockId, 4001);
    expect(fakeApiClient.qaRequests.single.question, '这个定义怎么用？');
    expect(container.read(courseFlowProvider).sessionId, 6001);
    expect(
      container.read(handoutProvider).selectedBlockQaMessages.single.citations,
      isNotEmpty,
    );
  });

  test('QA answers stay scoped to the selected block', () async {
    final fakeApiClient = _HandoutProviderFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    await container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '第一块问题',
        );
    expect(container.read(courseFlowProvider).sessionId, 6001);
    final secondBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(secondBlock);

    expect(container.read(courseFlowProvider).sessionId, isNull);
    expect(container.read(handoutProvider).selectedBlockQaMessages, isEmpty);
    expect(
      container.read(handoutProvider).qaMessagesByBlockId[4001],
      hasLength(1),
    );
  });

  test('stale QA response is ignored after selecting another block', () async {
    final fakeApiClient = _DelayedQaFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final pendingQa = container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '慢问题',
        );
    await fakeApiClient.qaRequested.future;
    final secondBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(secondBlock);
    fakeApiClient.qaResponse.complete(
      QaMessageModel.fromJson({
        'sessionId': 6001,
        'messageId': 6002,
        'answerMd': '旧回答',
        'citations': [],
      }),
    );
    await pendingQa;

    expect(container.read(courseFlowProvider).sessionId, isNull);
    expect(container.read(handoutProvider).qaMessagesByBlockId, isEmpty);
  });

  test('external course switch invalidates stale QA response', () async {
    final fakeApiClient = _DelayedQaFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final pendingQa = container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '慢问题',
        );
    await fakeApiClient.qaRequested.future;

    container.read(courseFlowProvider.notifier).startCourse('202');
    fakeApiClient.qaResponse.complete(
      QaMessageModel.fromJson({
        'sessionId': 6001,
        'messageId': 6002,
        'answerMd': '旧回答',
        'citations': [],
      }),
    );
    await pendingQa;

    expect(container.read(courseFlowProvider).courseId, '202');
    expect(container.read(courseFlowProvider).sessionId, isNull);
    expect(container.read(activeBlockProvider), isNull);
    expect(container.read(handoutProvider).qaMessagesByBlockId, isEmpty);
    expect(container.read(handoutProvider).qaSubmit.isLoading, isFalse);
  });

  test('playhead block switch clears stale QA loading state', () async {
    final fakeApiClient = _DelayedQaFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final pendingQa = container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '慢问题',
        );
    await fakeApiClient.qaRequested.future;

    container.read(handoutProvider.notifier).syncHighlightedBlock(380);
    await Future<void>.delayed(Duration.zero);

    final switchedState = container.read(handoutProvider);
    expect(switchedState.selectedBlock?.blockId, 4002);
    expect(switchedState.qaSubmit.isLoading, isFalse);
    expect(switchedState.jumpTarget.valueOrNull?.blockId, 4002);

    fakeApiClient.qaResponse.complete(
      QaMessageModel.fromJson({
        'sessionId': 6001,
        'messageId': 6002,
        'answerMd': '旧回答',
        'citations': [],
      }),
    );
    await pendingQa;

    expect(container.read(courseFlowProvider).sessionId, isNull);
    expect(container.read(handoutProvider).qaMessagesByBlockId, isEmpty);
    expect(container.read(handoutProvider).qaSubmit.isLoading, isFalse);
  });

  test('block generation polls status and refreshes blocks', () async {
    final fakeApiClient = _BlockGenerateFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final secondBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(secondBlock);
    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    expect(fakeApiClient.generateBlockCalls, 1);
    expect(fakeApiClient.blockStatusCalls, 1);
    expect(
      container.read(handoutProvider).blocks.valueOrNull!.items[1].status,
      'ready',
    );
  });

  test('block generation stays locked while status polling is pending',
      () async {
    final fakeApiClient = _SwitchCourseBlockGenerateFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final firstGenerate =
        container.read(handoutProvider.notifier).generateBlock(
              4002,
              courseId: '101',
              pollInterval: Duration.zero,
              maxAttempts: 1,
            );
    await fakeApiClient.blockStatusRequested.future;
    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    expect(fakeApiClient.generateBlockCalls, 1);
    expect(
        container.read(handoutProvider).blockGenerateRequest.isLoading, isTrue);

    fakeApiClient.blockStatus.complete(
      HandoutBlockStatusModel.fromJson({
        'blockId': 4002,
        'outlineKey': 'outline-2',
        'status': 'ready',
        'startSec': 360,
        'endSec': 540,
      }),
    );
    await firstGenerate;

    expect(container.read(handoutProvider).blockGenerateRequest.isLoading,
        isFalse);
    expect(fakeApiClient.generateBlockCalls, 1);
  });

  test('block generation ready status response refreshes blocks', () async {
    final fakeApiClient = _ReadyBlockGenerateFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    expect(
      container.read(handoutProvider).blocks.valueOrNull!.items[1].status,
      'pending',
    );
    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    expect(fakeApiClient.generateBlockCalls, 1);
    expect(fakeApiClient.blockStatusCalls, 0);
    expect(
      container
          .read(handoutProvider)
          .blockGenerateRequest
          .valueOrNull
          ?.blockStatus
          ?.status,
      'ready',
    );
    expect(
      container.read(handoutProvider).blocks.valueOrNull!.items[1].status,
      'ready',
    );
  });

  test('selecting another block clears stale block generation error', () async {
    final fakeApiClient = _UnexpectedBlockGenerateEntityFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final errorBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(errorBlock);
    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    expect(
        container.read(handoutProvider).blockGenerateRequest.hasError, isTrue);

    final firstBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[0];
    await container.read(handoutProvider.notifier).selectBlock(firstBlock);

    expect(
        container.read(handoutProvider).blockGenerateRequest.hasError, isFalse);
  });

  test('course reload invalidates stale block generation refresh', () async {
    final fakeApiClient = _SwitchCourseBlockGenerateFakeApiClient();
    final container = ProviderContainer(
      overrides: [
        apiClientProvider.overrideWithValue(fakeApiClient),
      ],
    );
    addTearDown(container.dispose);
    final subscription = container.listen(handoutProvider, (_, __) {});
    addTearDown(subscription.close);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    final staleGenerate =
        container.read(handoutProvider.notifier).generateBlock(
              4002,
              courseId: '101',
              pollInterval: Duration.zero,
              maxAttempts: 1,
            );
    await fakeApiClient.blockStatusRequested.future;

    await container.read(handoutProvider.notifier).load(
          '202',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    fakeApiClient.blockStatus.complete(
      HandoutBlockStatusModel.fromJson({
        'blockId': 4002,
        'outlineKey': 'outline-2',
        'status': 'ready',
        'startSec': 360,
        'endSec': 540,
      }),
    );
    await staleGenerate;

    expect(container.read(handoutProvider).latest.valueOrNull?.handoutVersionId,
        3002);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 5001);
    expect(container.read(activeBlockProvider), 5001);
    expect(
      container.read(handoutProvider).blockGenerateRequest.isLoading,
      isFalse,
    );
  });
}

class _HandoutProviderFakeApiClient extends ApiClient {
  _HandoutProviderFakeApiClient({
    this.noActiveFirst = false,
    this.versionStatus = const HandoutVersionStatusModel(
      handoutVersionId: 3001,
      status: 'ready',
      outlineStatus: 'ready',
      totalBlocks: 2,
      readyBlocks: 1,
      pendingBlocks: 1,
      sourceParseRunId: 9001,
    ),
  });

  final bool noActiveFirst;
  final HandoutVersionStatusModel versionStatus;
  int fetchLatestCalls = 0;
  int generateHandoutCalls = 0;
  final List<int> jumpTargetBlockIds = [];
  final List<QaMessageRequestModel> qaRequests = [];

  @override
  Future<HandoutLatestModel> fetchLatestHandout(String courseId) async {
    fetchLatestCalls++;
    if (noActiveFirst && fetchLatestCalls == 1) {
      final requestOptions = RequestOptions(path: '/api/v1/courses/$courseId');
      throw DioException(
        requestOptions: requestOptions,
        response: Response<Map<String, dynamic>>(
          requestOptions: requestOptions,
          statusCode: 404,
          data: {
            'errorCode': 'handout.no_active_version',
          },
        ),
      );
    }
    return const HandoutLatestModel(
      handoutVersionId: 3001,
      title: '高数期末冲刺讲义',
      summary: '按考试优先级整理的知识块',
      totalBlocks: 2,
      status: 'ready',
    );
  }

  @override
  Future<HandoutGenerateResultModel> generateHandout({
    required String courseId,
    required String idempotencyKey,
  }) async {
    generateHandoutCalls++;
    return HandoutGenerateResultModel.fromJson({
      'taskId': 7101,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'handout_version', 'id': 3001},
    });
  }

  @override
  Future<HandoutVersionStatusModel> fetchHandoutVersionStatus(
    int handoutVersionId,
  ) async {
    return versionStatus;
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
          'outlineKey': 'outline-1',
          'blockId': 4001,
          'title': '极限与连续',
          'summary': '先抓必考定义和题型',
          'startSec': 120,
          'endSec': 360,
          'sortNo': 1,
          'generationStatus': 'ready',
          'sourceSegmentKeys': ['mp4-c1'],
        },
      ],
    });
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    return HandoutBlocksModel.fromJson({
      'items': [
        _readyBlockJson(),
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
      ],
    });
  }

  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    jumpTargetBlockIds.add(blockId);
    return HandoutJumpTargetModel(
      blockId: blockId,
      videoResourceId: 501,
      startSec: blockId == 4002 ? 360 : 120,
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
      'citations': [
        {
          'resourceId': 501,
          'refLabel': 'PDF 第 2 页',
          'pageNo': 2,
        },
      ],
      'retrievedDocuments': [
        {'resourceId': 999},
      ],
    });
  }
}

class _UnexpectedGenerateEntityFakeApiClient
    extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutGenerateResultModel> generateHandout({
    required String courseId,
    required String idempotencyKey,
  }) async {
    return HandoutGenerateResultModel.fromJson({
      'taskId': 7101,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'quiz', 'id': 8001},
    });
  }
}

class _FailingLatestFakeApiClient extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutLatestModel> fetchLatestHandout(String courseId) async {
    throw StateError('latest failed');
  }
}

class _SwitchCourseFakeApiClient extends _HandoutProviderFakeApiClient {
  final oldStatusRequested = Completer<void>();
  final oldStatus = Completer<HandoutVersionStatusModel>();

  @override
  Future<HandoutLatestModel> fetchLatestHandout(String courseId) async {
    if (courseId == '202') {
      return const HandoutLatestModel(
        handoutVersionId: 3002,
        title: '新课程讲义',
        summary: '切课后的讲义',
        totalBlocks: 1,
        status: 'ready',
      );
    }
    return super.fetchLatestHandout(courseId);
  }

  @override
  Future<HandoutVersionStatusModel> fetchHandoutVersionStatus(
    int handoutVersionId,
  ) async {
    if (handoutVersionId == 3001) {
      if (!oldStatusRequested.isCompleted) {
        oldStatusRequested.complete();
      }
      return oldStatus.future;
    }
    return const HandoutVersionStatusModel(
      handoutVersionId: 3002,
      status: 'ready',
      outlineStatus: 'ready',
      totalBlocks: 1,
      readyBlocks: 1,
      pendingBlocks: 0,
      sourceParseRunId: 9002,
    );
  }

  @override
  Future<HandoutOutlineModel> fetchLatestHandoutOutline(
    String courseId,
  ) async {
    if (courseId == '202') {
      return HandoutOutlineModel.fromJson({
        'handoutVersionId': 3002,
        'title': '新课程讲义',
        'summary': '切课后的讲义',
        'items': [],
      });
    }
    return super.fetchLatestHandoutOutline(courseId);
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    if (courseId == '202') {
      return HandoutBlocksModel.fromJson({
        'items': [
          {
            'blockId': 5001,
            'outlineKey': 'outline-new',
            'title': '新课程块',
            'summary': '切课后的块',
            'status': 'ready',
            'contentMd': '### 新课程块',
            'startSec': 0,
            'endSec': 120,
            'citations': [],
          },
        ],
      });
    }
    return super.fetchLatestHandoutBlocks(courseId);
  }
}

class _RaceFakeApiClient extends _HandoutProviderFakeApiClient {
  final firstJumpRequested = Completer<void>();
  final secondJumpRequested = Completer<void>();
  final firstJump = Completer<HandoutJumpTargetModel>();
  final secondJump = Completer<HandoutJumpTargetModel>();
  final firstCurrentRequested = Completer<void>();
  final secondCurrentRequested = Completer<void>();
  final firstCurrent = Completer<CurrentHandoutBlockModel>();
  final secondCurrent = Completer<CurrentHandoutBlockModel>();
  var _jumpCalls = 0;
  var _currentCalls = 0;

  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) {
    _jumpCalls++;
    if (_jumpCalls == 1) {
      firstJumpRequested.complete();
      return firstJump.future;
    }
    secondJumpRequested.complete();
    return secondJump.future;
  }

  @override
  Future<CurrentHandoutBlockModel> fetchCurrentHandoutBlock({
    required String courseId,
    required int currentSec,
  }) {
    _currentCalls++;
    if (_currentCalls == 1) {
      firstCurrentRequested.complete();
      return firstCurrent.future;
    }
    secondCurrentRequested.complete();
    return secondCurrent.future;
  }
}

class _PendingCurrentFakeApiClient extends _HandoutProviderFakeApiClient {
  final currentRequested = Completer<void>();
  final current = Completer<CurrentHandoutBlockModel>();

  @override
  Future<CurrentHandoutBlockModel> fetchCurrentHandoutBlock({
    required String courseId,
    required int currentSec,
  }) {
    currentRequested.complete();
    return current.future;
  }
}

class _MismatchedJumpTargetFakeApiClient extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    return const HandoutJumpTargetModel(
      blockId: 4999,
      videoResourceId: 501,
      startSec: 120,
    );
  }
}

class _SwitchCourseCurrentBlockFakeApiClient
    extends _SwitchCourseFakeApiClient {
  final currentRequested = Completer<void>();
  final current = Completer<CurrentHandoutBlockModel>();

  @override
  Future<HandoutVersionStatusModel> fetchHandoutVersionStatus(
    int handoutVersionId,
  ) async {
    if (handoutVersionId == 3001) {
      return const HandoutVersionStatusModel(
        handoutVersionId: 3001,
        status: 'ready',
        outlineStatus: 'ready',
        totalBlocks: 2,
        readyBlocks: 1,
        pendingBlocks: 1,
        sourceParseRunId: 9001,
      );
    }
    return super.fetchHandoutVersionStatus(handoutVersionId);
  }

  @override
  Future<CurrentHandoutBlockModel> fetchCurrentHandoutBlock({
    required String courseId,
    required int currentSec,
  }) {
    currentRequested.complete();
    return current.future;
  }
}

class _DelayedQaFakeApiClient extends _HandoutProviderFakeApiClient {
  final qaRequested = Completer<void>();
  final qaResponse = Completer<QaMessageModel>();

  @override
  Future<QaMessageModel> createQaMessage({
    required QaMessageRequestModel request,
  }) {
    qaRequests.add(request);
    qaRequested.complete();
    return qaResponse.future;
  }
}

class _BlockGenerateFakeApiClient extends _HandoutProviderFakeApiClient {
  var generateBlockCalls = 0;
  var blockStatusCalls = 0;
  var _blockReady = false;

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateBlockCalls++;
    return HandoutBlockGenerateResultModel.fromJson({
      'taskId': 7102,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'handout_block', 'id': blockId},
    });
  }

  @override
  Future<HandoutBlockStatusModel> fetchHandoutBlockStatus(int blockId) async {
    blockStatusCalls++;
    _blockReady = true;
    return HandoutBlockStatusModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-2',
      'status': 'ready',
      'startSec': 360,
      'endSec': 540,
    });
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    if (!_blockReady) {
      return super.fetchLatestHandoutBlocks(courseId);
    }
    return HandoutBlocksModel.fromJson({
      'items': [
        _readyBlockJson(),
        {
          'blockId': 4002,
          'outlineKey': 'outline-2',
          'title': '集合的表示方法',
          'summary': '从列举法过渡到描述法',
          'status': 'ready',
          'contentMd': '### 集合的表示方法',
          'startSec': 360,
          'endSec': 540,
          'citations': [],
        },
      ],
    });
  }
}

class _ReadyBlockGenerateFakeApiClient extends _BlockGenerateFakeApiClient {
  var _generated = false;

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateBlockCalls++;
    _generated = true;
    return HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-2',
      'status': 'ready',
      'startSec': 360,
      'endSec': 540,
    });
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    if (!_generated) {
      return super.fetchLatestHandoutBlocks(courseId);
    }
    return HandoutBlocksModel.fromJson({
      'items': [
        _readyBlockJson(),
        {
          'blockId': 4002,
          'outlineKey': 'outline-2',
          'title': '集合的表示方法',
          'summary': '从列举法过渡到描述法',
          'status': 'ready',
          'contentMd': '### 集合的表示方法',
          'startSec': 360,
          'endSec': 540,
          'citations': [],
        },
      ],
    });
  }
}

class _UnexpectedBlockGenerateEntityFakeApiClient
    extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    return HandoutBlockGenerateResultModel.fromJson({
      'taskId': 7102,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'handout_block', 'id': 4999},
    });
  }
}

class _SwitchCourseBlockGenerateFakeApiClient
    extends _SwitchCourseFakeApiClient {
  final blockStatusRequested = Completer<void>();
  final blockStatus = Completer<HandoutBlockStatusModel>();
  var generateBlockCalls = 0;

  @override
  Future<HandoutVersionStatusModel> fetchHandoutVersionStatus(
    int handoutVersionId,
  ) async {
    if (handoutVersionId == 3001) {
      return const HandoutVersionStatusModel(
        handoutVersionId: 3001,
        status: 'ready',
        outlineStatus: 'ready',
        totalBlocks: 2,
        readyBlocks: 1,
        pendingBlocks: 1,
        sourceParseRunId: 9001,
      );
    }
    return super.fetchHandoutVersionStatus(handoutVersionId);
  }

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateBlockCalls++;
    return HandoutBlockGenerateResultModel.fromJson({
      'taskId': 7102,
      'status': 'queued',
      'nextAction': 'poll',
      'entity': {'type': 'handout_block', 'id': blockId},
    });
  }

  @override
  Future<HandoutBlockStatusModel> fetchHandoutBlockStatus(int blockId) {
    blockStatusRequested.complete();
    return blockStatus.future;
  }
}

Map<String, Object?> _readyBlockJson() {
  return {
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
  };
}
