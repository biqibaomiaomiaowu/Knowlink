import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/resource_upload_models.dart';

void main() {
  test('course resource playback model parses nullable duration', () {
    final playback = CourseResourcePlaybackModel.fromJson({
      'resourceId': 501,
      'resourceType': 'mp4',
      'playbackUrl':
          'http://127.0.0.1:9000/knowlink/raw/1/101/temp/video.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256',
      'mimeType': 'video/mp4',
      'expiresAt': '2026-04-18T16:00:00+00:00',
      'durationSec': null,
    });

    expect(playback.resourceId, 501);
    expect(playback.resourceType, ResourceType.mp4);
    expect(playback.mimeType, 'video/mp4');
    expect(playback.durationSec, isNull);
    expect(
      playback.playbackUrl,
      'http://127.0.0.1:9000/knowlink/raw/1/101/temp/video.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256',
    );
    expect(playback.expiresAt, DateTime.parse('2026-04-18T16:00:00+00:00'));
  });
}
