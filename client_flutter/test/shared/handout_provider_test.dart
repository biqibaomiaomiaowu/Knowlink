import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/handout_models.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';
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

  test('default selection follows the first outline child, not block order',
      () async {
    final fakeApiClient = _OutOfOrderBlocksFakeApiClient();
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
    expect(state.outlineChildren.map((child) => child.blockId), [4001, 4002]);
    expect(state.selectedOutlineChild?.blockId, 4001);
    expect(state.selectedBlock?.blockId, 4001);
    expect(container.read(activeBlockProvider), 4001);
  });

  test('load honors pending home resume target before default selection',
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
    container.read(handoutResumeTargetProvider.notifier).state =
        const HandoutResumeTarget(courseId: '101', blockId: 4002);

    await container.read(handoutProvider.notifier).load(
          '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.selectedBlock?.blockId, 4002);
    expect(container.read(activeBlockProvider), 4002);
    expect(container.read(handoutResumeTargetProvider), isNull);
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

  test('load auto generates the first outline child when it is pending once',
      () async {
    final fakeApiClient = _FirstPendingBlockFakeApiClient();
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
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(fakeApiClient.generatedBlockIds, [4001]);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4001);

    await container.read(handoutProvider.notifier).refreshData('101');
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(fakeApiClient.generatedBlockIds, [4001]);
  });

  test('load retries first pending child auto generation after failure',
      () async {
    final fakeApiClient = _FlakyFirstPendingBlockFakeApiClient();
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
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(fakeApiClient.generateAttempts, 1);
    expect(fakeApiClient.generatedBlockIds, isEmpty);

    await container.read(handoutProvider.notifier).refreshData('101');
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(fakeApiClient.generateAttempts, 2);
    expect(fakeApiClient.generatedBlockIds, [4001]);
  });

  test('load does not auto generate later pending children', () async {
    final fakeApiClient = _LaterPendingBlockFakeApiClient();
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
    await Future<void>.delayed(Duration.zero);

    expect(fakeApiClient.generatedBlockIds, isEmpty);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4001);
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
    expect(fakeApiClient.playbackResourceIds, [501]);
    expect(
      container.read(handoutProvider).jumpTarget.valueOrNull?.blockId,
      4002,
    );
    expect(
      container.read(handoutProvider).playback.valueOrNull?.playbackUrl,
      'http://127.0.0.1:9000/video-501.mp4?X-Amz-Signature=demo',
    );
  });

  test('jump target with video resource fetches playback URL', () async {
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
    final block = container.read(handoutProvider).blocks.valueOrNull!.items[0];

    await container.read(handoutProvider.notifier).selectBlock(block);

    expect(fakeApiClient.jumpTargetBlockIds, [4001]);
    expect(fakeApiClient.playbackResourceIds, [501]);
    expect(container.read(handoutProvider).playback.hasError, isFalse);
    expect(
      container.read(handoutProvider).playback.valueOrNull?.durationSec,
      isNull,
    );
  });

  test('jump target start time overrides outline child start time', () async {
    final fakeApiClient = _JumpTargetOffsetFakeApiClient();
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
    final block = container.read(handoutProvider).blocks.valueOrNull!.items[0];

    await container.read(handoutProvider.notifier).selectBlock(block);

    expect(block.startSec, 120);
    expect(
        container.read(handoutProvider).jumpTarget.valueOrNull?.startSec, 135);
    expect(container.read(playerStateProvider).positionSec, 135);
    expect(fakeApiClient.playbackResourceIds, [501]);
  });

  test('jump target without video keeps playback empty without blocking QA',
      () async {
    final fakeApiClient = _NoVideoJumpTargetFakeApiClient();
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
    final block = container.read(handoutProvider).blocks.valueOrNull!.items[0];

    await container.read(handoutProvider.notifier).selectBlock(block);
    await container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '没有视频也能问答吗？',
        );

    final state = container.read(handoutProvider);
    expect(state.jumpTarget.valueOrNull?.videoResourceId, isNull);
    expect(state.playback.valueOrNull, isNull);
    expect(state.playback.hasError, isFalse);
    expect(fakeApiClient.playbackResourceIds, isEmpty);
    expect(fakeApiClient.qaRequests.single.handoutBlockId, 4001);
  });

  test('playback request errors stay scoped to playback state', () async {
    final cases = [
      (statusCode: 409, errorCode: 'resource.not_video'),
      (statusCode: 503, errorCode: 'resource.playback_unavailable'),
      (statusCode: null, errorCode: 'network.unavailable'),
    ];

    for (final item in cases) {
      final fakeApiClient = _PlaybackFailingFakeApiClient(
        statusCode: item.statusCode,
        errorCode: item.errorCode,
      );
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
      final block =
          container.read(handoutProvider).blocks.valueOrNull!.items[0];
      await container.read(handoutProvider.notifier).selectBlock(block);

      final state = container.read(handoutProvider);
      expect(state.jumpTarget.valueOrNull?.blockId, 4001);
      expect(state.playback.hasError, isTrue);
      expect(state.selectedBlock?.blockId, 4001);
      expect(state.selectedBlockQaMessages, isEmpty);
    }
  });

  test('retry playback refreshes the presigned URL without new jump target',
      () async {
    final fakeApiClient = _PlaybackRetryFakeApiClient();
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
    final block = container.read(handoutProvider).blocks.valueOrNull!.items[0];
    await container.read(handoutProvider.notifier).selectBlock(block);

    expect(container.read(handoutProvider).playback.hasError, isTrue);
    expect(fakeApiClient.jumpTargetBlockIds, [4001]);
    expect(fakeApiClient.playbackResourceIds, [501]);

    await container.read(handoutProvider.notifier).retryPlayback();

    expect(fakeApiClient.jumpTargetBlockIds, [4001]);
    expect(fakeApiClient.playbackResourceIds, [501, 501]);
    expect(
      container.read(handoutProvider).playback.valueOrNull?.playbackUrl,
      'http://127.0.0.1:9000/video-501-retry.mp4?X-Amz-Signature=retry',
    );
  });

  test('stale playback response is ignored after switching selected block',
      () async {
    final fakeApiClient = _StalePlaybackFakeApiClient();
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
    final staleSelection =
        container.read(handoutProvider.notifier).selectBlock(blocks[0]);
    await fakeApiClient.playbackRequested.future;

    await container.read(handoutProvider.notifier).selectBlock(blocks[1]);
    fakeApiClient.playback.complete(
      CourseResourcePlaybackModel.fromJson({
        'resourceId': 501,
        'resourceType': 'mp4',
        'playbackUrl': 'http://127.0.0.1:9000/stale.mp4',
        'mimeType': 'video/mp4',
        'expiresAt': '2026-04-18T16:00:00+00:00',
        'durationSec': 120,
      }),
    );
    await staleSelection;

    final state = container.read(handoutProvider);
    expect(state.selectedBlock?.blockId, 4002);
    expect(state.jumpTarget.valueOrNull?.blockId, 4002);
    expect(state.playback.valueOrNull, isNull);
  });

  test('course reload invalidates in-flight playback response', () async {
    final fakeApiClient = _StalePlaybackSwitchCourseFakeApiClient();
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
    final staleSelection = container.read(handoutProvider.notifier).selectBlock(
        container.read(handoutProvider).blocks.valueOrNull!.items[0]);
    await fakeApiClient.playbackRequested.future;

    await container.read(handoutProvider.notifier).load(
          '202',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    fakeApiClient.playback.complete(
      CourseResourcePlaybackModel.fromJson({
        'resourceId': 501,
        'resourceType': 'mp4',
        'playbackUrl': 'http://127.0.0.1:9000/stale.mp4',
        'mimeType': 'video/mp4',
        'expiresAt': '2026-04-18T16:00:00+00:00',
        'durationSec': 120,
      }),
    );
    await staleSelection;

    final state = container.read(handoutProvider);
    expect(state.latest.valueOrNull?.handoutVersionId, 3002);
    expect(state.selectedBlock?.blockId, 5001);
    expect(state.playback.valueOrNull, isNull);
  });

  test('blocks outside the outline cannot drive selection or jump target',
      () async {
    final fakeApiClient = _OrphanBlockFakeApiClient();
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
    final orphanBlock = container
        .read(handoutProvider)
        .blocks
        .valueOrNull!
        .items
        .singleWhere((block) => block.blockId == 4999);

    await container.read(handoutProvider.notifier).selectBlock(orphanBlock);
    await container.read(handoutProvider.notifier).requestJumpTarget(4999);
    await container.read(handoutProvider.notifier).generateBlock(
          4999,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    await container.read(handoutProvider.notifier).submitQuestion(
          courseId: '101',
          question: '孤儿 block 会被选中吗？',
        );

    expect(container.read(handoutProvider).selectedOutlineChild?.blockId, 4001);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4001);
    expect(container.read(activeBlockProvider), 4001);
    expect(fakeApiClient.jumpTargetBlockIds, isEmpty);
    expect(fakeApiClient.generateBlockCalls, 0);
    expect(fakeApiClient.qaRequests.single.handoutBlockId, 4001);
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

  test('playhead highlight does not change selected QA context', () async {
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

    final highlightedState = container.read(handoutProvider);
    expect(highlightedState.highlightedChildFor(380)?.blockId, 4002);
    expect(highlightedState.selectedBlock?.blockId, 4001);
    expect(highlightedState.qaSubmit.isLoading, isTrue);
    expect(highlightedState.jumpTarget.valueOrNull, isNull);

    fakeApiClient.qaResponse.complete(
      QaMessageModel.fromJson({
        'sessionId': 6001,
        'messageId': 6002,
        'answerMd': '旧回答',
        'citations': [],
      }),
    );
    await pendingQa;

    expect(container.read(courseFlowProvider).sessionId, 6001);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4001);
    expect(container.read(handoutProvider).qaMessagesByBlockId[4001],
        hasLength(1));
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

  test('block generation loading state is retained by block id after switching',
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
    final firstBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[0];
    final secondBlock =
        container.read(handoutProvider).blocks.valueOrNull!.items[1];
    await container.read(handoutProvider.notifier).selectBlock(secondBlock);

    final firstGenerate =
        container.read(handoutProvider.notifier).generateBlock(
              4002,
              courseId: '101',
              pollInterval: Duration.zero,
              maxAttempts: 1,
            );
    await fakeApiClient.blockStatusRequested.future;

    await container.read(handoutProvider.notifier).selectBlock(firstBlock);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4001);
    expect(container.read(handoutProvider).isBlockGenerating(4002), isTrue);
    expect(
      container.read(handoutProvider).blockGenerateRequestFor(4002).isLoading,
      isTrue,
    );
    expect(
      container.read(handoutProvider).blockGenerateRequestFor(4001).isLoading,
      isFalse,
    );

    await container.read(handoutProvider.notifier).selectBlock(secondBlock);
    expect(container.read(handoutProvider).selectedBlock?.blockId, 4002);
    expect(container.read(handoutProvider).isBlockGenerating(4002), isTrue);
    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    expect(fakeApiClient.generateBlockCalls, 1);

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

    expect(container.read(handoutProvider).isBlockGenerating(4002), isFalse);
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

  test('direct ready block generation response wins over stale pending blocks',
      () async {
    final fakeApiClient = _ReadyBlockGenerateStaleBlocksFakeApiClient();
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
    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.blocks.valueOrNull!.items[1].status, 'pending');
    expect(state.effectiveBlockStatus(4002), 'ready');

    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    expect(fakeApiClient.generateBlockCalls, 1);
  });

  test('outline ready status wins over stale pending blocks', () async {
    final fakeApiClient = _OutlineReadyBlockPendingFakeApiClient();
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
    expect(state.blocks.valueOrNull!.items[1].status, 'pending');
    expect(state.effectiveBlockStatus(4002), 'ready');

    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );
    expect(fakeApiClient.generateBlockCalls, 0);
  });

  test('playhead near next pending block prefetches it once', () async {
    final fakeApiClient = _PrefetchBlockFakeApiClient();
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

    await container
        .read(handoutProvider.notifier)
        .prefetchNextBlockNearPosition(
          courseId: '101',
          positionSec: 329,
        );
    expect(fakeApiClient.generateBlockCalls, 0);

    await container
        .read(handoutProvider.notifier)
        .prefetchNextBlockNearPosition(
          courseId: '101',
          positionSec: 330,
        );
    expect(fakeApiClient.generatedBlockIds, [4002]);

    await container
        .read(handoutProvider.notifier)
        .prefetchNextBlockNearPosition(
          courseId: '101',
          positionSec: 331,
        );
    expect(fakeApiClient.generatedBlockIds, [4002]);
  });

  test('playhead prefetch retries after a failed generation request', () async {
    final fakeApiClient = _FlakyPrefetchBlockFakeApiClient();
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

    await container
        .read(handoutProvider.notifier)
        .prefetchNextBlockNearPosition(
          courseId: '101',
          positionSec: 330,
        );

    expect(fakeApiClient.generateAttempts, 1);
    expect(fakeApiClient.generatedBlockIds, isEmpty);

    await container
        .read(handoutProvider.notifier)
        .prefetchNextBlockNearPosition(
          courseId: '101',
          positionSec: 331,
        );

    expect(fakeApiClient.generateAttempts, 2);
    expect(fakeApiClient.generatedBlockIds, [4002]);
  });

  test('playhead prefetch skips ready and generating next blocks', () async {
    final cases = [
      _PrefetchBlockFakeApiClient(nextStatus: 'ready'),
      _PrefetchBlockFakeApiClient(nextStatus: 'generating'),
    ];

    for (final fakeApiClient in cases) {
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
      await container
          .read(handoutProvider.notifier)
          .prefetchNextBlockNearPosition(
            courseId: '101',
            positionSec: 335,
          );

      expect(fakeApiClient.generateBlockCalls, 0);
    }
  });

  test('playhead prefetch works in gaps before the next block', () async {
    final fakeApiClient = _PrefetchBlockFakeApiClient(
      firstEndSec: 320,
      nextStartSec: 360,
    );
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
    await container
        .read(handoutProvider.notifier)
        .prefetchNextBlockNearPosition(
          courseId: '101',
          positionSec: 330,
        );

    expect(fakeApiClient.generatedBlockIds, [4002]);
  });

  test('block refresh clears selection when selected child leaves outline',
      () async {
    final fakeApiClient = _SelectionInvalidatedOutlineFakeApiClient();
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
    expect(container.read(activeBlockProvider), 4002);

    await container.read(handoutProvider.notifier).generateBlock(
          4002,
          courseId: '101',
          pollInterval: Duration.zero,
          maxAttempts: 1,
        );

    final state = container.read(handoutProvider);
    expect(state.selectedBlockId, isNull);
    expect(state.selectedOutlineChild, isNull);
    expect(state.selectedBlock, isNull);
    expect(container.read(activeBlockProvider), isNull);
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
  final List<int> playbackResourceIds = [];
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
    return HandoutOutlineModel.fromJson(_outlineJson());
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

class _FirstPendingBlockFakeApiClient extends _HandoutProviderFakeApiClient {
  final generatedBlockIds = <int>[];
  var _blockReady = false;

  @override
  Future<HandoutOutlineModel> fetchLatestHandoutOutline(
    String courseId,
  ) async {
    return HandoutOutlineModel.fromJson(
      _outlineJson(
        sections: [
          {
            'outlineKey': 'section-1',
            'title': '极限与集合',
            'summary': '从极限连续过渡到集合表示',
            'startSec': 120,
            'endSec': 540,
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
                'generationStatus': _blockReady ? 'ready' : 'pending',
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
            ],
          },
        ],
      ),
    );
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    return HandoutBlocksModel.fromJson({
      'items': [
        {
          ..._readyBlockJson(),
          'status': _blockReady ? 'ready' : 'pending',
          'contentMd': _blockReady ? '### 极限与连续' : null,
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
      ],
    });
  }

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generatedBlockIds.add(blockId);
    _blockReady = true;
    return HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-1',
      'status': 'ready',
      'startSec': 120,
      'endSec': 360,
    });
  }
}

class _FlakyFirstPendingBlockFakeApiClient
    extends _FirstPendingBlockFakeApiClient {
  var generateAttempts = 0;

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateAttempts++;
    if (generateAttempts == 1) {
      throw StateError('block generation failed');
    }
    return super.generateHandoutBlock(
      blockId: blockId,
      idempotencyKey: idempotencyKey,
    );
  }
}

class _LaterPendingBlockFakeApiClient extends _HandoutProviderFakeApiClient {
  final generatedBlockIds = <int>[];

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generatedBlockIds.add(blockId);
    return HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-2',
      'status': 'ready',
      'startSec': 360,
      'endSec': 540,
    });
  }
}

class _OutOfOrderBlocksFakeApiClient extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    return HandoutBlocksModel.fromJson({
      'items': [
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
        _readyBlockJson(),
      ],
    });
  }
}

class _OrphanBlockFakeApiClient extends _HandoutProviderFakeApiClient {
  var generateBlockCalls = 0;

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    return HandoutBlocksModel.fromJson({
      'items': [
        _readyBlockJson(),
        {
          'blockId': 4999,
          'outlineKey': 'outline-orphan',
          'title': '孤儿讲义块',
          'summary': '不在 outline child 中的块',
          'status': 'ready',
          'contentMd': '### 孤儿讲义块',
          'startSec': 900,
          'endSec': 960,
          'citations': [],
        },
      ],
    });
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
      return HandoutOutlineModel.fromJson(_outlineJson(
        handoutVersionId: 3002,
        title: '新课程讲义',
        summary: '切课后的讲义',
        sections: [
          {
            'outlineKey': 'section-new',
            'title': '新课程章节',
            'summary': '切课后的章节',
            'startSec': 0,
            'endSec': 120,
            'sortNo': 1,
            'children': [
              {
                'outlineKey': 'outline-new',
                'blockId': 5001,
                'title': '新课程块',
                'summary': '切课后的块',
                'startSec': 0,
                'endSec': 120,
                'sortNo': 1,
                'generationStatus': 'ready',
                'sourceSegmentKeys': ['mp4-new'],
                'topicTags': ['新课程'],
              },
            ],
          },
        ],
      ));
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

class _NoVideoJumpTargetFakeApiClient extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    jumpTargetBlockIds.add(blockId);
    return HandoutJumpTargetModel(
      blockId: blockId,
      startSec: blockId == 4002 ? 360 : 120,
      docResourceId: 502,
      pageNo: 2,
    );
  }
}

class _JumpTargetOffsetFakeApiClient extends _HandoutProviderFakeApiClient {
  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    jumpTargetBlockIds.add(blockId);
    return HandoutJumpTargetModel(
      blockId: blockId,
      videoResourceId: 501,
      startSec: blockId == 4002 ? 375 : 135,
      docResourceId: 502,
      pageNo: 2,
    );
  }
}

class _PlaybackFailingFakeApiClient extends _HandoutProviderFakeApiClient {
  _PlaybackFailingFakeApiClient({
    required this.statusCode,
    required this.errorCode,
  });

  final int? statusCode;
  final String errorCode;

  @override
  Future<CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) async {
    playbackResourceIds.add(resourceId);
    final requestOptions =
        RequestOptions(path: '/api/v1/course-resources/$resourceId/playback');
    throw DioException(
      requestOptions: requestOptions,
      response: statusCode == null
          ? null
          : Response<Map<String, dynamic>>(
              requestOptions: requestOptions,
              statusCode: statusCode,
              data: {
                'errorCode': errorCode,
              },
            ),
    );
  }
}

class _PlaybackRetryFakeApiClient extends _HandoutProviderFakeApiClient {
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
          'http://127.0.0.1:9000/video-$resourceId-retry.mp4?X-Amz-Signature=retry',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-04-18T16:00:00+00:00',
      'durationSec': null,
    });
  }
}

class _StalePlaybackFakeApiClient extends _NoVideoJumpTargetFakeApiClient {
  final playbackRequested = Completer<void>();
  final playback = Completer<CourseResourcePlaybackModel>();

  @override
  Future<HandoutJumpTargetModel> fetchHandoutJumpTarget(int blockId) async {
    jumpTargetBlockIds.add(blockId);
    if (blockId == 4001) {
      return const HandoutJumpTargetModel(
        blockId: 4001,
        videoResourceId: 501,
        startSec: 120,
      );
    }
    return const HandoutJumpTargetModel(
      blockId: 4002,
      startSec: 360,
    );
  }

  @override
  Future<CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) {
    playbackResourceIds.add(resourceId);
    playbackRequested.complete();
    return playback.future;
  }
}

class _StalePlaybackSwitchCourseFakeApiClient
    extends _SwitchCourseFakeApiClient {
  final playbackRequested = Completer<void>();
  final playback = Completer<CourseResourcePlaybackModel>();

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
  Future<CourseResourcePlaybackModel> fetchCourseResourcePlayback(
    int resourceId,
  ) {
    playbackResourceIds.add(resourceId);
    playbackRequested.complete();
    return playback.future;
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

class _ReadyBlockGenerateStaleBlocksFakeApiClient
    extends _HandoutProviderFakeApiClient {
  var generateBlockCalls = 0;

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateBlockCalls++;
    return HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-2',
      'status': 'ready',
      'startSec': 360,
      'endSec': 540,
    });
  }
}

class _OutlineReadyBlockPendingFakeApiClient
    extends _HandoutProviderFakeApiClient {
  var generateBlockCalls = 0;

  @override
  Future<HandoutOutlineModel> fetchLatestHandoutOutline(
    String courseId,
  ) async {
    return HandoutOutlineModel.fromJson(_outlineJson(
      sections: [
        {
          'outlineKey': 'section-1',
          'title': '极限与集合',
          'summary': '从极限连续过渡到集合表示',
          'startSec': 120,
          'endSec': 540,
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
              'generationStatus': 'ready',
              'sourceSegmentKeys': ['mp4-c2'],
              'topicTags': ['集合'],
            },
          ],
        },
      ],
    ));
  }

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateBlockCalls++;
    return HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-2',
      'status': 'ready',
      'startSec': 360,
      'endSec': 540,
    });
  }
}

class _PrefetchBlockFakeApiClient extends _HandoutProviderFakeApiClient {
  _PrefetchBlockFakeApiClient({
    this.nextStatus = 'pending',
    this.firstEndSec = 360,
    this.nextStartSec = 360,
  });

  final String nextStatus;
  final int firstEndSec;
  final int nextStartSec;
  final generatedBlockIds = <int>[];

  int get generateBlockCalls => generatedBlockIds.length;

  @override
  Future<HandoutOutlineModel> fetchLatestHandoutOutline(
    String courseId,
  ) async {
    return HandoutOutlineModel.fromJson(_outlineJson(
      sections: [
        {
          'outlineKey': 'section-1',
          'title': '极限与集合',
          'summary': '从极限连续过渡到集合表示',
          'startSec': 120,
          'endSec': 540,
          'sortNo': 1,
          'children': [
            {
              'outlineKey': 'outline-1',
              'blockId': 4001,
              'title': '极限与连续',
              'summary': '先抓必考定义和题型',
              'startSec': 120,
              'endSec': firstEndSec,
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
              'startSec': nextStartSec,
              'endSec': 540,
              'sortNo': 2,
              'generationStatus': nextStatus,
              'sourceSegmentKeys': ['mp4-c2'],
              'topicTags': ['集合'],
            },
          ],
        },
      ],
    ));
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
          'status': nextStatus,
          'contentMd': nextStatus == 'ready' ? '### 集合的表示方法' : null,
          'startSec': nextStartSec,
          'endSec': 540,
          'citations': [],
        },
      ],
    });
  }

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generatedBlockIds.add(blockId);
    return HandoutBlockGenerateResultModel.fromJson({
      'blockId': blockId,
      'outlineKey': 'outline-2',
      'status': 'generating',
      'startSec': 360,
      'endSec': 540,
    });
  }
}

class _FlakyPrefetchBlockFakeApiClient extends _PrefetchBlockFakeApiClient {
  var generateAttempts = 0;

  @override
  Future<HandoutBlockGenerateResultModel> generateHandoutBlock({
    required int blockId,
    required String idempotencyKey,
  }) async {
    generateAttempts++;
    if (generateAttempts == 1) {
      throw StateError('prefetch failed');
    }
    return super.generateHandoutBlock(
      blockId: blockId,
      idempotencyKey: idempotencyKey,
    );
  }
}

class _SelectionInvalidatedOutlineFakeApiClient
    extends _BlockGenerateFakeApiClient {
  @override
  Future<HandoutOutlineModel> fetchLatestHandoutOutline(
    String courseId,
  ) async {
    if (blockStatusCalls == 0) {
      return super.fetchLatestHandoutOutline(courseId);
    }
    return HandoutOutlineModel.fromJson(_outlineJson(
      sections: [
        {
          'outlineKey': 'section-1',
          'title': '极限与集合',
          'summary': '刷新后只保留第一个 child',
          'startSec': 120,
          'endSec': 360,
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
          ],
        },
      ],
    ));
  }

  @override
  Future<HandoutBlocksModel> fetchLatestHandoutBlocks(String courseId) async {
    if (blockStatusCalls == 0) {
      return super.fetchLatestHandoutBlocks(courseId);
    }
    return HandoutBlocksModel.fromJson({
      'items': [
        _readyBlockJson(),
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

Map<String, Object?> _outlineJson({
  int handoutVersionId = 3001,
  String title = '高数期末冲刺讲义',
  String summary = '按视频时间线组织',
  List<Map<String, Object?>>? sections,
}) {
  return {
    'handoutVersionId': handoutVersionId,
    'title': title,
    'summary': summary,
    'items': sections ??
        [
          {
            'outlineKey': 'section-1',
            'title': '极限与集合',
            'summary': '从极限连续过渡到集合表示',
            'startSec': 120,
            'endSec': 540,
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
            ],
          },
        ],
    'outlineUsedFallback': false,
    'outlineIssues': [],
  };
}
