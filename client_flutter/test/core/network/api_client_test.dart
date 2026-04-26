import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:knowlink_client/core/network/api_client.dart';
import 'package:knowlink_client/shared/models/confirm_recommendation_request.dart';
import 'package:knowlink_client/shared/models/recommendation_enums.dart';
import 'package:knowlink_client/shared/models/recommendation_request.dart';

void main() {
  test('fetchRecommendations sends expected path, auth header, and parses data',
      () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'recommendations': [
                {
                  'catalogId': 'math-final-01',
                  'title': '高等数学期末冲刺',
                  'provider': 'KnowLink Seed',
                  'level': 'intermediate',
                  'estimatedHours': 4,
                  'fitScore': 96,
                  'reasons': ['难度与当前基础匹配'],
                  'defaultResourceManifest': [
                    {
                      'resourceType': 'mp4',
                      'required': true,
                      'description': '主课程视频',
                    },
                  ],
                },
              ],
            },
          }),
          200,
          headers: {
            Headers.contentTypeHeader: ['application/json'],
          },
        );
      },
    );
    final client = ApiClient(
      httpClientAdapter: adapter,
      baseUrl: 'https://example.test',
      demoToken: 'week-one-token',
    );

    final request = RecommendationRequestModel(
      goalText: '高等数学期末复习',
      selfLevel: SelfLevel.intermediate,
      timeBudgetMinutes: 240,
      examAt: DateTime.utc(2026, 6, 15, 1),
      preferredStyle: PreferredStyle.exam,
    );

    final recommendations = await client.fetchRecommendations(request);

    expect(recommendations, hasLength(1));
    expect(recommendations.single.catalogId, 'math-final-01');
    expect(adapter.requests, hasLength(1));

    final captured = adapter.requests.single;
    expect(captured.method, 'POST');
    expect(captured.path, '/api/v1/recommendations/courses');
    expect(_headerValue(captured.headers, 'authorization'),
        'Bearer week-one-token');
    expect(captured.data, request.toJson());
  });

  test('confirmRecommendation sends idempotency key and parses created course',
      () async {
    final adapter = _RecordingHttpClientAdapter(
      onFetch: (options, _) async {
        return ResponseBody.fromString(
          jsonEncode({
            'data': {
              'course': {
                'courseId': 101,
                'title': '高数期末冲刺课',
                'entryType': 'recommendation',
                'catalogId': 'math-final-01',
                'lifecycleStatus': 'draft',
                'pipelineStage': 'idle',
                'pipelineStatus': 'idle',
                'updatedAt': '2026-04-18T15:00:00+00:00',
              },
              'createdFromCatalogId': 'math-final-01',
            },
          }),
          201,
          headers: {
            Headers.contentTypeHeader: ['application/json'],
          },
        );
      },
    );
    final client = ApiClient(
      httpClientAdapter: adapter,
      baseUrl: 'https://example.test',
      demoToken: 'week-one-token',
    );
    const request = ConfirmRecommendationRequestModel(
      goalText: '高等数学期末复习',
      preferredStyle: PreferredStyle.exam,
      titleOverride: '高数期末冲刺课',
    );

    final result = await client.confirmRecommendation(
      catalogId: 'math-final-01',
      request: request,
      idempotencyKey: 'rec-confirm-1',
    );

    expect(result.createdFromCatalogId, 'math-final-01');
    expect(result.course.courseId, 101);
    expect(adapter.requests, hasLength(1));

    final captured = adapter.requests.single;
    expect(captured.method, 'POST');
    expect(
      captured.path,
      '/api/v1/recommendations/math-final-01/confirm',
    );
    expect(_headerValue(captured.headers, 'authorization'),
        'Bearer week-one-token');
    expect(
      _headerValue(captured.headers, 'idempotency-key'),
      'rec-confirm-1',
    );
    expect(captured.data, request.toJson());
  });
}

String? _headerValue(Map<String, dynamic> headers, String key) {
  for (final entry in headers.entries) {
    if (entry.key.toLowerCase() == key.toLowerCase()) {
      return entry.value?.toString();
    }
  }
  return null;
}

class _RecordingHttpClientAdapter implements HttpClientAdapter {
  _RecordingHttpClientAdapter({
    required this.onFetch,
  });

  final Future<ResponseBody> Function(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
  ) onFetch;

  final List<RequestOptions> requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    return onFetch(options, requestStream);
  }

  @override
  void close({
    bool force = false,
  }) {}
}
