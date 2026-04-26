import 'package:dio/dio.dart';

import '../../shared/models/confirm_recommendation_request.dart';
import '../../shared/models/confirm_recommendation_result.dart';
import '../../shared/models/recommendation_card.dart';
import '../../shared/models/recommendation_request.dart';
import '../config/app_config.dart';

class ApiClient {
  ApiClient({
    Dio? dio,
    HttpClientAdapter? httpClientAdapter,
    String? baseUrl,
    String? demoToken,
  }) : _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: baseUrl ?? AppConfig.apiBaseUrl,
                headers: {
                  'Authorization': 'Bearer ${demoToken ?? AppConfig.demoToken}',
                  'Content-Type': 'application/json',
                },
              ),
            ) {
    if (httpClientAdapter != null) {
      _dio.httpClientAdapter = httpClientAdapter;
    }
  }

  final Dio _dio;

  Future<List<RecommendationCardModel>> fetchRecommendations(
    RecommendationRequestModel request,
  ) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/recommendations/courses',
      data: request.toJson(),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    final recommendations = data['recommendations'] as List<dynamic>;
    return recommendations
        .map(
          (item) => RecommendationCardModel.fromJson(
            Map<String, dynamic>.from(item as Map),
          ),
        )
        .toList();
  }

  Future<ConfirmRecommendationResultModel> confirmRecommendation({
    required String catalogId,
    required ConfirmRecommendationRequestModel request,
    required String idempotencyKey,
  }) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/recommendations/$catalogId/confirm',
      data: request.toJson(),
      options: Options(
        headers: {
          'Idempotency-Key': idempotencyKey,
        },
      ),
    );

    final data = response.data?['data'] as Map<String, dynamic>;
    return ConfirmRecommendationResultModel.fromJson(data);
  }
}
