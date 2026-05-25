import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/models/bilibili_import_models.dart';

void main() {
  test('QR session parses fields and exposes confirmed and terminal states',
      () {
    final pending = BilibiliQrSessionModel.fromJson({
      'sessionId': 'bili_qr_session_001',
      'status': 'pending_scan',
      'qrCodeUrl': 'https://passport.bilibili.com/qrcode-demo',
      'expiresAt': '2026-05-18T12:15:00+00:00',
    });
    final confirmed = BilibiliQrSessionModel.fromJson({
      'sessionId': 'bili_qr_session_001',
      'status': 'confirmed',
      'qrCodeUrl': 'https://passport.bilibili.com/qrcode-demo',
      'expiresAt': '2026-05-18T12:15:00+00:00',
    });
    final expired = BilibiliQrSessionModel.fromJson({
      'sessionId': 'bili_qr_session_001',
      'status': 'expired',
      'qrCodeUrl': 'https://passport.bilibili.com/qrcode-demo',
      'expiresAt': '2026-05-18T12:15:00+00:00',
    });

    expect(pending.sessionId, 'bili_qr_session_001');
    expect(pending.qrCodeUrl, 'https://passport.bilibili.com/qrcode-demo');
    expect(pending.expiresAt, DateTime.parse('2026-05-18T12:15:00+00:00'));
    expect(pending.isConfirmed, isFalse);
    expect(pending.isTerminal, isFalse);
    expect(confirmed.isConfirmed, isTrue);
    expect(confirmed.isTerminal, isTrue);
    expect(expired.isTerminal, isTrue);
  });

  test('QR session accepts nullable URL and expiry fields', () {
    final session = BilibiliQrSessionModel.fromJson({
      'sessionId': 'bili_qr_session_002',
      'status': 'failed',
      'qrCodeUrl': null,
      'expiresAt': null,
    });

    expect(session.qrCodeUrl, isNull);
    expect(session.expiresAt, isNull);
    expect(session.isTerminal, isTrue);
  });

  test('auth session parses safe login fields without cookie data', () {
    final session = BilibiliAuthSessionModel.fromJson({
      'loginStatus': 'active',
      'userNickname': 'KnowLink Demo',
      'expiresAt': '2026-05-18T14:00:00+00:00',
    });

    expect(session.loginStatus, 'active');
    expect(session.userNickname, 'KnowLink Demo');
    expect(session.expiresAt, DateTime.parse('2026-05-18T14:00:00+00:00'));
    expect(session.isActive, isTrue);
  });

  test('preview parses parts and exposes default selected part ids', () {
    final preview = BilibiliPreviewModel.fromJson({
      'previewId': 'bili_preview_9101',
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
      'sourceType': 'multi_p',
      'title': '课程样例',
      'coverUrl': 'https://i0.hdslb.com/bfs/archive/demo.jpg',
      'totalParts': 2,
      'parts': [
        {
          'partId': 'cid-1001',
          'title': 'P1 导论',
          'durationSec': 600,
          'cid': 1001,
          'pageNo': 1,
          'selectedByDefault': false,
        },
        {
          'partId': 'cid-1002',
          'title': 'P2 例题',
          'durationSec': 900,
          'cid': 1002,
          'pageNo': 2,
          'selectedByDefault': true,
        },
      ],
      'defaultSelectionMode': 'current_part',
    });

    expect(preview.previewId, 'bili_preview_9101');
    expect(preview.parts, hasLength(2));
    expect(preview.parts.first.displayDuration, '10 分钟');
    expect(preview.parts.last.displayDuration, '15 分钟');
    expect(preview.defaultSelectedPartIds, ['cid-1002']);
  });

  test('preview accepts nullable cover URL', () {
    final preview = BilibiliPreviewModel.fromJson({
      'previewId': 'bili_preview_9103',
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD',
      'sourceType': 'single_video',
      'title': '课程样例',
      'coverUrl': null,
      'totalParts': 1,
      'parts': [
        {
          'partId': 'cid-1001',
          'title': 'P1 导论',
          'durationSec': 600,
          'cid': 1001,
          'pageNo': 1,
          'selectedByDefault': true,
        },
      ],
      'defaultSelectionMode': 'current_part',
    });

    expect(preview.coverUrl, isNull);
    expect(preview.defaultSelectedPartIds, ['cid-1001']);
  });

  test('preview part duration rounds down with positive minimum one minute',
      () {
    final oneMinute = BilibiliPreviewPartModel.fromJson({
      'partId': 'cid-1001',
      'title': 'P1 导论',
      'durationSec': 61,
      'cid': 1001,
      'pageNo': 1,
      'selectedByDefault': true,
    });
    final subMinute = BilibiliPreviewPartModel.fromJson({
      'partId': 'cid-1003',
      'title': 'P3 开场',
      'durationSec': 59,
      'cid': 1003,
      'pageNo': 3,
      'selectedByDefault': false,
    });
    final zeroMinute = BilibiliPreviewPartModel.fromJson({
      'partId': 'cid-1002',
      'title': 'P2 片头',
      'durationSec': 0,
      'cid': 1002,
      'pageNo': 2,
      'selectedByDefault': false,
    });

    expect(oneMinute.displayDuration, '1 分钟');
    expect(subMinute.displayDuration, '1 分钟');
    expect(zeroMinute.displayDuration, '0 分钟');
  });

  test('preview defaults to first part id when no part is selected', () {
    final preview = BilibiliPreviewModel.fromJson({
      'previewId': 'bili_preview_9102',
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD',
      'sourceType': 'multi_p',
      'title': '课程样例',
      'coverUrl': 'https://i0.hdslb.com/bfs/archive/demo.jpg',
      'totalParts': 2,
      'parts': [
        {
          'partId': 'cid-1001',
          'title': 'P1 导论',
          'durationSec': 600,
          'cid': 1001,
          'pageNo': 1,
          'selectedByDefault': false,
        },
        {
          'partId': 'cid-1002',
          'title': 'P2 例题',
          'durationSec': 900,
          'cid': 1002,
          'pageNo': 2,
          'selectedByDefault': false,
        },
      ],
      'defaultSelectionMode': 'current_part',
    });

    expect(preview.defaultSelectedPartIds, ['cid-1001']);
  });

  test('create request serializes qualityPreference with android safe default',
      () {
    const request = BilibiliImportCreateRequestModel(
      previewId: 'bili_preview_9101',
      sourceUrl: 'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
      selectionMode: 'selected_parts',
      selectedPartIds: ['cid-1001'],
    );

    expect(request.toJson(), {
      'previewId': 'bili_preview_9101',
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
      'selectionMode': 'selected_parts',
      'selectedPartIds': ['cid-1001'],
      'qualityPreference': 'android_safe',
    });
  });

  test('run parses status fields and exposes terminal recoverable helpers', () {
    final downloading = BilibiliImportRunModel.fromJson({
      'importRunId': 9001,
      'courseId': 101,
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD?p=2',
      'sourceType': 'multi_p',
      'status': 'downloading',
      'progressPct': 42,
      'stage': 'download',
      'taskId': 7001,
      'resourceIds': <int>[],
      'preview': {
        'title': '线性代数复习',
        'parts': [
          {
            'partId': 'cid-1001',
            'title': 'P1 行列式',
            'durationSec': 1800,
          },
        ],
      },
      'errorCode': null,
      'failureReason': null,
      'recoverable': false,
      'nextAction': 'poll',
    });
    final recoverable = BilibiliImportRunModel.fromJson({
      'importRunId': 9002,
      'courseId': 101,
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD?p=3',
      'sourceType': 'multi_p',
      'status': 'recoverable',
      'progressPct': 58,
      'stage': 'error',
      'taskId': 7002,
      'resourceIds': <int>[],
      'preview': null,
      'errorCode': 'bilibili.auth_expired',
      'failureReason': '登录态已过期',
      'recoverable': true,
      'nextAction': 'retry',
    });
    final imported = BilibiliImportRunModel.fromJson({
      'importRunId': 9003,
      'courseId': 101,
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD?p=4',
      'sourceType': 'multi_p',
      'status': 'imported',
      'progressPct': 100,
      'stage': 'done',
      'taskId': 7003,
      'resourceIds': [501, 502],
      'preview': null,
      'errorCode': null,
      'failureReason': null,
      'recoverable': false,
      'nextAction': 'none',
    });

    expect(downloading.previewTitle, '线性代数复习');
    expect(downloading.isTerminal, isFalse);
    expect(downloading.canCancel, isTrue);
    expect(recoverable.isTerminal, isTrue);
    expect(recoverable.isFailed, isTrue);
    expect(recoverable.recoverable, isTrue);
    expect(recoverable.canCancel, isFalse);
    expect(imported.isImported, isTrue);
    expect(imported.resourceIds, [501, 502]);
  });

  test('run accepts nullable task id and next action', () {
    final run = BilibiliImportRunModel.fromJson({
      'importRunId': 9004,
      'courseId': 101,
      'sourceUrl': 'https://www.bilibili.com/video/BV1xx411c7mD?p=5',
      'sourceType': 'multi_p',
      'status': 'failed',
      'progressPct': 0,
      'stage': 'error',
      'taskId': null,
      'resourceIds': <int>[],
      'preview': null,
      'errorCode': 'bilibili.metadata_failed',
      'failureReason': '元数据获取失败',
      'recoverable': false,
      'nextAction': null,
    });

    expect(run.taskId, isNull);
    expect(run.nextAction, isNull);
    expect(run.isTerminal, isTrue);
    expect(run.isFailed, isTrue);
  });
}
